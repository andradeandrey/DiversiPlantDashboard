"""IUCN Red List crawler."""
from typing import Generator, Dict, Any, List, Optional
import requests
import os
from .base import BaseCrawler


class IUCNCrawler(BaseCrawler):
    """
    Crawler for IUCN Red List of Threatened Species.

    API: https://apiv3.iucnredlist.org
    Coverage: ~150,000 species assessments
    Data: Conservation status, threats, habitats
    Note: Requires API token from IUCN
    """

    name = 'iucn'

    BASE_URL = 'https://apiv3.iucnredlist.org/api/v3'

    # IUCN Red List categories
    CATEGORIES = {
        'EX': 'Extinct',
        'EW': 'Extinct in the Wild',
        'CR': 'Critically Endangered',
        'EN': 'Endangered',
        'VU': 'Vulnerable',
        'NT': 'Near Threatened',
        'LC': 'Least Concern',
        'DD': 'Data Deficient',
        'NE': 'Not Evaluated',
    }

    def __init__(self, db_url: str):
        super().__init__(db_url)
        self.api_token = os.environ.get('IUCN_API_TOKEN', '')
        self.session = requests.Session()

    def _get_headers(self) -> Dict:
        """Get request headers with API token."""
        return {
            'Authorization': f'Token {self.api_token}'
        }

    def fetch_data(self, mode='incremental', **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        Fetch species data from IUCN Red List.

        Args:
            mode: 'full' or 'incremental'
            **kwargs: Additional parameters

        Yields:
            Species conservation data
        """
        if not self.api_token:
            self.logger.error("IUCN API token not set. Set IUCN_API_TOKEN environment variable.")
            return

        region = kwargs.get('region', None)
        category = kwargs.get('category', None)
        max_records = kwargs.get('max_records', None)

        # Fetch plant species
        page = 0
        count = 0

        while True:
            try:
                # Get species list
                url = f"{self.BASE_URL}/speciescount/kingdom/plantae"
                if region:
                    url = f"{self.BASE_URL}/species/region/{region}/page/{page}"
                else:
                    url = f"{self.BASE_URL}/species/page/{page}"

                response = self.session.get(
                    url,
                    headers=self._get_headers(),
                    params={'token': self.api_token},
                    timeout=60
                )
                response.raise_for_status()
                data = response.json()

                species_list = data.get('result', [])
                if not species_list:
                    break

                for species in species_list:
                    # Filter to plants only
                    if species.get('kingdom_name', '').lower() != 'plantae':
                        continue

                    # Filter by category if specified
                    if category and species.get('category') != category:
                        continue

                    yield species
                    count += 1

                    if max_records and count >= max_records:
                        return

                page += 1
                self.logger.info(f"Fetched page {page}, {count} plant species so far")

            except requests.exceptions.RequestException as e:
                self.logger.error(f"IUCN API error: {e}")
                raise

    def transform(self, raw_data: Dict) -> Dict:
        """
        Transform IUCN data to internal schema.

        Args:
            raw_data: Raw species data from IUCN

        Returns:
            Transformed data
        """
        scientific_name = raw_data.get('scientific_name', '')

        if not scientific_name:
            return {}

        transformed = {
            'canonical_name': self._clean_species_name(scientific_name),
            'family': raw_data.get('family_name'),
            'iucn_taxon_id': raw_data.get('taxonid'),
            'taxonomic_status': 'accepted',
        }

        # Extract genus
        parts = transformed['canonical_name'].split()
        if parts:
            transformed['genus'] = parts[0]

        # Store conservation data as traits
        traits = {}

        category = raw_data.get('category')
        if category:
            traits['iucn_category'] = category
            traits['iucn_category_name'] = self.CATEGORIES.get(category, category)

        if raw_data.get('population_trend'):
            traits['population_trend'] = raw_data['population_trend']

        if traits:
            transformed['traits'] = traits

        # Common names
        main_common = raw_data.get('main_common_name')
        if main_common:
            transformed['common_names'] = [{
                'name': main_common,
                'language': 'en'
            }]

        return transformed

    def _clean_species_name(self, name: str) -> str:
        """Clean species name."""
        if not name:
            return ''

        parts = name.strip().split()
        if len(parts) >= 2:
            return f"{parts[0]} {parts[1]}"
        return name.strip()

    def get_species_details(self, taxon_id: int) -> Dict:
        """
        Get detailed information for a species.

        Args:
            taxon_id: IUCN taxon ID

        Returns:
            Detailed species information
        """
        if not self.api_token:
            return {}

        try:
            response = self.session.get(
                f"{self.BASE_URL}/species/id/{taxon_id}",
                headers=self._get_headers(),
                params={'token': self.api_token},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data.get('result', [{}])[0]

        except Exception as e:
            self.logger.error(f"Error fetching species {taxon_id}: {e}")
            return {}

    def get_species_by_name(self, name: str) -> Optional[Dict]:
        """
        Search for a species by name.

        Args:
            name: Species scientific name

        Returns:
            Species data if found
        """
        if not self.api_token:
            return None

        try:
            response = self.session.get(
                f"{self.BASE_URL}/species/{name}",
                headers=self._get_headers(),
                params={'token': self.api_token},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            results = data.get('result', [])
            return results[0] if results else None

        except Exception as e:
            self.logger.error(f"Error searching species {name}: {e}")
            return None

    def get_threats(self, taxon_id: int) -> List[Dict]:
        """
        Get threats for a species.

        Args:
            taxon_id: IUCN taxon ID

        Returns:
            List of threats
        """
        if not self.api_token:
            return []

        try:
            response = self.session.get(
                f"{self.BASE_URL}/threats/species/id/{taxon_id}",
                headers=self._get_headers(),
                params={'token': self.api_token},
                timeout=30
            )
            response.raise_for_status()
            return response.json().get('result', [])

        except Exception as e:
            self.logger.error(f"Error fetching threats: {e}")
            return []

    def get_habitats(self, taxon_id: int) -> List[Dict]:
        """
        Get habitats for a species.

        Args:
            taxon_id: IUCN taxon ID

        Returns:
            List of habitats
        """
        if not self.api_token:
            return []

        try:
            response = self.session.get(
                f"{self.BASE_URL}/habitats/species/id/{taxon_id}",
                headers=self._get_headers(),
                params={'token': self.api_token},
                timeout=30
            )
            response.raise_for_status()
            return response.json().get('result', [])

        except Exception as e:
            self.logger.error(f"Error fetching habitats: {e}")
            return []

    def get_conservation_actions(self, taxon_id: int) -> List[Dict]:
        """
        Get conservation measures for a species.

        Args:
            taxon_id: IUCN taxon ID

        Returns:
            List of conservation actions
        """
        if not self.api_token:
            return []

        try:
            response = self.session.get(
                f"{self.BASE_URL}/conservation_actions/species/id/{taxon_id}",
                headers=self._get_headers(),
                params={'token': self.api_token},
                timeout=30
            )
            response.raise_for_status()
            return response.json().get('result', [])

        except Exception as e:
            self.logger.error(f"Error fetching conservation actions: {e}")
            return []
