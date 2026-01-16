"""GBIF (Global Biodiversity Information Facility) crawler."""
from typing import Generator, Dict, Any
import requests
from .base import BaseCrawler


class GBIFCrawler(BaseCrawler):
    """
    Crawler for Global Biodiversity Information Facility.

    API Documentation: https://www.gbif.org/developer/species
    Rate Limits: None specified, but use reasonable delays
    Coverage: ~2 million plant species names
    """

    name = 'gbif'
    BASE_URL = 'https://api.gbif.org/v1'

    # Plant kingdom key in GBIF
    PLANTAE_KEY = 6

    def fetch_data(self, mode='incremental', **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        Fetch plant species from GBIF.

        Args:
            mode: 'full' for all species, 'incremental' for updates
            **kwargs: Additional parameters

        Yields:
            Species data from GBIF
        """
        limit = kwargs.get('limit', 300)
        max_records = kwargs.get('max_records', None)
        offset = 0
        total_fetched = 0

        self.logger.info(f"Starting GBIF fetch (limit={limit}, mode={mode})")

        while True:
            try:
                # Search for accepted plant species
                response = requests.get(
                    f"{self.BASE_URL}/species/search",
                    params={
                        'highertaxonKey': self.PLANTAE_KEY,
                        'status': 'ACCEPTED',
                        'rank': 'SPECIES',
                        'limit': limit,
                        'offset': offset,
                    },
                    timeout=60
                )
                response.raise_for_status()
                data = response.json()

                results = data.get('results', [])
                if not results:
                    self.logger.info(f"No more results at offset {offset}")
                    break

                for species in results:
                    yield species
                    total_fetched += 1

                    if max_records and total_fetched >= max_records:
                        self.logger.info(f"Reached max_records limit: {max_records}")
                        return

                # Check if there are more results
                end_of_records = data.get('endOfRecords', True)
                if end_of_records:
                    break

                offset += limit
                self.logger.info(f"Fetched {total_fetched} records, continuing from offset {offset}")

            except requests.exceptions.RequestException as e:
                self.logger.error(f"GBIF API error: {e}")
                raise

    def transform(self, raw_data: Dict) -> Dict:
        """
        Transform GBIF data to internal schema.

        Args:
            raw_data: Raw species data from GBIF

        Returns:
            Transformed data matching database schema
        """
        transformed = {
            'canonical_name': raw_data.get('canonicalName') or raw_data.get('species'),
            'genus': raw_data.get('genus'),
            'family': raw_data.get('family'),
            'gbif_taxon_key': raw_data.get('key') or raw_data.get('usageKey'),
            'taxonomic_status': self._normalize_status(raw_data.get('taxonomicStatus', '')),
        }

        # Extract vernacular names if available
        vernacular = raw_data.get('vernacularNames', [])
        if vernacular:
            common_names = []
            for v in vernacular:
                lang = self._normalize_language(v.get('language', 'en'))
                if lang in ['en', 'pt']:
                    common_names.append({
                        'name': v.get('vernacularName'),
                        'language': lang
                    })
            if common_names:
                transformed['common_names'] = common_names

        return transformed

    def _normalize_status(self, status: str) -> str:
        """Normalize taxonomic status."""
        status = status.lower() if status else ''
        if status in ['accepted', 'valid']:
            return 'accepted'
        elif status in ['synonym', 'heterotypic_synonym', 'homotypic_synonym']:
            return 'synonym'
        else:
            return 'unresolved'

    def _normalize_language(self, lang: str) -> str:
        """Normalize language codes."""
        lang = lang.lower() if lang else 'en'
        # Map common variations
        lang_map = {
            'english': 'en',
            'eng': 'en',
            'portuguese': 'pt',
            'por': 'pt',
            'pt-br': 'pt',
        }
        return lang_map.get(lang, lang[:2] if len(lang) >= 2 else 'en')

    def get_species_details(self, taxon_key: int) -> Dict:
        """
        Get detailed information for a specific species.

        Args:
            taxon_key: GBIF taxon key

        Returns:
            Detailed species information
        """
        try:
            response = requests.get(
                f"{self.BASE_URL}/species/{taxon_key}",
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching species {taxon_key}: {e}")
            return {}

    def get_occurrences(self, taxon_key: int, country: str = None) -> Generator[Dict, None, None]:
        """
        Get occurrence records for a species.

        Args:
            taxon_key: GBIF taxon key
            country: Optional country code filter

        Yields:
            Occurrence records
        """
        offset = 0
        limit = 300

        while True:
            params = {
                'taxonKey': taxon_key,
                'limit': limit,
                'offset': offset,
            }
            if country:
                params['country'] = country

            try:
                response = requests.get(
                    f"{self.BASE_URL}/occurrence/search",
                    params=params,
                    timeout=60
                )
                response.raise_for_status()
                data = response.json()

                results = data.get('results', [])
                if not results:
                    break

                for occ in results:
                    yield occ

                if data.get('endOfRecords', True):
                    break

                offset += limit

            except requests.exceptions.RequestException as e:
                self.logger.error(f"Error fetching occurrences: {e}")
                break
