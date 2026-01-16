"""REFLORA (Flora do Brasil 2020) crawler."""
from typing import Generator, Dict, Any, List
import requests
from bs4 import BeautifulSoup
import re
import time
from .base import BaseCrawler


class REFLORACrawler(BaseCrawler):
    """
    Crawler for Flora do Brasil 2020 (REFLORA/JBRJ).

    Website: http://floradobrasil.jbrj.gov.br
    Coverage: ~50,000 Brazilian plant species
    Data: Names, distribution, common names in Portuguese
    """

    name = 'reflora'
    BASE_URL = 'http://floradobrasil.jbrj.gov.br'
    API_URL = 'http://servicos.jbrj.gov.br/flora'

    def __init__(self, db_url: str):
        super().__init__(db_url)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'DiversiPlant/1.0 (Academic Research; contact@diversiplant.org)'
        })

    def fetch_data(self, mode='incremental', **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        Fetch species data from REFLORA.

        Uses the API when available, falls back to web scraping.

        Args:
            mode: 'full' or 'incremental'
            **kwargs: Additional parameters

        Yields:
            Species data
        """
        # Try API first
        families = kwargs.get('families', None) or self._get_families()
        max_per_family = kwargs.get('max_per_family', None)

        self.logger.info(f"Fetching from {len(families)} families")

        for family in families:
            self.logger.info(f"Processing family: {family}")
            try:
                species_list = self._fetch_family_species(family, max_per_family)
                for species in species_list:
                    yield species
                # Rate limiting
                time.sleep(0.5)
            except Exception as e:
                self.logger.error(f"Error processing family {family}: {e}")
                continue

    def _get_families(self) -> List[str]:
        """Get list of plant families from REFLORA."""
        families = []

        try:
            # Try API endpoint
            response = self.session.get(
                f"{self.API_URL}/familias",
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                families = [f.get('familia', f.get('name', '')) for f in data if f]
            else:
                # Fallback: scrape from website
                families = self._scrape_families()

        except Exception as e:
            self.logger.warning(f"Error fetching families: {e}, using default list")
            # Fallback to common Brazilian families
            families = [
                'Fabaceae', 'Asteraceae', 'Orchidaceae', 'Poaceae',
                'Rubiaceae', 'Melastomataceae', 'Myrtaceae', 'Euphorbiaceae',
                'Bromeliaceae', 'Lauraceae', 'Araceae', 'Solanaceae',
                'Apocynaceae', 'Piperaceae', 'Cyperaceae'
            ]

        return families

    def _scrape_families(self) -> List[str]:
        """Scrape family list from REFLORA website."""
        families = []
        try:
            url = f"{self.BASE_URL}/reflora/listaBrasil/PrincipalUC/PrincipalUC.do"
            response = self.session.get(url, timeout=30)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find family links
            family_links = soup.find_all('a', href=re.compile(r'familia='))
            for link in family_links:
                family_name = link.text.strip()
                if family_name:
                    families.append(family_name)

        except Exception as e:
            self.logger.error(f"Error scraping families: {e}")

        return families

    def _fetch_family_species(self, family: str, max_records: int = None) -> List[Dict]:
        """Fetch all species for a family."""
        species_list = []

        try:
            # Try API
            response = self.session.get(
                f"{self.API_URL}/taxon",
                params={
                    'familia': family,
                    'tipoResultado': 'json'
                },
                timeout=60
            )

            if response.status_code == 200:
                try:
                    data = response.json()
                    for item in data:
                        if max_records and len(species_list) >= max_records:
                            break
                        species_list.append(item)
                except ValueError:
                    # Response is not JSON, try scraping
                    species_list = self._scrape_family_species(family, max_records)
            else:
                species_list = self._scrape_family_species(family, max_records)

        except Exception as e:
            self.logger.error(f"Error fetching family {family}: {e}")

        return species_list

    def _scrape_family_species(self, family: str, max_records: int = None) -> List[Dict]:
        """Scrape species data for a family from website."""
        species_list = []

        try:
            url = f"{self.BASE_URL}/reflora/listaBrasil/ConsultaPublicaUC/ResultadoDaConsultaNo498UC.do"
            response = self.session.get(
                url,
                params={'familia': family},
                timeout=60
            )

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find species rows
            species_rows = soup.find_all('tr', class_='resultadoConsulta')

            for row in species_rows:
                if max_records and len(species_list) >= max_records:
                    break

                try:
                    species_data = self._parse_species_row(row, family)
                    if species_data:
                        species_list.append(species_data)
                except Exception as e:
                    self.logger.warning(f"Error parsing species row: {e}")

        except Exception as e:
            self.logger.error(f"Error scraping family {family}: {e}")

        return species_list

    def _parse_species_row(self, row, family: str) -> Dict:
        """Parse a species row from the search results."""
        cells = row.find_all('td')
        if len(cells) < 2:
            return None

        species_data = {
            'familia': family,
            'nomeCompleto': '',
            'id': None,
            'nomesVulgares': []
        }

        # Extract species name
        name_cell = cells[0]
        species_link = name_cell.find('a')
        if species_link:
            species_data['nomeCompleto'] = species_link.text.strip()
            href = species_link.get('href', '')
            # Extract ID from URL
            id_match = re.search(r'idDadosListaBrasil=(\d+)', href)
            if id_match:
                species_data['id'] = id_match.group(1)

        # Extract common names if available
        for cell in cells:
            text = cell.text.strip()
            if 'Nome popular:' in text or 'Nomes populares:' in text:
                names = text.replace('Nome popular:', '').replace('Nomes populares:', '')
                names = [n.strip() for n in names.split(',') if n.strip()]
                species_data['nomesVulgares'] = names

        return species_data

    def transform(self, raw_data: Dict) -> Dict:
        """
        Transform REFLORA data to internal schema.

        Args:
            raw_data: Raw species data from REFLORA

        Returns:
            Transformed data matching database schema
        """
        canonical = raw_data.get('nomeCompleto', '') or raw_data.get('scientificName', '')

        # Clean the name (remove author)
        canonical = self._clean_species_name(canonical)

        transformed = {
            'canonical_name': canonical,
            'family': raw_data.get('familia') or raw_data.get('family'),
            'reflora_id': str(raw_data.get('id')) if raw_data.get('id') else None,
            'taxonomic_status': 'accepted',
        }

        # Extract genus from canonical name
        parts = canonical.split()
        if parts:
            transformed['genus'] = parts[0]

        # Handle common names in Portuguese
        vulgar_names = raw_data.get('nomesVulgares', [])
        if vulgar_names:
            common_names = []
            for name in vulgar_names:
                if isinstance(name, str) and name.strip():
                    common_names.append({
                        'name': name.strip(),
                        'language': 'pt'
                    })
            if common_names:
                transformed['common_names'] = common_names

        return transformed

    def _clean_species_name(self, name: str) -> str:
        """Remove author and extra info from species name."""
        if not name:
            return ''

        # Remove everything after common author patterns
        patterns = [
            r'\s+\(.*?\)',  # (Author)
            r'\s+[A-Z][a-z]*\.\s*$',  # Author abbreviation at end
            r'\s+ex\s+.*$',  # ex Author
            r'\s+var\.\s+.*$',  # var. name
            r'\s+subsp\.\s+.*$',  # subsp. name
        ]

        cleaned = name.strip()
        for pattern in patterns:
            cleaned = re.sub(pattern, '', cleaned)

        # Keep only first two words (genus + species)
        parts = cleaned.split()
        if len(parts) >= 2:
            return f"{parts[0]} {parts[1]}"
        return cleaned

    def get_species_details(self, reflora_id: str) -> Dict:
        """
        Get detailed information for a specific species.

        Args:
            reflora_id: REFLORA species ID

        Returns:
            Detailed species information
        """
        try:
            response = self.session.get(
                f"{self.API_URL}/taxon/{reflora_id}",
                timeout=30
            )

            if response.status_code == 200:
                return response.json()

        except Exception as e:
            self.logger.error(f"Error fetching species {reflora_id}: {e}")

        return {}
