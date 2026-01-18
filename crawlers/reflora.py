"""REFLORA (Flora e Funga do Brasil) crawler.

Data source: Flora e Funga do Brasil - Instituto de Pesquisas Jardim Botânico do Rio de Janeiro
IPT: https://ipt.jbrj.gov.br/jbrj/resource?r=lista_especies_flora_brasil
GBIF: https://doi.org/10.15468/1mtkaw

Note: Old API (servicos.jbrj.gov.br) was discontinued. Now uses Darwin Core Archive.
"""
from typing import Generator, Dict, Any, List, Optional
import requests
import zipfile
import pandas as pd
import json
import os
import tempfile
from .base import BaseCrawler


class REFLORACrawler(BaseCrawler):
    """
    Crawler for Flora e Funga do Brasil (REFLORA/JBRJ).

    Source: Darwin Core Archive from IPT
    Coverage: ~163,000 Brazilian plant and fungi species
    Data: Names, distribution by state, common names in Portuguese, life forms
    """

    name = 'reflora'

    # IPT Darwin Core Archive URL
    DWC_ARCHIVE_URL = 'https://ipt.jbrj.gov.br/jbrj/archive.do?r=lista_especies_flora_brasil'

    def __init__(self, db_url: str):
        super().__init__(db_url)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'DiversiPlant/1.0 (Academic Research)'
        })
        self._cache_dir = os.path.join(tempfile.gettempdir(), 'reflora_dwc')
        self._taxon_df: Optional[pd.DataFrame] = None
        self._vernacular_df: Optional[pd.DataFrame] = None
        self._distribution_df: Optional[pd.DataFrame] = None
        self._profile_df: Optional[pd.DataFrame] = None

    def fetch_data(self, mode='incremental', **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        Fetch species data from Flora e Funga do Brasil Darwin Core Archive.

        Args:
            mode: 'full' or 'incremental'
            **kwargs: Additional parameters (max_records, kingdom_filter)

        Yields:
            Species data records
        """
        max_records = kwargs.get('max_records', None)
        kingdom_filter = kwargs.get('kingdom', 'Plantae')  # Filter for plants only

        # Download and extract Darwin Core Archive
        if not self._load_dwc_archive():
            self.logger.error("Failed to load Darwin Core Archive")
            return

        # Filter for accepted names only (NOME_ACEITO in Portuguese)
        taxon_df = self._taxon_df[
            self._taxon_df['taxonomicStatus'] == 'NOME_ACEITO'
        ].copy()

        # Filter by kingdom if specified
        if kingdom_filter:
            taxon_df = taxon_df[taxon_df['kingdom'] == kingdom_filter]

        # Filter for species rank only (not orders, families, etc.)
        # Valid ranks: ESPECIE, VARIEDADE, SUBESPECIE, FORMA
        species_ranks = ['ESPECIE', 'VARIEDADE', 'SUBESPECIE', 'FORMA']
        taxon_df = taxon_df[taxon_df['taxonRank'].isin(species_ranks)]

        self.logger.info(f"Processing {len(taxon_df)} accepted {kingdom_filter} species")

        count = 0
        for _, row in taxon_df.iterrows():
            taxon_id = row.get('id') or row.get('taxonID')

            # Get vernacular names for this taxon
            vernacular_names = []
            if self._vernacular_df is not None and taxon_id:
                vn = self._vernacular_df[self._vernacular_df['id'] == taxon_id]
                vernacular_names = vn['vernacularName'].tolist() if not vn.empty else []

            # Get species profile (life form, etc.)
            profile = {}
            if self._profile_df is not None and taxon_id:
                sp = self._profile_df[self._profile_df['id'] == taxon_id]
                if not sp.empty:
                    profile = sp.iloc[0].to_dict()

            record = row.to_dict()
            record['vernacularNames'] = vernacular_names
            record['profile'] = profile

            yield record
            count += 1

            if count % 10000 == 0:
                self.logger.info(f"Progress: {count} species processed")

            if max_records and count >= max_records:
                break

    def _load_dwc_archive(self) -> bool:
        """Download and load Darwin Core Archive."""
        if self._taxon_df is not None:
            return True

        os.makedirs(self._cache_dir, exist_ok=True)
        archive_path = os.path.join(self._cache_dir, 'dwc_archive.zip')
        taxon_path = os.path.join(self._cache_dir, 'taxon.txt')

        # Check if already extracted
        if os.path.exists(taxon_path):
            self.logger.info("Loading Flora e Funga do Brasil from cache")
            return self._load_extracted_files()

        # Download archive
        self.logger.info("Downloading Flora e Funga do Brasil Darwin Core Archive (~20MB)...")
        try:
            response = self.session.get(self.DWC_ARCHIVE_URL, timeout=600, stream=True)
            response.raise_for_status()

            with open(archive_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            self.logger.info("Download complete, extracting...")

            # Extract archive
            with zipfile.ZipFile(archive_path, 'r') as zf:
                zf.extractall(self._cache_dir)

            return self._load_extracted_files()

        except Exception as e:
            self.logger.error(f"Error downloading Darwin Core Archive: {e}")
            return False

    def _load_extracted_files(self) -> bool:
        """Load extracted DwC-A files into DataFrames."""
        try:
            # Main taxon file
            taxon_path = os.path.join(self._cache_dir, 'taxon.txt')
            if os.path.exists(taxon_path):
                self._taxon_df = pd.read_csv(taxon_path, sep='\t', low_memory=False)
                self.logger.info(f"Loaded {len(self._taxon_df)} taxon records")

            # Vernacular names
            vernacular_path = os.path.join(self._cache_dir, 'vernacularname.txt')
            if os.path.exists(vernacular_path):
                self._vernacular_df = pd.read_csv(vernacular_path, sep='\t', low_memory=False)
                self.logger.info(f"Loaded {len(self._vernacular_df)} vernacular names")

            # Distribution
            dist_path = os.path.join(self._cache_dir, 'distribution.txt')
            if os.path.exists(dist_path):
                self._distribution_df = pd.read_csv(dist_path, sep='\t', low_memory=False)
                self.logger.info(f"Loaded {len(self._distribution_df)} distribution records")

            # Species profile
            profile_path = os.path.join(self._cache_dir, 'speciesprofile.txt')
            if os.path.exists(profile_path):
                self._profile_df = pd.read_csv(profile_path, sep='\t', low_memory=False)
                self.logger.info(f"Loaded {len(self._profile_df)} species profiles")

            return self._taxon_df is not None

        except Exception as e:
            self.logger.error(f"Error loading DwC-A files: {e}")
            return False

    def transform(self, raw_data: Dict) -> Dict:
        """
        Transform Flora e Funga do Brasil Darwin Core data to internal schema.

        Args:
            raw_data: Raw taxon data from DwC-A

        Returns:
            Transformed data matching database schema
        """
        # Darwin Core uses scientificName
        scientific_name = raw_data.get('scientificName', '')
        canonical = self._clean_species_name(scientific_name)

        if not canonical:
            return {}

        transformed = {
            'canonical_name': canonical,
            'family': raw_data.get('family'),
            'genus': raw_data.get('genus'),
            'reflora_id': str(raw_data.get('id')) if raw_data.get('id') else None,
            'taxonomic_status': 'accepted',
        }

        # Build traits from profile
        traits = {}
        profile = raw_data.get('profile', {})

        # Life form from DwC-A speciesprofile (stored as JSON string)
        life_form_json = profile.get('lifeForm')
        if life_form_json and pd.notna(life_form_json):
            try:
                life_form_data = json.loads(life_form_json) if isinstance(life_form_json, str) else life_form_json
                life_forms = life_form_data.get('lifeForm', [])
                habitats = life_form_data.get('habitat', [])
                vegetation_types = life_form_data.get('vegetationType', [])

                # Use first life form for growth_form mapping
                if life_forms:
                    growth_form = self._map_life_form(life_forms[0])
                    if growth_form:
                        traits['growth_form'] = growth_form
                    traits['life_forms_reflora'] = life_forms

                if habitats:
                    traits['habitat'] = habitats

                if vegetation_types:
                    traits['vegetation_types'] = vegetation_types

            except (json.JSONDecodeError, TypeError):
                pass

        if traits:
            transformed['traits'] = traits

        # Handle vernacular names (Portuguese)
        vernacular_names = raw_data.get('vernacularNames', [])
        if vernacular_names:
            common_names = []
            for name in vernacular_names:
                if isinstance(name, str) and name.strip():
                    common_names.append({
                        'name': name.strip(),
                        'language': 'pt'
                    })
            if common_names:
                transformed['common_names'] = common_names

        return transformed

    def _map_life_form(self, life_form: str) -> str:
        """Map REFLORA life form to standardized growth_form."""
        if not life_form:
            return ''

        life_form = life_form.lower().strip()

        mappings = {
            'árvore': 'tree',
            'arvore': 'tree',
            'arbusto': 'shrub',
            'subarbusto': 'subshrub',
            'erva': 'forb',
            'trepadeira': 'vine',
            'liana': 'liana',
            'palmeira': 'palm',
            'bambu': 'bamboo',
            'samambaia': 'fern',
            'epífita': 'epiphyte',
            'epifita': 'epiphyte',
            'aquática': 'aquatic',
            'aquatica': 'aquatic',
            'suculenta': 'succulent',
        }

        for key, value in mappings.items():
            if key in life_form:
                return value

        return 'other'

    def _clean_species_name(self, name: str) -> str:
        """Extract binomial name from scientific name with author."""
        if not name:
            return ''

        # Keep only first two words (genus + species)
        parts = name.strip().split()
        if len(parts) >= 2:
            return f"{parts[0]} {parts[1]}"
        return name.strip()

    def get_species_by_state(self, state_code: str) -> List[str]:
        """
        Get species occurring in a Brazilian state.

        Args:
            state_code: Two-letter state code (e.g., 'SC', 'SP')

        Returns:
            List of species canonical names
        """
        if not self._load_dwc_archive():
            return []

        if self._distribution_df is None:
            return []

        # Filter distribution by state
        state_dist = self._distribution_df[
            self._distribution_df['locality'].str.contains(state_code, case=False, na=False)
        ]

        taxon_ids = state_dist['id'].unique()

        # Get species names for these taxon IDs
        species = self._taxon_df[self._taxon_df['id'].isin(taxon_ids)]
        return [self._clean_species_name(n) for n in species['scientificName'].tolist()]

    def get_endemic_species(self) -> List[str]:
        """Get all species endemic to Brazil (from distribution data)."""
        if not self._load_dwc_archive():
            return []

        if self._distribution_df is None:
            return []

        # Parse occurrenceRemarks JSON to find endemic species
        endemic_ids = set()
        for _, row in self._distribution_df.iterrows():
            remarks = row.get('occurrenceRemarks')
            if remarks and pd.notna(remarks):
                try:
                    data = json.loads(remarks) if isinstance(remarks, str) else remarks
                    if data.get('endemism', '').lower() == 'endemica':
                        endemic_ids.add(row['id'])
                except (json.JSONDecodeError, TypeError):
                    pass

        endemic = self._taxon_df[self._taxon_df['id'].isin(endemic_ids)]
        return [self._clean_species_name(n) for n in endemic['scientificName'].tolist()]

    def get_coverage_stats(self) -> Dict:
        """Get Flora e Funga do Brasil coverage statistics."""
        if not self._load_dwc_archive():
            return {}

        return {
            'total_taxa': len(self._taxon_df),
            'accepted_species': len(self._taxon_df[self._taxon_df['taxonomicStatus'] == 'NOME_ACEITO']),
            'vernacular_names': len(self._vernacular_df) if self._vernacular_df is not None else 0,
            'distributions': len(self._distribution_df) if self._distribution_df is not None else 0,
        }
