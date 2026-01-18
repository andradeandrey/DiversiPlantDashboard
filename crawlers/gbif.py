"""GBIF (Global Biodiversity Information Facility) crawler."""
from typing import Generator, Dict, Any, List
import requests
import time
from .base import BaseCrawler


class GBIFCrawler(BaseCrawler):
    """
    Crawler for Global Biodiversity Information Facility.

    API Documentation: https://www.gbif.org/developer/species
    Rate Limits: None specified, but use reasonable delays
    Coverage: ~2 million plant species names

    Note: GBIF API has a limit of 100,000 results per query.
    For large taxa like Tracheophyta (~300k species), use by_family=True
    to paginate by family instead of offset.
    """

    name = 'gbif'
    BASE_URL = 'https://api.gbif.org/v1'

    # Taxon keys in GBIF
    PLANTAE_KEY = 6           # All Plantae (includes algae, bryophytes)
    TRACHEOPHYTA_KEY = 7707728  # Vascular plants only (trees, shrubs, herbs, ferns)

    # Default to vascular plants for agroforestry relevance
    DEFAULT_TAXON_KEY = TRACHEOPHYTA_KEY

    # API limits
    MAX_OFFSET = 99700  # GBIF returns 404 after ~100k records
    REQUEST_DELAY = 0.1  # Delay between requests to be respectful

    def fetch_data(self, mode='incremental', **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        Fetch plant species from GBIF.

        Args:
            mode: 'full' for all species, 'incremental' for updates
            **kwargs: Additional parameters
                - taxon_key: Override the default taxon key (TRACHEOPHYTA)
                - include_all_plants: If True, use PLANTAE_KEY instead
                - by_family: If True, paginate by family to bypass 100k limit
                - families: List of specific family keys to fetch

        Yields:
            Species data from GBIF
        """
        # If by_family mode, delegate to family-based fetching
        if kwargs.get('by_family', False):
            yield from self._fetch_by_family(mode=mode, **kwargs)
            return

        limit = kwargs.get('limit', 300)
        max_records = kwargs.get('max_records', None)
        offset = 0
        total_fetched = 0

        # Determine which taxon to query
        if kwargs.get('include_all_plants'):
            taxon_key = self.PLANTAE_KEY
            taxon_name = "Plantae"
        else:
            taxon_key = kwargs.get('taxon_key', self.DEFAULT_TAXON_KEY)
            taxon_name = "Tracheophyta" if taxon_key == self.TRACHEOPHYTA_KEY else f"taxon {taxon_key}"

        self.logger.info(f"Starting GBIF fetch for {taxon_name} (limit={limit}, mode={mode})")

        while True:
            try:
                # Search for accepted plant species
                response = requests.get(
                    f"{self.BASE_URL}/species/search",
                    params={
                        'highertaxonKey': taxon_key,
                        'status': 'ACCEPTED',
                        'rank': 'SPECIES',
                        'limit': limit,
                        'offset': offset,
                    },
                    timeout=60
                )

                # Handle 404 as end of pagination (GBIF API limitation)
                if response.status_code == 404:
                    self.logger.info(f"Reached GBIF pagination limit at offset {offset}")
                    break

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
                    self.logger.info(f"End of records reached. Total: {total_fetched}")
                    break

                offset += limit

                # Check if we're approaching the API limit
                if offset >= self.MAX_OFFSET:
                    self.logger.warning(
                        f"Approaching GBIF API limit at offset {offset}. "
                        f"Use by_family=True for complete data."
                    )
                    break

                # Log progress every 3000 records
                if total_fetched % 3000 == 0:
                    self.logger.info(f"Progress: {total_fetched} records fetched")

                time.sleep(self.REQUEST_DELAY)

            except requests.exceptions.RequestException as e:
                self.logger.error(f"GBIF API error: {e}")
                # Don't raise on 404, treat as end of data
                if '404' in str(e):
                    self.logger.info(f"Stopping at offset {offset} due to API limit")
                    break
                raise

    def _get_families(self, taxon_key: int) -> List[Dict]:
        """
        Get all families within a higher taxon.

        Args:
            taxon_key: The higher taxon key (e.g., TRACHEOPHYTA_KEY)

        Returns:
            List of family records with 'key' and 'canonicalName'
        """
        families = []
        offset = 0
        limit = 1000

        self.logger.info(f"Fetching families for taxon {taxon_key}...")

        while True:
            try:
                response = requests.get(
                    f"{self.BASE_URL}/species/search",
                    params={
                        'highertaxonKey': taxon_key,
                        'rank': 'FAMILY',
                        'status': 'ACCEPTED',
                        'limit': limit,
                        'offset': offset,
                    },
                    timeout=60
                )

                if response.status_code == 404:
                    break

                response.raise_for_status()
                data = response.json()

                results = data.get('results', [])
                if not results:
                    break

                for fam in results:
                    families.append({
                        'key': fam.get('key'),
                        'name': fam.get('canonicalName') or fam.get('scientificName'),
                        'numDescendants': fam.get('numDescendants', 0)
                    })

                if data.get('endOfRecords', True):
                    break

                offset += limit
                time.sleep(self.REQUEST_DELAY)

            except requests.exceptions.RequestException as e:
                self.logger.error(f"Error fetching families: {e}")
                break

        self.logger.info(f"Found {len(families)} families")
        return families

    def _fetch_by_family(self, mode='incremental', **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        Fetch species by iterating through each family.
        This bypasses the 100k offset limit by making separate queries per family.

        Args:
            mode: 'full' or 'incremental'
            **kwargs: Additional parameters

        Yields:
            Species data from GBIF
        """
        limit = kwargs.get('limit', 300)
        max_records = kwargs.get('max_records', None)

        # Determine taxon
        if kwargs.get('include_all_plants'):
            taxon_key = self.PLANTAE_KEY
            taxon_name = "Plantae"
        else:
            taxon_key = kwargs.get('taxon_key', self.DEFAULT_TAXON_KEY)
            taxon_name = "Tracheophyta" if taxon_key == self.TRACHEOPHYTA_KEY else f"taxon {taxon_key}"

        self.logger.info(f"Starting GBIF fetch BY FAMILY for {taxon_name}")

        # Get all families
        families = kwargs.get('families') or self._get_families(taxon_key)

        # Sort by number of descendants (largest first for better progress visibility)
        families.sort(key=lambda x: x.get('numDescendants', 0), reverse=True)

        total_fetched = 0
        families_processed = 0

        for family in families:
            family_key = family.get('key')
            family_name = family.get('name', 'Unknown')

            if not family_key:
                continue

            offset = 0
            family_count = 0

            self.logger.info(f"Fetching family {families_processed + 1}/{len(families)}: {family_name}")

            while True:
                try:
                    response = requests.get(
                        f"{self.BASE_URL}/species/search",
                        params={
                            'highertaxonKey': family_key,
                            'status': 'ACCEPTED',
                            'rank': 'SPECIES',
                            'limit': limit,
                            'offset': offset,
                        },
                        timeout=60
                    )

                    if response.status_code == 404:
                        break

                    response.raise_for_status()
                    data = response.json()

                    results = data.get('results', [])
                    if not results:
                        break

                    for species in results:
                        yield species
                        total_fetched += 1
                        family_count += 1

                        if max_records and total_fetched >= max_records:
                            self.logger.info(f"Reached max_records limit: {max_records}")
                            return

                    if data.get('endOfRecords', True):
                        break

                    offset += limit
                    time.sleep(self.REQUEST_DELAY)

                except requests.exceptions.RequestException as e:
                    self.logger.error(f"Error fetching family {family_name}: {e}")
                    break

            families_processed += 1

            # Log progress every 10 families
            if families_processed % 10 == 0:
                self.logger.info(
                    f"Progress: {families_processed}/{len(families)} families, "
                    f"{total_fetched} total species"
                )

        self.logger.info(
            f"Completed BY FAMILY fetch: {families_processed} families, "
            f"{total_fetched} species"
        )

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
