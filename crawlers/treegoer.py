"""TreeGOER / EcoregionsTreeFinder crawler.

Data source: EcoregionsTreeFinder - A Global Dataset Documenting the Abundance
of Observations of > 45,000 Tree Species in 828 Terrestrial Ecoregions.

Reference: Kindt (2024) DOI: 10.1111/geb.70064
Zenodo: https://doi.org/10.5281/zenodo.13166796
"""
from typing import Generator, Dict, Any, List, Optional
import requests
import pandas as pd
import io
import os
import tempfile
from .base import BaseCrawler


class TreeGOERCrawler(BaseCrawler):
    """
    Crawler for EcoregionsTreeFinder database (TreeGOER-derived).

    Coverage: 48,129 tree species across 828 RESOLVE Ecoregions
    Data: Species-ecoregion relationships with observation counts
    Use: Validate tree species selection for specific ecoregions
    """

    name = 'treegoer'

    # EcoregionsTreeFinder data URLs (Zenodo)
    DATA_URL = 'https://zenodo.org/records/13166796/files/EcoregionsTreeFinder.txt?download=1'
    SPECIES_URL = 'https://zenodo.org/records/13166796/files/EcoregionsTreeFinder_species.txt?download=1'
    ECOREGIONS_URL = 'https://zenodo.org/records/13166796/files/EcoregionsTreeFinder_ecoregions.txt?download=1'

    def __init__(self, db_url: str):
        super().__init__(db_url)
        self._cache_dir = os.path.join(tempfile.gettempdir(), 'ecoregions_treefinder')
        self._data: Optional[pd.DataFrame] = None
        self._species_data: Optional[pd.DataFrame] = None

    def fetch_data(self, mode='incremental', **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        Fetch EcoregionsTreeFinder species-ecoregion data.

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
            self.logger.error("No EcoregionsTreeFinder data available")
            return

        # Get unique species (we only need species data, not per-ecoregion)
        # Group by species to get aggregated stats
        species_df = df.groupby('species').agg({
            'ECO_ID': 'count',  # Number of ecoregions
            'n': 'sum',         # Total observations
        }).reset_index()
        species_df.columns = ['species', 'n_ecoregions', 'total_observations']

        self.logger.info(f"Processing {len(species_df)} unique tree species")

        count = 0
        for _, row in species_df.iterrows():
            yield row.to_dict()
            count += 1

            if count % 10000 == 0:
                self.logger.info(f"Progress: {count} species processed")

            if max_records and count >= max_records:
                break

    def _load_data(self, data_path: str = None) -> Optional[pd.DataFrame]:
        """Load EcoregionsTreeFinder data from file or download."""
        if self._data is not None:
            return self._data

        os.makedirs(self._cache_dir, exist_ok=True)
        cache_file = os.path.join(self._cache_dir, 'EcoregionsTreeFinder.txt')

        # Try local file first
        if data_path and os.path.exists(data_path):
            self.logger.info(f"Loading EcoregionsTreeFinder from: {data_path}")
            self._data = pd.read_csv(data_path, sep='|')
            return self._data

        # Try cache
        if os.path.exists(cache_file):
            self.logger.info("Loading EcoregionsTreeFinder from cache")
            self._data = pd.read_csv(cache_file, sep='|')
            return self._data

        # Download
        self.logger.info("Downloading EcoregionsTreeFinder data (49MB)...")
        try:
            response = requests.get(self.DATA_URL, timeout=600, stream=True)
            response.raise_for_status()

            # Save to cache
            with open(cache_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            self.logger.info("Download complete, loading data...")
            self._data = pd.read_csv(cache_file, sep='|')

            return self._data

        except Exception as e:
            self.logger.error(f"Error downloading EcoregionsTreeFinder: {e}")
            return None

    def transform(self, raw_data: Dict) -> Dict:
        """
        Transform EcoregionsTreeFinder data to internal schema.

        Args:
            raw_data: Raw species record with aggregated stats

        Returns:
            Transformed data
        """
        species_name = raw_data.get('species', '')

        if not species_name:
            return {}

        transformed = {
            'canonical_name': self._clean_species_name(species_name),
            'taxonomic_status': 'accepted',
            'traits': {
                'growth_form': 'tree',  # EcoregionsTreeFinder is trees only
                'treegoer_validated': True,
                'n_ecoregions': raw_data.get('n_ecoregions', 0),
                'total_observations': raw_data.get('total_observations', 0),
            }
        }

        # Extract genus
        parts = transformed['canonical_name'].split()
        if parts:
            transformed['genus'] = parts[0]

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
            eco_id: RESOLVE ecoregion ID (ECO_ID in data)

        Returns:
            List of species canonical names
        """
        df = self._load_data()
        if df is None:
            return []

        filtered = df[df['ECO_ID'] == eco_id]
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
            (df['ECO_ID'] == eco_id) &
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

        return matches[['ECO_ID', 'n']].rename(
            columns={'ECO_ID': 'eco_id', 'n': 'n_occurrences'}
        ).to_dict('records')

    def get_coverage_stats(self) -> Dict:
        """Get EcoregionsTreeFinder coverage statistics."""
        df = self._load_data()
        if df is None:
            return {}

        return {
            'total_records': len(df),
            'unique_species': df['species'].nunique(),
            'unique_ecoregions': df['ECO_ID'].nunique(),
        }
