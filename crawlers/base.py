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
        """Save or update a species record."""
        with Session(self.engine) as session:
            # Check if species exists
            result = session.execute(
                text("SELECT id FROM species WHERE canonical_name = :name"),
                {'name': data['canonical_name']}
            ).fetchone()

            if result:
                # Update existing
                species_id = result[0]
                self._update_species(session, species_id, data)
                self.stats['updated'] += 1
            else:
                # Insert new
                species_id = self._insert_species(session, data)
                self.stats['inserted'] += 1

            # Handle traits if present
            if 'traits' in data:
                self._save_traits(session, species_id, data['traits'])

            # Handle common names if present
            if 'common_names' in data:
                self._save_common_names(session, species_id, data['common_names'])

            session.commit()

    def _insert_species(self, session: Session, data: Dict) -> int:
        """Insert a new species record."""
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
                        'woodiness', 'nitrogen_fixer', 'dispersal_syndrome', 'deciduousness']:
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
                        'woodiness', 'nitrogen_fixer', 'dispersal_syndrome', 'deciduousness']:
                if traits.get(key) is not None:
                    fields.append(key)

            cols_str = ', '.join(fields)
            vals_str = ', '.join(f':{f}' for f in fields)

            session.execute(
                text(f"INSERT INTO species_traits ({cols_str}) VALUES ({vals_str})"),
                {k: traits.get(k) for k in fields}
            )

    def _save_common_names(self, session: Session, species_id: int, names: list):
        """Save common names for a species."""
        for name_data in names:
            try:
                session.execute(
                    text("""
                        INSERT INTO common_names (species_id, common_name, language, source)
                        VALUES (:sid, :name, :lang, :src)
                        ON CONFLICT (species_id, common_name, language) DO NOTHING
                    """),
                    {
                        'sid': species_id,
                        'name': name_data['name'],
                        'lang': name_data.get('language', 'en'),
                        'src': self.name
                    }
                )
            except Exception as e:
                self.logger.warning(f"Error saving common name: {e}")

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
