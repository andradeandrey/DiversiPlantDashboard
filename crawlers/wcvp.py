"""WCVP (World Checklist of Vascular Plants) crawler."""
from typing import Generator, Dict, Any, Optional
import requests
import zipfile
import csv
import io
import os
import sys
import tempfile
from .base import BaseCrawler

# Increase CSV field size limit for large WCVP fields
csv.field_size_limit(sys.maxsize)


class WCVPCrawler(BaseCrawler):
    """
    Crawler for World Checklist of Vascular Plants.

    Source: Royal Botanic Gardens, Kew
    Coverage: ~350,000 accepted vascular plant species
    Data: Taxonomic backbone, distribution, synonyms
    """

    name = 'wcvp'

    # WCVP data download URL (static releases)
    DOWNLOAD_URL = 'https://sftp.kew.org/pub/data-repositories/WCVP/'
    NAMES_FILE = 'wcvp_names.csv'
    DISTRIBUTION_FILE = 'wcvp_distribution.csv'

    def __init__(self, db_url: str):
        super().__init__(db_url)
        self.session = requests.Session()
        self._data_dir: Optional[str] = None

    def fetch_data(self, mode='incremental', **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        Fetch species data from WCVP.

        Downloads the WCVP CSV files and processes them.

        Args:
            mode: 'full' or 'incremental'
            **kwargs: Additional parameters

        Yields:
            Species data
        """
        data_path = kwargs.get('data_path', None)
        max_records = kwargs.get('max_records', None)

        if data_path and os.path.exists(data_path):
            # Use local data file
            self._data_dir = data_path
        else:
            # Download data (or use cached)
            self._data_dir = self._download_data()

        if not self._data_dir:
            self.logger.error("Failed to obtain WCVP data")
            return

        names_file = os.path.join(self._data_dir, self.NAMES_FILE)
        if not os.path.exists(names_file):
            self.logger.error(f"Names file not found: {names_file}")
            return

        self.logger.info(f"Processing WCVP names from: {names_file}")
        count = 0

        with open(names_file, 'r', encoding='utf-8') as f:
            # WCVP uses pipe delimiter
            reader = csv.DictReader(f, delimiter='|')

            for row in reader:
                # Only process accepted species
                if row.get('taxon_status') != 'Accepted':
                    continue
                if row.get('taxon_rank') != 'Species':
                    continue

                yield row
                count += 1

                if count % 10000 == 0:
                    self.logger.info(f"Progress: {count} species processed")

                if max_records and count >= max_records:
                    break

        self.logger.info(f"Processed {count} accepted species")

    def _download_data(self) -> Optional[str]:
        """Download WCVP data files."""
        # Check for cached data
        cache_dir = os.path.join(tempfile.gettempdir(), 'wcvp_cache')

        names_file = os.path.join(cache_dir, self.NAMES_FILE)
        if os.path.exists(names_file):
            self.logger.info("Using cached WCVP data")
            return cache_dir

        self.logger.info("Downloading WCVP data...")

        try:
            # Download ZIP file
            zip_url = f"{self.DOWNLOAD_URL}wcvp.zip"
            response = self.session.get(zip_url, stream=True, timeout=300)
            response.raise_for_status()

            # Extract to cache directory
            os.makedirs(cache_dir, exist_ok=True)

            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                z.extractall(cache_dir)

            self.logger.info(f"WCVP data extracted to: {cache_dir}")
            return cache_dir

        except Exception as e:
            self.logger.error(f"Error downloading WCVP data: {e}")
            return None

    def transform(self, raw_data: Dict) -> Dict:
        """
        Transform WCVP data to internal schema.

        Args:
            raw_data: Raw CSV row from WCVP

        Returns:
            Transformed data matching database schema
        """
        transformed = {
            'canonical_name': raw_data.get('taxon_name', ''),
            'genus': raw_data.get('genus', ''),
            'family': raw_data.get('family', ''),
            'wcvp_id': raw_data.get('plant_name_id') or raw_data.get('kew_id'),
            'taxonomic_status': 'accepted',
        }

        # Extract traits if available
        traits = {}

        life_form = raw_data.get('lifeform_description', '')
        if life_form:
            growth_form = self._parse_life_form(life_form)
            if growth_form:
                traits['growth_form'] = growth_form
            traits['life_form'] = life_form

        if traits:
            transformed['traits'] = traits

        return transformed

    def _parse_life_form(self, life_form: str) -> Optional[str]:
        """Extract growth form from WCVP life form description."""
        life_form = life_form.lower()

        if 'tree' in life_form:
            return 'tree'
        elif 'shrub' in life_form:
            return 'shrub'
        elif 'herb' in life_form or 'annual' in life_form or 'perennial' in life_form:
            return 'herb'
        elif 'climber' in life_form or 'vine' in life_form or 'liana' in life_form:
            return 'climber'
        elif 'palm' in life_form:
            return 'palm'
        elif 'fern' in life_form:
            return 'fern'
        elif 'bamboo' in life_form:
            return 'bamboo'

        return None

    def fetch_distribution(self) -> Generator[Dict, None, None]:
        """
        Fetch distribution data from WCVP.

        Yields:
            Distribution records with TDWG codes
        """
        if not self._data_dir:
            return

        dist_file = os.path.join(self._data_dir, self.DISTRIBUTION_FILE)
        if not os.path.exists(dist_file):
            self.logger.warning("Distribution file not found")
            return

        with open(dist_file, 'r', encoding='utf-8') as f:
            # WCVP uses pipe delimiter
            reader = csv.DictReader(f, delimiter='|')

            for row in reader:
                yield {
                    'wcvp_id': row.get('plant_name_id'),
                    'tdwg_code': row.get('area_code_l3'),
                    'native': row.get('introduced') == '0',
                    'introduced': row.get('introduced') == '1',
                    'endemic': row.get('endemic') == '1',
                }

    def get_synonyms(self, wcvp_id: str) -> list:
        """
        Get synonyms for a species.

        Args:
            wcvp_id: WCVP plant name ID

        Returns:
            List of synonym names
        """
        synonyms = []

        if not self._data_dir:
            return synonyms

        names_file = os.path.join(self._data_dir, self.NAMES_FILE)

        with open(names_file, 'r', encoding='utf-8') as f:
            # WCVP uses pipe delimiter
            reader = csv.DictReader(f, delimiter='|')

            for row in reader:
                if row.get('accepted_plant_name_id') == wcvp_id:
                    if row.get('taxon_status') == 'Synonym':
                        synonyms.append(row.get('taxon_name'))

        return synonyms
