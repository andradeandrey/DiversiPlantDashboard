"""GIFT (Global Inventory of Floras and Traits) crawler."""
from typing import Generator, Dict, Any, List, Optional
import subprocess
import json
import tempfile
import os
from .base import BaseCrawler


class GIFTCrawler(BaseCrawler):
    """
    Crawler for Global Inventory of Floras and Traits.

    Uses the GIFT R package via rpy2 or subprocess.
    Coverage: ~350,000 species with functional traits
    Traits: growth_form, height, dispersal, nitrogen fixation, etc.
    """

    name = 'gift'

    # GIFT trait IDs for the traits we need
    TRAIT_IDS = {
        'growth_form': '1.2.1',
        'climber_type': '1.4.2',
        'dispersal_syndrome': '3.3.1',
        'nitrogen_fixer': '4.5.1',
        'max_height': '3.1.1',
        'woodiness': '1.2.2',
        'life_form': '1.1.1',
    }

    def __init__(self, db_url: str):
        super().__init__(db_url)
        self._r_available = self._check_r_available()

    def _check_r_available(self) -> bool:
        """Check if R and GIFT package are available."""
        try:
            result = subprocess.run(
                ['Rscript', '-e', 'library(GIFT); cat("ok")'],
                capture_output=True,
                text=True,
                timeout=30
            )
            return 'ok' in result.stdout
        except Exception as e:
            self.logger.warning(f"R/GIFT not available: {e}")
            return False

    def fetch_data(self, mode='incremental', **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        Fetch species traits from GIFT via R.

        Args:
            mode: 'full' or 'incremental'
            **kwargs: Additional parameters

        Yields:
            Species trait data
        """
        if not self._r_available:
            self.logger.error("R/GIFT package not available. Install R and GIFT package.")
            return

        traits_to_fetch = kwargs.get('traits', list(self.TRAIT_IDS.keys()))
        region = kwargs.get('region', None)

        self.logger.info(f"Fetching GIFT traits: {traits_to_fetch}")

        for trait_name in traits_to_fetch:
            trait_id = self.TRAIT_IDS.get(trait_name)
            if not trait_id:
                continue

            self.logger.info(f"Fetching trait: {trait_name} (ID: {trait_id})")

            try:
                data = self._fetch_trait_data(trait_id, region)
                for record in data:
                    record['_trait_name'] = trait_name
                    yield record

            except Exception as e:
                self.logger.error(f"Error fetching trait {trait_name}: {e}")
                continue

    def _fetch_trait_data(self, trait_id: str, region: str = None) -> List[Dict]:
        """Fetch trait data from GIFT using R."""
        # Create R script
        r_script = f'''
        library(GIFT)
        library(jsonlite)

        # Fetch trait data
        traits <- GIFT_traits(trait_IDs = "{trait_id}")

        # Convert to JSON
        json_data <- toJSON(traits, auto_unbox = TRUE)
        cat(json_data)
        '''

        # Write R script to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.R', delete=False) as f:
            f.write(r_script)
            script_path = f.name

        try:
            # Run R script
            result = subprocess.run(
                ['Rscript', script_path],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                self.logger.error(f"R error: {result.stderr}")
                return []

            # Parse JSON output
            try:
                data = json.loads(result.stdout)
                if isinstance(data, list):
                    return data
                return []
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON parse error: {e}")
                return []

        finally:
            os.unlink(script_path)

    def transform(self, raw_data: Dict) -> Dict:
        """
        Transform GIFT data to internal schema.

        Args:
            raw_data: Raw trait data from GIFT

        Returns:
            Transformed data matching database schema
        """
        species_name = raw_data.get('work_species', '') or raw_data.get('species', '')

        if not species_name:
            return {}

        transformed = {
            'canonical_name': self._clean_species_name(species_name),
            'gift_work_id': raw_data.get('work_ID'),
            'taxonomic_status': 'accepted',
        }

        # Extract genus
        parts = transformed['canonical_name'].split()
        if parts:
            transformed['genus'] = parts[0]

        # Build traits
        trait_name = raw_data.get('_trait_name', '')
        trait_value = raw_data.get('trait_value')

        traits = {}

        if trait_name == 'growth_form' and trait_value:
            traits['growth_form'] = self._normalize_growth_form(trait_value)
        elif trait_name == 'climber_type' and trait_value:
            if trait_value.lower() not in ['self-supporting', 'self supporting']:
                traits['growth_form'] = 'climber'
        elif trait_name == 'max_height' and trait_value:
            try:
                traits['max_height_m'] = float(trait_value)
            except (ValueError, TypeError):
                pass
        elif trait_name == 'woodiness' and trait_value:
            traits['woodiness'] = trait_value.lower()
        elif trait_name == 'nitrogen_fixer' and trait_value:
            traits['nitrogen_fixer'] = trait_value.lower() in ['yes', 'true', '1']
        elif trait_name == 'dispersal_syndrome' and trait_value:
            traits['dispersal_syndrome'] = trait_value
        elif trait_name == 'life_form' and trait_value:
            traits['life_form'] = trait_value

        if traits:
            transformed['traits'] = traits

        return transformed

    def _clean_species_name(self, name: str) -> str:
        """Clean species name."""
        if not name:
            return ''

        # Remove subspecies, varieties, authors
        parts = name.strip().split()
        if len(parts) >= 2:
            return f"{parts[0]} {parts[1]}"
        return name.strip()

    def _normalize_growth_form(self, form: str) -> str:
        """Normalize growth form values."""
        form = form.lower().strip()

        growth_form_map = {
            'tree': 'tree',
            'shrub': 'shrub',
            'subshrub': 'shrub',
            'herb': 'herb',
            'herbaceous': 'herb',
            'grass': 'herb',
            'graminoid': 'herb',
            'climber': 'climber',
            'vine': 'climber',
            'liana': 'climber',
            'palm': 'palm',
            'fern': 'fern',
            'bamboo': 'bamboo',
            'succulent': 'succulent',
            'aquatic': 'aquatic',
            'epiphyte': 'epiphyte',
        }

        for key, value in growth_form_map.items():
            if key in form:
                return value

        return form

    def get_species_by_region(self, region_id: int) -> List[Dict]:
        """
        Get species list for a GIFT region.

        Args:
            region_id: GIFT region ID

        Returns:
            List of species in the region
        """
        if not self._r_available:
            return []

        r_script = f'''
        library(GIFT)
        library(jsonlite)

        species <- GIFT_species(GIFT_version = "3.0", entity_ID = {region_id})
        json_data <- toJSON(species, auto_unbox = TRUE)
        cat(json_data)
        '''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.R', delete=False) as f:
            f.write(r_script)
            script_path = f.name

        try:
            result = subprocess.run(
                ['Rscript', script_path],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0:
                return json.loads(result.stdout)

        except Exception as e:
            self.logger.error(f"Error fetching species by region: {e}")

        finally:
            os.unlink(script_path)

        return []

    def get_available_traits(self) -> List[Dict]:
        """Get list of available traits in GIFT."""
        if not self._r_available:
            return []

        r_script = '''
        library(GIFT)
        library(jsonlite)

        traits <- GIFT_traits_meta()
        json_data <- toJSON(traits, auto_unbox = TRUE)
        cat(json_data)
        '''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.R', delete=False) as f:
            f.write(r_script)
            script_path = f.name

        try:
            result = subprocess.run(
                ['Rscript', script_path],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                return json.loads(result.stdout)

        except Exception as e:
            self.logger.error(f"Error fetching traits meta: {e}")

        finally:
            os.unlink(script_path)

        return []
