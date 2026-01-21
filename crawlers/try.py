"""TRY Plant Trait Database crawler for lifespan data.

Data source: TRY Plant Trait Database
File: data/TRY_lifespan_numeric_processed.txt (pre-processed TSV)
Trait: Plant lifespan (longevity) numeric (TraitID 59)

Note: TRY data is pre-processed locally. For raw data access, see https://www.try-db.org/
"""
from typing import Generator, Dict, Any, Optional
import pandas as pd
import os
from .base import BaseCrawler
from sqlalchemy import text
from sqlalchemy.orm import Session


class TRYCrawler(BaseCrawler):
    """
    Crawler for TRY Plant Trait Database (lifespan data).

    Source: Pre-processed TRY export (TSV format)
    Coverage: ~4,400 unique species with lifespan data
    Data: Lifespan in years (numeric, uses mean when multiple values)
    """

    name = 'try'

    # Path to pre-processed TRY data
    DATA_FILE = 'data/TRY_lifespan_numeric_processed.txt'

    def __init__(self, db_url: str):
        super().__init__(db_url)
        self._df: Optional[pd.DataFrame] = None

    def fetch_data(self, mode='incremental', **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        Fetch lifespan data from pre-processed TRY export.

        Args:
            mode: 'full' or 'incremental'
            **kwargs: Additional parameters

        Yields:
            Species lifespan records
        """
        max_records = kwargs.get('max_records', None)

        # Load data file
        data_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            self.DATA_FILE
        )

        if not os.path.exists(data_path):
            self.logger.error(f"TRY data file not found: {data_path}")
            return

        self.logger.info(f"Loading TRY data from {data_path}")

        try:
            # TRY exports use tab-separated format with quoted fields
            self._df = pd.read_csv(
                data_path,
                sep='\t',
                low_memory=False,
                quotechar='"'
            )

            self.logger.info(f"Loaded {len(self._df)} raw records")

            # Key columns we need:
            # - AccSpeciesName: Accepted species name
            # - StdValue: Standardized lifespan value in years
            # - CleanedValueStr: Cleaned numeric value

            if 'AccSpeciesName' not in self._df.columns:
                self.logger.error("Column 'AccSpeciesName' not found in TRY data")
                return

            # Aggregate by species - use mean of StdValue for species with multiple records
            lifespan_df = self._df.groupby('AccSpeciesName').agg({
                'StdValue': 'mean',  # Mean lifespan
                'AccSpeciesID': 'first',  # Keep first TRY species ID
                'DatasetID': lambda x: list(x.unique())[:5],  # List of source datasets
            }).reset_index()

            self.logger.info(f"Aggregated to {len(lifespan_df)} unique species")

            count = 0
            for _, row in lifespan_df.iterrows():
                species_name = row['AccSpeciesName']
                lifespan_years = row['StdValue']

                # Skip invalid records
                if pd.isna(species_name) or pd.isna(lifespan_years):
                    continue

                # Skip unreasonably high values (likely errors)
                if lifespan_years > 5000:
                    self.logger.warning(f"Skipping unrealistic lifespan: {species_name} = {lifespan_years} years")
                    continue

                yield {
                    'AccSpeciesName': species_name,
                    'StdValue': float(lifespan_years),
                    'AccSpeciesID': row.get('AccSpeciesID'),
                    'DatasetIDs': row.get('DatasetID', [])
                }

                count += 1
                if count % 1000 == 0:
                    self.logger.info(f"Progress: {count} species processed")

                if max_records and count >= max_records:
                    break

        except Exception as e:
            self.logger.error(f"Error loading TRY data: {e}")
            raise

    def transform(self, raw_data: Dict) -> Dict:
        """
        Transform TRY data to internal schema.

        Note: TRY crawler doesn't create new species, only updates traits.

        Args:
            raw_data: Raw TRY record

        Returns:
            Transformed data with canonical_name and traits
        """
        species_name = raw_data.get('AccSpeciesName', '')

        # Clean species name - keep only binomial
        canonical = self._clean_species_name(species_name)
        if not canonical:
            return {}

        return {
            'canonical_name': canonical,
            'traits': {
                'lifespan_years': raw_data.get('StdValue')
            }
        }

    def _clean_species_name(self, name: str) -> str:
        """Extract binomial name from full scientific name."""
        if not name:
            return ''

        # Keep only first two words (genus + species)
        parts = name.strip().split()
        if len(parts) >= 2:
            return f"{parts[0]} {parts[1]}"
        return name.strip()

    def validate(self, data: Dict) -> bool:
        """Validate TRY data before saving."""
        if not data.get('canonical_name'):
            return False

        traits = data.get('traits', {})
        lifespan = traits.get('lifespan_years')

        # Must have valid lifespan value
        if lifespan is None:
            return False

        # Reasonable range: 1-5000 years
        if lifespan < 1 or lifespan > 5000:
            return False

        return True

    def _save(self, data: Dict):
        """
        Save TRY data - only updates existing species.

        TRY is a trait-only source, so we don't create new species.
        We only update lifespan_years for species that already exist.
        """
        canonical_name = data['canonical_name']
        lifespan_years = data['traits']['lifespan_years']

        with Session(self.engine) as session:
            # Find existing species
            result = session.execute(
                text("SELECT id FROM species WHERE canonical_name = :name"),
                {'name': canonical_name}
            ).fetchone()

            if not result:
                self.stats['skipped'] += 1
                return

            species_id = result[0]

            # Check if traits exist for this source
            existing = session.execute(
                text("SELECT id FROM species_traits WHERE species_id = :sid AND source = :src"),
                {'sid': species_id, 'src': self.name}
            ).fetchone()

            if existing:
                # Update existing record
                session.execute(
                    text("""
                        UPDATE species_traits
                        SET lifespan_years = :lifespan
                        WHERE id = :id
                    """),
                    {'id': existing[0], 'lifespan': lifespan_years}
                )
                self.stats['updated'] += 1
            else:
                # Insert new traits record
                session.execute(
                    text("""
                        INSERT INTO species_traits (species_id, source, lifespan_years)
                        VALUES (:sid, :src, :lifespan)
                    """),
                    {'sid': species_id, 'src': self.name, 'lifespan': lifespan_years}
                )
                self.stats['inserted'] += 1

            session.commit()

    def get_lifespan_stats(self) -> Dict:
        """Get statistics about lifespan data coverage."""
        with Session(self.engine) as session:
            result = session.execute(text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(lifespan_years) as with_lifespan,
                    ROUND(AVG(lifespan_years)::numeric, 1) as avg_lifespan,
                    ROUND(MIN(lifespan_years)::numeric, 1) as min_lifespan,
                    ROUND(MAX(lifespan_years)::numeric, 1) as max_lifespan
                FROM species_traits
                WHERE source = 'try'
            """)).fetchone()

            return {
                'total_records': result[0],
                'with_lifespan': result[1],
                'avg_lifespan_years': result[2],
                'min_lifespan_years': result[3],
                'max_lifespan_years': result[4]
            }
