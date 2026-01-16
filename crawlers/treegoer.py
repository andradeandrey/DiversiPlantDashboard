"""TreeGOER (Global Observation-based Ecoregion Tree Database) crawler."""
from typing import Generator, Dict, Any, List, Optional
import requests
import pandas as pd
import io
import os
import tempfile
from .base import BaseCrawler


class TreeGOERCrawler(BaseCrawler):
    """
    Crawler for TreeGOER database.

    Coverage: >80% of tree species with ecoregion associations
    Data: Species-ecoregion relationships based on GBIF occurrences
    Use: Validate tree species selection for specific ecoregions
    """

    name = 'treegoer'

    # TreeGOER data URL (from figshare or Zenodo)
    DATA_URL = 'https://figshare.com/ndownloader/files/treegoer_data.csv'

    def __init__(self, db_url: str):
        super().__init__(db_url)
        self._cache_path = os.path.join(tempfile.gettempdir(), 'treegoer_cache.csv')
        self._data: Optional[pd.DataFrame] = None

    def fetch_data(self, mode='incremental', **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        Fetch TreeGOER species-ecoregion data.

        Args:
            mode: 'full' or 'incremental'
            **kwargs: Additional parameters (ecoregion, max_records)

        Yields:
            Species-ecoregion association records
        """
        data_path = kwargs.get('data_path', None)
        ecoregion_filter = kwargs.get('ecoregion', None)
        max_records = kwargs.get('max_records', None)

        # Load data
        df = self._load_data(data_path)
        if df is None or df.empty:
            self.logger.error("No TreeGOER data available")
            return

        self.logger.info(f"Processing {len(df)} TreeGOER records")

        # Apply filters
        if ecoregion_filter:
            df = df[df['eco_id'] == ecoregion_filter]

        count = 0
        for _, row in df.iterrows():
            yield row.to_dict()
            count += 1

            if max_records and count >= max_records:
                break

    def _load_data(self, data_path: str = None) -> Optional[pd.DataFrame]:
        """Load TreeGOER data from file or download."""
        if self._data is not None:
            return self._data

        # Try local file first
        if data_path and os.path.exists(data_path):
            self.logger.info(f"Loading TreeGOER from: {data_path}")
            self._data = pd.read_csv(data_path)
            return self._data

        # Try cache
        if os.path.exists(self._cache_path):
            self.logger.info("Loading TreeGOER from cache")
            self._data = pd.read_csv(self._cache_path)
            return self._data

        # Download
        self.logger.info("Downloading TreeGOER data...")
        try:
            response = requests.get(self.DATA_URL, timeout=300)
            response.raise_for_status()

            self._data = pd.read_csv(io.StringIO(response.text))

            # Cache for future use
            self._data.to_csv(self._cache_path, index=False)

            return self._data

        except Exception as e:
            self.logger.error(f"Error downloading TreeGOER: {e}")
            return None

    def transform(self, raw_data: Dict) -> Dict:
        """
        Transform TreeGOER data to internal schema.

        Args:
            raw_data: Raw species-ecoregion record

        Returns:
            Transformed data
        """
        species_name = raw_data.get('species', '') or raw_data.get('canonical_name', '')

        if not species_name:
            return {}

        transformed = {
            'canonical_name': self._clean_species_name(species_name),
            'taxonomic_status': 'accepted',
            'traits': {
                'growth_form': 'tree',  # TreeGOER is trees only
            }
        }

        # Extract genus
        parts = transformed['canonical_name'].split()
        if parts:
            transformed['genus'] = parts[0]

        # Store ecoregion association for validation
        if raw_data.get('eco_id'):
            transformed['_ecoregion'] = {
                'eco_id': raw_data.get('eco_id'),
                'eco_name': raw_data.get('eco_name'),
                'occurrence_count': raw_data.get('n_occurrences', 0),
                'confirmed': raw_data.get('confirmed', False)
            }

        return transformed

    def _clean_species_name(self, name: str) -> str:
        """Clean species name."""
        if not name:
            return ''

        parts = name.strip().split()
        if len(parts) >= 2:
            return f"{parts[0]} {parts[1]}"
        return name.strip()

    def get_species_for_ecoregion(self, eco_id: int) -> List[str]:
        """
        Get all tree species confirmed for an ecoregion.

        Args:
            eco_id: RESOLVE ecoregion ID

        Returns:
            List of species canonical names
        """
        df = self._load_data()
        if df is None:
            return []

        filtered = df[df['eco_id'] == eco_id]
        return filtered['species'].unique().tolist()

    def validate_species_in_ecoregion(self, species_name: str, eco_id: int) -> bool:
        """
        Check if a tree species is confirmed for an ecoregion.

        Args:
            species_name: Species canonical name
            eco_id: RESOLVE ecoregion ID

        Returns:
            True if species is confirmed in ecoregion
        """
        df = self._load_data()
        if df is None:
            return False

        # Clean species name for matching
        species_clean = self._clean_species_name(species_name).lower()

        match = df[
            (df['eco_id'] == eco_id) &
            (df['species'].str.lower() == species_clean)
        ]

        return not match.empty

    def get_ecoregions_for_species(self, species_name: str) -> List[Dict]:
        """
        Get all ecoregions where a species occurs.

        Args:
            species_name: Species canonical name

        Returns:
            List of ecoregion info dicts
        """
        df = self._load_data()
        if df is None:
            return []

        species_clean = self._clean_species_name(species_name).lower()

        matches = df[df['species'].str.lower() == species_clean]

        return matches[['eco_id', 'eco_name', 'n_occurrences']].to_dict('records')

    def get_coverage_stats(self) -> Dict:
        """Get TreeGOER coverage statistics."""
        df = self._load_data()
        if df is None:
            return {}

        return {
            'total_records': len(df),
            'unique_species': df['species'].nunique(),
            'unique_ecoregions': df['eco_id'].nunique(),
        }
