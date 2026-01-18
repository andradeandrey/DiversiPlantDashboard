"""IUCN Red List crawler (API v4).

Data source: IUCN Red List of Threatened Species
API: https://api.iucnredlist.org/api/v4
Registration: https://api.iucnredlist.org/users/sign_up

Note: API v3 discontinued after March 2025. This uses v4.
"""
from typing import Generator, Dict, Any, List, Optional
import requests
import os
from .base import BaseCrawler


class IUCNCrawler(BaseCrawler):
    """
    Crawler for IUCN Red List of Threatened Species (API v4).

    API: https://api.iucnredlist.org/api/v4
    Coverage: ~150,000 species assessments
    Data: Conservation status, threats, habitats
    Note: Requires API token from IUCN (register at api.iucnredlist.org)
    """

    name = 'iucn'

    BASE_URL = 'https://api.iucnredlist.org/api/v4'

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
        """Get request headers with Bearer token (v4 API)."""
        return {
            'Authorization': f'Bearer {self.api_token}',
            'Accept': 'application/json'
        }

    def fetch_data(self, mode='incremental', **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        Fetch plant species data from IUCN Red List v4 API.

        Args:
            mode: 'full' or 'incremental'
            **kwargs: Additional parameters

        Yields:
            Species conservation data
        """
        if not self.api_token:
            self.logger.error(
                "IUCN API token not set. "
                "Register at https://api.iucnredlist.org/users/sign_up "
                "and set IUCN_API_TOKEN environment variable."
            )
            return

        category = kwargs.get('category', None)
        max_records = kwargs.get('max_records', None)

        # Fetch plant species from v4 API
        # Endpoint: /api/v4/taxa/kingdom/Plantae
        page = 0
        count = 0

        while True:
            try:
                url = f"{self.BASE_URL}/taxa/kingdom/Plantae"
                params = {
                    'page': page,
                    'latest': 'true'  # Only latest assessments
                }

                response = self.session.get(
                    url,
                    headers=self._get_headers(),
                    params=params,
                    timeout=60
                )

                if response.status_code == 401:
                    self.logger.error("IUCN API authentication failed. Check your token.")
                    return

                response.raise_for_status()
                data = response.json()

                # v4 API returns 'assessments' list
                assessments = data.get('assessments', [])
                if not assessments:
                    break

                for assessment in assessments:
                    # Filter by category if specified
                    if category:
                        red_list_cat = assessment.get('red_list_category', {})
                        if red_list_cat.get('code') != category:
                            continue

                    yield assessment
                    count += 1

                    if max_records and count >= max_records:
                        return

                page += 1
                self.logger.info(f"Fetched page {page}, {count} plant species so far")

                # v4 API paginates at 100 per page
                if len(assessments) < 100:
                    break

            except requests.exceptions.RequestException as e:
                self.logger.error(f"IUCN API error: {e}")
                raise

    def transform(self, raw_data: Dict) -> Dict:
        """
        Transform IUCN v4 API data to internal schema.

        Args:
            raw_data: Raw assessment data from IUCN v4 API

        Returns:
            Transformed data
        """
        # v4 API returns taxon info nested
        taxon = raw_data.get('taxon', {})
        scientific_name = taxon.get('scientific_name', '')

        if not scientific_name:
            return {}

        transformed = {
            'canonical_name': self._clean_species_name(scientific_name),
            'family': taxon.get('family_name'),
            'iucn_taxon_id': taxon.get('taxon_id'),
            'taxonomic_status': 'accepted',
        }

        # Extract genus
        parts = transformed['canonical_name'].split()
        if parts:
            transformed['genus'] = parts[0]

        # Store conservation data as traits
        traits = {}

        # v4 API: red_list_category is nested
        red_list_cat = raw_data.get('red_list_category', {})
        category = red_list_cat.get('code')
        if category:
            traits['iucn_category'] = category
            traits['iucn_category_name'] = self.CATEGORIES.get(category, red_list_cat.get('name', category))

        # Population trend
        pop_trend = raw_data.get('population_trend', {})
        if pop_trend.get('code'):
            traits['population_trend'] = pop_trend.get('code')

        # Assessment year
        if raw_data.get('year_published'):
            traits['assessment_year'] = raw_data['year_published']

        if traits:
            transformed['traits'] = traits

        # Common names (may need separate API call in v4)
        # v4 API may include vernacular names differently
        vernacular_names = raw_data.get('vernacular_names', [])
        if vernacular_names:
            common_names = []
            for vn in vernacular_names[:5]:  # Limit to 5
                common_names.append({
                    'name': vn.get('name', ''),
                    'language': vn.get('language', 'en')
                })
            if common_names:
                transformed['common_names'] = common_names

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
