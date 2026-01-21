"""Practitioners database crawler for Brazilian threatened species.

Data source: Practitioners dataset (compiled by Brazilian botanists)
File: data/practitioners.csv
Coverage: ~3,600 Brazilian species with threat status and habitat data

This dataset focuses on Brazilian endemic and native species with conservation
status information following IUCN categories.
"""
from typing import Generator, Dict, Any, Optional
import pandas as pd
import os
import re
from .base import BaseCrawler
from sqlalchemy import text
from sqlalchemy.orm import Session


class PractitionersCrawler(BaseCrawler):
    """
    Crawler for Practitioners database (Brazilian endangered species).

    Source: Pre-compiled CSV from Brazilian botanists
    Coverage: ~3,600 species with threat status
    Data: growth_form, threat_status (IUCN), establishment, habitat
    """

    name = 'practitioners'

    # Path to practitioners data
    DATA_FILE = 'data/practitioners.csv'

    # Mapping from Portuguese threat status to IUCN codes
    THREAT_STATUS_MAP = {
        'criticamente em perigo (cr)': 'CR',
        'em perigo (en)': 'EN',
        'vulnerável (vu)': 'VU',
        'vulneravel (vu)': 'VU',
        'quase ameaçada (nt)': 'NT',
        'quase ameacada (nt)': 'NT',
        'menos preocupante (lc)': 'LC',
        'dados insuficientes (dd)': 'DD',
        'extinta (ex)': 'EX',
        'extinta na natureza (ew)': 'EW',
    }

    # Mapping for growth_form standardization
    GROWTH_FORM_MAP = {
        'tree': 'tree',
        'shrub': 'shrub',
        'subshrub': 'subshrub',
        'herb': 'herb',
        'forb': 'forb',
        'vine': 'vine',
        'liana': 'liana',
        'climber': 'climber',
        'palm': 'palm',
        'bamboo': 'bamboo',
        'fern': 'fern',
        'epiphyte': 'epiphyte',
        'succulent': 'succulent',
        'aquatic': 'aquatic',
        'grass': 'grass',
    }

    def __init__(self, db_url: str):
        super().__init__(db_url)
        self._df: Optional[pd.DataFrame] = None

    def fetch_data(self, mode='incremental', **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        Fetch species data from practitioners CSV.

        Args:
            mode: 'full' or 'incremental'
            **kwargs: Additional parameters (max_records)

        Yields:
            Species records with threat status and habitat data
        """
        max_records = kwargs.get('max_records', None)

        # Load data file
        data_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            self.DATA_FILE
        )

        if not os.path.exists(data_path):
            self.logger.error(f"Practitioners data file not found: {data_path}")
            return

        self.logger.info(f"Loading practitioners data from {data_path}")

        try:
            # CSV with BOM (UTF-8-BOM)
            self._df = pd.read_csv(
                data_path,
                encoding='utf-8-sig',  # Handle BOM
                low_memory=False
            )

            self.logger.info(f"Loaded {len(self._df)} records")

            count = 0
            for _, row in self._df.iterrows():
                species_name = row.get('sci_names', '')

                # Skip rows without species name
                if pd.isna(species_name) or not species_name.strip():
                    continue

                yield row.to_dict()

                count += 1
                if count % 1000 == 0:
                    self.logger.info(f"Progress: {count} species processed")

                if max_records and count >= max_records:
                    break

        except Exception as e:
            self.logger.error(f"Error loading practitioners data: {e}")
            raise

    def transform(self, raw_data: Dict) -> Dict:
        """
        Transform practitioners data to internal schema.

        Args:
            raw_data: Raw CSV row as dictionary

        Returns:
            Transformed data matching database schema
        """
        species_name = raw_data.get('sci_names', '')
        canonical = self._clean_species_name(species_name)

        if not canonical:
            return {}

        transformed = {
            'canonical_name': canonical,
            'family': raw_data.get('family') if pd.notna(raw_data.get('family')) else None,
        }

        # Build traits
        traits = {}

        # Growth form - use primary (growth_form) or secondary (growth_form2)
        growth_form = raw_data.get('growth_form')
        if not growth_form or pd.isna(growth_form):
            growth_form = raw_data.get('growth_form2')

        if growth_form and pd.notna(growth_form):
            normalized_gf = self._normalize_growth_form(growth_form)
            if normalized_gf:
                traits['growth_form'] = normalized_gf

        # Threat status - normalize to IUCN code
        threat_status = raw_data.get('threat_status')
        if threat_status and pd.notna(threat_status):
            iucn_code = self._normalize_threat_status(threat_status)
            if iucn_code:
                traits['threat_status'] = iucn_code

        # Establishment type
        establishment = raw_data.get('establishment')
        if establishment and pd.notna(establishment) and isinstance(establishment, str):
            traits['establishment'] = establishment.strip().lower()

        # Habitat
        habitat = raw_data.get('habitat')
        if habitat and pd.notna(habitat) and isinstance(habitat, str):
            traits['habitat'] = habitat.strip()

        # Max height
        max_height = raw_data.get('plant_max_height')
        if max_height and pd.notna(max_height):
            try:
                traits['max_height_m'] = float(max_height)
            except (ValueError, TypeError):
                pass

        # Stratum
        stratum = raw_data.get('stratum')
        if stratum and pd.notna(stratum) and isinstance(stratum, str):
            traits['stratum'] = stratum.strip()

        if traits:
            transformed['traits'] = traits

        # Common names
        common_names = []

        common_pt = raw_data.get('common_pt')
        if common_pt and pd.notna(common_pt) and isinstance(common_pt, str):
            common_names.append({'name': common_pt.strip(), 'language': 'pt'})

        common_en = raw_data.get('common_en')
        if common_en and pd.notna(common_en) and isinstance(common_en, str):
            common_names.append({'name': common_en.strip(), 'language': 'en'})

        if common_names:
            transformed['common_names'] = common_names

        return transformed

    def _clean_species_name(self, name: str) -> str:
        """Extract binomial name from full scientific name."""
        if not name or pd.isna(name):
            return ''

        name = str(name).strip()

        # Keep only first two words (genus + species)
        parts = name.split()
        if len(parts) >= 2:
            return f"{parts[0]} {parts[1]}"
        return name

    def _normalize_threat_status(self, status: str) -> Optional[str]:
        """
        Normalize threat status to IUCN code.

        Args:
            status: Portuguese or English threat status

        Returns:
            IUCN code (CR, EN, VU, NT, LC, DD, EX, EW) or None
        """
        if not status:
            return None

        status_lower = status.lower().strip()

        # Check mapped values
        if status_lower in self.THREAT_STATUS_MAP:
            return self.THREAT_STATUS_MAP[status_lower]

        # Try to extract code from parentheses: "Em Perigo (EN)" -> "EN"
        match = re.search(r'\(([A-Z]{2})\)', status)
        if match:
            code = match.group(1)
            if code in ('CR', 'EN', 'VU', 'NT', 'LC', 'DD', 'EX', 'EW'):
                return code

        # If already a valid code
        status_upper = status.upper().strip()
        if status_upper in ('CR', 'EN', 'VU', 'NT', 'LC', 'DD', 'EX', 'EW'):
            return status_upper

        return None

    def _normalize_growth_form(self, growth_form: str) -> Optional[str]:
        """Normalize growth form to standard values."""
        if not growth_form:
            return None

        gf_lower = growth_form.lower().strip()

        if gf_lower in self.GROWTH_FORM_MAP:
            return self.GROWTH_FORM_MAP[gf_lower]

        return gf_lower if gf_lower else None

    def _save(self, data: Dict):
        """
        Save practitioners data.

        For existing species: update traits
        For new species: create species + traits
        """
        canonical_name = data['canonical_name']

        with Session(self.engine) as session:
            # Check if species exists
            result = session.execute(
                text("SELECT id FROM species WHERE canonical_name = :name"),
                {'name': canonical_name}
            ).fetchone()

            if result:
                species_id = result[0]
                self.stats['updated'] += 1
            else:
                # Insert new species
                result = session.execute(
                    text("""
                        INSERT INTO species (canonical_name, family)
                        VALUES (:name, :family)
                        RETURNING id
                    """),
                    {'name': canonical_name, 'family': data.get('family')}
                )
                species_id = result.fetchone()[0]
                self.stats['inserted'] += 1

            # Save traits
            if 'traits' in data:
                self._save_traits_practitioners(session, species_id, data['traits'])

            # Save common names
            if 'common_names' in data:
                self._save_common_names(session, species_id, data['common_names'])

            session.commit()

    def _save_traits_practitioners(self, session: Session, species_id: int, traits: Dict):
        """Save practitioner-specific traits including threat_status."""
        # Check if traits exist for this source
        existing = session.execute(
            text("SELECT id FROM species_traits WHERE species_id = :sid AND source = :src"),
            {'sid': species_id, 'src': self.name}
        ).fetchone()

        if existing:
            # Build update query
            updates = []
            values = {'id': existing[0]}

            for key in ['growth_form', 'max_height_m', 'stratum', 'threat_status',
                        'establishment', 'habitat']:
                if traits.get(key) is not None:
                    updates.append(f"{key} = :{key}")
                    values[key] = traits[key]

            if updates:
                session.execute(
                    text(f"UPDATE species_traits SET {', '.join(updates)} WHERE id = :id"),
                    values
                )
        else:
            # Insert new traits record
            fields = ['species_id', 'source']
            values = {'species_id': species_id, 'source': self.name}

            for key in ['growth_form', 'max_height_m', 'stratum', 'threat_status',
                        'establishment', 'habitat']:
                if traits.get(key) is not None:
                    fields.append(key)
                    values[key] = traits[key]

            cols_str = ', '.join(fields)
            vals_str = ', '.join(f':{f}' for f in fields)

            session.execute(
                text(f"INSERT INTO species_traits ({cols_str}) VALUES ({vals_str})"),
                values
            )

    def get_threat_stats(self) -> Dict:
        """Get statistics about threat status coverage."""
        with Session(self.engine) as session:
            # Count by threat status
            result = session.execute(text("""
                SELECT threat_status, COUNT(*) as count
                FROM species_traits
                WHERE source = 'practitioners' AND threat_status IS NOT NULL
                GROUP BY threat_status
                ORDER BY count DESC
            """)).fetchall()

            return {
                'by_status': {row[0]: row[1] for row in result},
                'total_threatened': sum(
                    row[1] for row in result
                    if row[0] in ('CR', 'EN', 'VU')
                )
            }

    def get_establishment_stats(self) -> Dict:
        """Get statistics about establishment type coverage."""
        with Session(self.engine) as session:
            result = session.execute(text("""
                SELECT establishment, COUNT(*) as count
                FROM species_traits
                WHERE source = 'practitioners' AND establishment IS NOT NULL
                GROUP BY establishment
                ORDER BY count DESC
            """)).fetchall()

            return {row[0]: row[1] for row in result}
