"""Base crawler class for DiversiPlant data sources."""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Generator, Dict, Any, Optional
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class BaseCrawler(ABC):
    """Abstract base class for all data crawlers."""

    def __init__(self, db_url: str):
        """
        Initialize the crawler.

        Args:
            db_url: PostgreSQL connection string
        """
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)
        self.logger = logging.getLogger(f"crawler.{self.name}")
        self.stats = {
            'processed': 0,
            'inserted': 0,
            'updated': 0,
            'errors': 0,
            'skipped': 0
        }
        self._run_id: Optional[int] = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name identifier for the crawler."""
        pass

    @abstractmethod
    def fetch_data(self, **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        Fetch data from the external source.

        Yields:
            Dict containing raw data from the source
        """
        pass

    @abstractmethod
    def transform(self, raw_data: Dict) -> Dict:
        """
        Transform raw data to match the database schema.

        Args:
            raw_data: Raw data from the source

        Returns:
            Transformed data ready for database insertion
        """
        pass

    def validate(self, data: Dict) -> bool:
        """
        Validate transformed data before insertion.

        Args:
            data: Transformed data

        Returns:
            True if valid, False otherwise
        """
        # Base validation - must have canonical_name
        return bool(data.get('canonical_name'))

    def run(self, mode: str = 'incremental', **kwargs):
        """
        Execute the crawler.

        Args:
            mode: 'full' for complete refresh, 'incremental' for updates only
            **kwargs: Additional arguments passed to fetch_data
        """
        self.logger.info(f"Starting {self.name} crawler in {mode} mode")
        self._log_start()

        try:
            for batch in self.fetch_data(mode=mode, **kwargs):
                try:
                    if isinstance(batch, list):
                        for item in batch:
                            self._process_item(item)
                    else:
                        self._process_item(batch)
                except Exception as e:
                    self.stats['errors'] += 1
                    self.logger.error(f"Error processing batch: {e}")
                    self._log_message('ERROR', str(e))

            self._log_success()
            self.logger.info(f"Completed {self.name}: {self.stats}")

        except Exception as e:
            self.logger.error(f"Crawler failed: {e}")
            self._log_error(str(e))
            raise

    def _process_item(self, raw_data: Dict):
        """Process a single data item."""
        self.stats['processed'] += 1

        try:
            transformed = self.transform(raw_data)

            if not self.validate(transformed):
                self.stats['skipped'] += 1
                return

            self._save(transformed)

        except Exception as e:
            self.stats['errors'] += 1
            self.logger.warning(f"Error processing item: {e}")

    def _save(self, data: Dict):
        """Save or update a species record using UPSERT."""
        with Session(self.engine) as session:
            # Use UPSERT to handle duplicates atomically
            species_id, was_inserted = self._upsert_species(session, data)

            if was_inserted:
                self.stats['inserted'] += 1
            else:
                self.stats['updated'] += 1

            # Handle traits if present
            if 'traits' in data:
                self._save_traits(session, species_id, data['traits'])

            # Handle common names if present
            if 'common_names' in data:
                self._save_common_names(session, species_id, data['common_names'])

            session.commit()

    def _upsert_species(self, session: Session, data: Dict) -> tuple:
        """
        Insert or update a species record atomically using UPSERT.

        Returns:
            Tuple of (species_id, was_inserted)
        """
        # Build the field mappings
        fields = ['canonical_name']
        values = {'canonical_name': data['canonical_name']}

        for col in ['genus', 'family', 'taxonomic_status']:
            if data.get(col):
                fields.append(col)
                values[col] = data[col]

        # Add source-specific ID
        id_field, id_value = self._get_source_id_field(data)
        if id_field and id_value:
            fields.append(id_field)
            values[id_field] = id_value

        cols_str = ', '.join(fields)
        vals_str = ', '.join(f':{f}' for f in fields)

        # Build UPDATE clause for conflict (exclude canonical_name from updates)
        update_fields = [f for f in fields if f != 'canonical_name']
        if id_field in update_fields:
            # Only update source ID if it was NULL
            update_clause = ', '.join(
                f"{f} = COALESCE(species.{f}, EXCLUDED.{f})" if f == id_field
                else f"{f} = EXCLUDED.{f}"
                for f in update_fields
            )
        else:
            update_clause = ', '.join(f"{f} = EXCLUDED.{f}" for f in update_fields)

        # Use INSERT ... ON CONFLICT for atomic upsert
        # xmax = 0 means it was inserted, xmax > 0 means it was updated
        result = session.execute(
            text(f"""
                INSERT INTO species ({cols_str})
                VALUES ({vals_str})
                ON CONFLICT (canonical_name) DO UPDATE SET
                    {update_clause},
                    updated_at = NOW()
                RETURNING id, (xmax = 0) as was_inserted
            """),
            values
        ).fetchone()

        return result[0], result[1]

    def _get_source_id_field(self, data: Dict) -> tuple:
        """Get the source-specific ID field and value."""
        if self.name == 'gbif' and data.get('gbif_taxon_key'):
            return 'gbif_taxon_key', data['gbif_taxon_key']
        elif self.name == 'reflora' and data.get('reflora_id'):
            return 'reflora_id', data['reflora_id']
        elif self.name == 'gift' and data.get('gift_work_id'):
            return 'gift_work_id', data['gift_work_id']
        elif self.name == 'wcvp' and data.get('wcvp_id'):
            return 'wcvp_id', data['wcvp_id']
        elif self.name == 'iucn' and data.get('iucn_taxon_id'):
            return 'iucn_taxon_id', data['iucn_taxon_id']
        return None, None

    def _insert_species(self, session: Session, data: Dict) -> int:
        """Insert a new species record (legacy method, use _upsert_species instead)."""
        columns = ['canonical_name', 'genus', 'family', 'taxonomic_status']
        source_cols = [f'{self.name}_id' if self.name != 'gbif' else 'gbif_taxon_key']

        # Build dynamic insert based on available data
        fields = []
        values = {}

        for col in columns:
            if data.get(col):
                fields.append(col)
                values[col] = data[col]

        # Add source-specific ID
        if self.name == 'gbif' and data.get('gbif_taxon_key'):
            fields.append('gbif_taxon_key')
            values['gbif_taxon_key'] = data['gbif_taxon_key']
        elif self.name == 'reflora' and data.get('reflora_id'):
            fields.append('reflora_id')
            values['reflora_id'] = data['reflora_id']
        elif self.name == 'gift' and data.get('gift_work_id'):
            fields.append('gift_work_id')
            values['gift_work_id'] = data['gift_work_id']
        elif self.name == 'wcvp' and data.get('wcvp_id'):
            fields.append('wcvp_id')
            values['wcvp_id'] = data['wcvp_id']
        elif self.name == 'iucn' and data.get('iucn_taxon_id'):
            fields.append('iucn_taxon_id')
            values['iucn_taxon_id'] = data['iucn_taxon_id']

        cols_str = ', '.join(fields)
        vals_str = ', '.join(f':{f}' for f in fields)

        result = session.execute(
            text(f"INSERT INTO species ({cols_str}) VALUES ({vals_str}) RETURNING id"),
            values
        )
        return result.fetchone()[0]

    def _update_species(self, session: Session, species_id: int, data: Dict):
        """Update an existing species record."""
        # Update source-specific ID if not set
        id_field = None
        id_value = None

        if self.name == 'gbif' and data.get('gbif_taxon_key'):
            id_field = 'gbif_taxon_key'
            id_value = data['gbif_taxon_key']
        elif self.name == 'reflora' and data.get('reflora_id'):
            id_field = 'reflora_id'
            id_value = data['reflora_id']
        elif self.name == 'gift' and data.get('gift_work_id'):
            id_field = 'gift_work_id'
            id_value = data['gift_work_id']
        elif self.name == 'wcvp' and data.get('wcvp_id'):
            id_field = 'wcvp_id'
            id_value = data['wcvp_id']
        elif self.name == 'iucn' and data.get('iucn_taxon_id'):
            id_field = 'iucn_taxon_id'
            id_value = data['iucn_taxon_id']

        if id_field and id_value:
            session.execute(
                text(f"UPDATE species SET {id_field} = :val WHERE id = :id AND {id_field} IS NULL"),
                {'val': id_value, 'id': species_id}
            )

    def _save_traits(self, session: Session, species_id: int, traits: Dict):
        """Save species traits."""
        # Check if traits exist for this species from this source
        existing = session.execute(
            text("SELECT id FROM species_traits WHERE species_id = :sid AND source = :src"),
            {'sid': species_id, 'src': self.name}
        ).fetchone()

        if existing:
            # Update existing traits
            updates = []
            values = {'id': existing[0]}

            for key in ['growth_form', 'max_height_m', 'stratum', 'life_form',
                        'woodiness', 'nitrogen_fixer', 'dispersal_syndrome', 'deciduousness',
                        '_gift_trait_1_2_2', '_gift_trait_1_4_2']:
                if traits.get(key) is not None:
                    updates.append(f"{key} = :{key}")
                    values[key] = traits[key]

            if updates:
                session.execute(
                    text(f"UPDATE species_traits SET {', '.join(updates)} WHERE id = :id"),
                    values
                )
        else:
            # Insert new traits
            traits['species_id'] = species_id
            traits['source'] = self.name

            fields = ['species_id', 'source']
            for key in ['growth_form', 'max_height_m', 'stratum', 'life_form',
                        'woodiness', 'nitrogen_fixer', 'dispersal_syndrome', 'deciduousness',
                        '_gift_trait_1_2_2', '_gift_trait_1_4_2']:
                if traits.get(key) is not None:
                    fields.append(key)

            cols_str = ', '.join(fields)
            vals_str = ', '.join(f':{f}' for f in fields)

            session.execute(
                text(f"INSERT INTO species_traits ({cols_str}) VALUES ({vals_str})"),
                {k: traits.get(k) for k in fields}
            )

    def _save_common_names(self, session: Session, species_id: int, names: list):
        """Save common names for a species using savepoints for error isolation."""
        for name_data in names:
            name = name_data.get('name', '')
            if not name:
                continue

            # Truncate very long names (some GBIF names are concatenated lists)
            if len(name) > 500:
                name = name[:500]

            # Use a savepoint so failures don't abort the entire transaction
            savepoint = session.begin_nested()
            try:
                session.execute(
                    text("""
                        INSERT INTO common_names (species_id, common_name, language, source)
                        VALUES (:sid, :name, :lang, :src)
                        ON CONFLICT (species_id, common_name, language) DO NOTHING
                    """),
                    {
                        'sid': species_id,
                        'name': name,
                        'lang': name_data.get('language', 'en'),
                        'src': self.name
                    }
                )
                savepoint.commit()
            except Exception as e:
                savepoint.rollback()
                self.logger.debug(f"Skipped common name (error): {name[:50]}...")

    def _log_start(self):
        """Log crawler start to database."""
        with Session(self.engine) as session:
            # Update status
            session.execute(
                text("""
                    UPDATE crawler_status
                    SET status = 'running', last_run = NOW()
                    WHERE crawler_name = :name
                """),
                {'name': self.name}
            )

            # Create run record
            result = session.execute(
                text("""
                    INSERT INTO crawler_runs (crawler_name, started_at, status)
                    VALUES (:name, NOW(), 'running')
                    RETURNING id
                """),
                {'name': self.name}
            )
            self._run_id = result.fetchone()[0]

            session.commit()

    def _log_success(self):
        """Log successful completion."""
        with Session(self.engine) as session:
            session.execute(
                text("""
                    UPDATE crawler_status
                    SET status = 'completed',
                        last_success = NOW(),
                        records_processed = :processed
                    WHERE crawler_name = :name
                """),
                {'name': self.name, 'processed': self.stats['processed']}
            )

            if self._run_id:
                session.execute(
                    text("""
                        UPDATE crawler_runs
                        SET completed_at = NOW(),
                            status = 'completed',
                            records_processed = :processed,
                            records_inserted = :inserted,
                            records_updated = :updated
                        WHERE id = :id
                    """),
                    {
                        'id': self._run_id,
                        'processed': self.stats['processed'],
                        'inserted': self.stats['inserted'],
                        'updated': self.stats['updated']
                    }
                )

            session.commit()

    def _log_error(self, message: str):
        """Log error to database."""
        with Session(self.engine) as session:
            session.execute(
                text("""
                    UPDATE crawler_status
                    SET status = 'failed',
                        error_count = error_count + 1
                    WHERE crawler_name = :name
                """),
                {'name': self.name}
            )

            if self._run_id:
                session.execute(
                    text("""
                        UPDATE crawler_runs
                        SET completed_at = NOW(),
                            status = 'failed',
                            error_message = :msg
                        WHERE id = :id
                    """),
                    {'id': self._run_id, 'msg': message}
                )

            self._log_message('ERROR', message)
            session.commit()

    def _log_message(self, level: str, message: str, details: dict = None):
        """Log a message to the crawler_logs table."""
        import json
        with Session(self.engine) as session:
            session.execute(
                text("""
                    INSERT INTO crawler_logs (crawler_name, level, message, details)
                    VALUES (:name, :level, :msg, :details)
                """),
                {
                    'name': self.name,
                    'level': level,
                    'msg': message,
                    'details': json.dumps(details) if details else None
                }
            )
            session.commit()

    def refresh_unified_tables(self, species_ids: list = None):
        """
        Refresh unified tables (species_unified, species_regions, species_geometry).

        This method updates the denormalized unified tables after crawler runs.
        Should be called after bulk data imports or when unified tables need sync.

        Args:
            species_ids: Optional list of species IDs to refresh. If None, refreshes all.
        """
        self.logger.info("Refreshing unified tables...")

        with Session(self.engine) as session:
            # Check if unified tables exist
            tables_exist = session.execute(text("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_name IN ('species_unified', 'species_regions', 'species_geometry')
            """)).scalar()

            if tables_exist < 3:
                self.logger.warning("Unified tables not found. Run migrations first.")
                return

            # Refresh species_unified for affected species
            self._refresh_species_unified(session, species_ids)

            # Refresh species_regions from wcvp_distribution
            self._refresh_species_regions(session, species_ids)

            session.commit()

        self.logger.info("Unified tables refresh complete")

    def _refresh_species_unified(self, session: Session, species_ids: list = None):
        """Refresh species_unified table with consolidated traits."""
        self.logger.info("Refreshing species_unified...")

        where_clause = ""
        params = {}
        if species_ids:
            where_clause = "WHERE s.id = ANY(:ids)"
            params['ids'] = species_ids

        # Upsert species_unified with priority: gift > reflora > wcvp > treegoer
        # GIFT is prioritized for using more consistent definitions (liana vs vine)
        # and following Renata's Climber.R logic (trait_1.2.2 + trait_1.4.2)
        session.execute(text(f"""
            INSERT INTO species_unified (
                species_id,
                growth_form,
                growth_form_source,
                max_height_m,
                height_source,
                woodiness,
                nitrogen_fixer,
                dispersal_syndrome,
                deciduousness,
                is_native_brazil,
                sources_count
            )
            SELECT
                s.id,
                COALESCE(
                    (SELECT growth_form FROM species_traits WHERE species_id = s.id AND source = 'gift' AND growth_form IS NOT NULL LIMIT 1),
                    (SELECT growth_form FROM species_traits WHERE species_id = s.id AND source = 'reflora' AND growth_form IS NOT NULL LIMIT 1),
                    (SELECT growth_form FROM species_traits WHERE species_id = s.id AND source = 'wcvp' AND growth_form IS NOT NULL LIMIT 1),
                    (SELECT growth_form FROM species_traits WHERE species_id = s.id AND source = 'treegoer' AND growth_form IS NOT NULL LIMIT 1)
                ),
                CASE
                    WHEN EXISTS(SELECT 1 FROM species_traits WHERE species_id = s.id AND source = 'gift' AND growth_form IS NOT NULL) THEN 'gift'
                    WHEN EXISTS(SELECT 1 FROM species_traits WHERE species_id = s.id AND source = 'reflora' AND growth_form IS NOT NULL) THEN 'reflora'
                    WHEN EXISTS(SELECT 1 FROM species_traits WHERE species_id = s.id AND source = 'wcvp' AND growth_form IS NOT NULL) THEN 'wcvp'
                    WHEN EXISTS(SELECT 1 FROM species_traits WHERE species_id = s.id AND source = 'treegoer' AND growth_form IS NOT NULL) THEN 'treegoer'
                END,
                (SELECT max_height_m FROM species_traits WHERE species_id = s.id AND max_height_m IS NOT NULL ORDER BY
                    CASE source WHEN 'gift' THEN 1 WHEN 'reflora' THEN 2 WHEN 'wcvp' THEN 3 WHEN 'treegoer' THEN 4 ELSE 5 END
                LIMIT 1),
                (SELECT source FROM species_traits WHERE species_id = s.id AND max_height_m IS NOT NULL ORDER BY
                    CASE source WHEN 'gift' THEN 1 WHEN 'reflora' THEN 2 WHEN 'wcvp' THEN 3 WHEN 'treegoer' THEN 4 ELSE 5 END
                LIMIT 1),
                (SELECT woodiness FROM species_traits WHERE species_id = s.id AND woodiness IS NOT NULL LIMIT 1),
                (SELECT nitrogen_fixer FROM species_traits WHERE species_id = s.id AND nitrogen_fixer IS NOT NULL LIMIT 1),
                (SELECT dispersal_syndrome FROM species_traits WHERE species_id = s.id AND dispersal_syndrome IS NOT NULL LIMIT 1),
                (SELECT deciduousness FROM species_traits WHERE species_id = s.id AND deciduousness IS NOT NULL LIMIT 1),
                EXISTS(
                    SELECT 1 FROM species_regions sr
                    WHERE sr.species_id = s.id AND sr.tdwg_code LIKE 'BZ%' AND sr.is_native = TRUE
                ),
                (SELECT COUNT(DISTINCT source) FROM species_traits WHERE species_id = s.id)
            FROM species s
            {where_clause}
            AND EXISTS (SELECT 1 FROM species_traits WHERE species_id = s.id)
            ON CONFLICT (species_id) DO UPDATE SET
                growth_form = EXCLUDED.growth_form,
                growth_form_source = EXCLUDED.growth_form_source,
                max_height_m = EXCLUDED.max_height_m,
                height_source = EXCLUDED.height_source,
                woodiness = EXCLUDED.woodiness,
                nitrogen_fixer = EXCLUDED.nitrogen_fixer,
                dispersal_syndrome = EXCLUDED.dispersal_syndrome,
                deciduousness = EXCLUDED.deciduousness,
                is_native_brazil = EXCLUDED.is_native_brazil,
                sources_count = EXCLUDED.sources_count,
                last_updated = CURRENT_TIMESTAMP
        """), params)

        count = session.execute(text("SELECT COUNT(*) FROM species_unified")).scalar()
        self.logger.info(f"species_unified: {count} records")

    def _refresh_species_regions(self, session: Session, species_ids: list = None):
        """Refresh species_regions from wcvp_distribution."""
        self.logger.info("Refreshing species_regions...")

        # Check if wcvp_distribution exists and has data
        wcvp_exists = session.execute(text("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'wcvp_distribution'
            )
        """)).scalar()

        if not wcvp_exists:
            self.logger.warning("wcvp_distribution table not found")
            return

        where_clause = ""
        params = {}
        if species_ids:
            where_clause = "AND s.id = ANY(:ids)"
            params['ids'] = species_ids

        # Insert from wcvp_distribution
        session.execute(text(f"""
            INSERT INTO species_regions (species_id, tdwg_code, is_native, is_endemic, is_introduced, source)
            SELECT DISTINCT
                s.id,
                wd.tdwg_code,
                CASE
                    WHEN wd.establishment_means = 'native' THEN TRUE
                    WHEN wd.establishment_means IS NULL THEN TRUE
                    ELSE FALSE
                END,
                CASE WHEN wd.endemic = '1' THEN TRUE ELSE FALSE END,
                CASE WHEN wd.introduced = '1' THEN TRUE ELSE FALSE END,
                'wcvp'
            FROM species s
            JOIN wcvp_distribution wd ON s.wcvp_id = wd.taxon_id
            WHERE wd.tdwg_code IS NOT NULL
              AND LENGTH(TRIM(wd.tdwg_code)) > 0
              {where_clause}
            ON CONFLICT (species_id, tdwg_code) DO UPDATE SET
                is_native = EXCLUDED.is_native,
                is_endemic = EXCLUDED.is_endemic,
                is_introduced = EXCLUDED.is_introduced,
                source = EXCLUDED.source
        """), params)

        count = session.execute(text("SELECT COUNT(*) FROM species_regions")).scalar()
        self.logger.info(f"species_regions: {count} records")
