"""GIFT (Global Inventory of Floras and Traits) crawler.

Implements growth form determination logic based on Climber.R (Renata Rodrigues Lucas).
See docs/gift.md for detailed documentation on the priority rules.
"""
from typing import Generator, Dict, Any, List, Optional
import subprocess
import json
import tempfile
import os
from collections import defaultdict
from .base import BaseCrawler


class GIFTCrawler(BaseCrawler):
    """
    Crawler for Global Inventory of Floras and Traits.

    Uses the GIFT R package via rpy2 or subprocess.
    Coverage: ~350,000 species with functional traits
    Traits: growth_form, height, dispersal, nitrogen fixation, etc.

    Growth form determination follows Climber.R logic:
    - liana/vine always take priority over trait_1.2.2
    - self-supporting defers to trait_1.2.2
    - herb is normalized to forb
    """

    name = 'gift'

    # GIFT trait IDs for the traits we need
    # Reference: https://gift.uni-goettingen.de/
    TRAIT_IDS = {
        'growth_form': '1.2.2',      # Primary growth form (tree, shrub, herb, etc.)
        'climber_type': '1.4.2',     # Climber classification (liana, vine, self-supporting)
        'dispersal_syndrome': '3.3.1',
        'nitrogen_fixer': '4.5.1',
        'max_height': '3.1.1',
        'life_form': '1.1.1',
    }

    # Valid growth form values after normalization (aligned with Climber.R)
    VALID_GROWTH_FORMS = {
        'tree', 'shrub', 'subshrub', 'palm', 'liana', 'vine',
        'forb', 'graminoid', 'fern', 'bamboo', 'succulent',
        'aquatic', 'epiphyte', 'other'
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
        # Create R script with output to temp file to avoid progress bar interference
        output_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        output_path = output_file.name
        output_file.close()

        r_script = f'''
        suppressPackageStartupMessages(library(GIFT))
        suppressPackageStartupMessages(library(jsonlite))

        # Fetch trait data (suppress messages)
        traits <- suppressMessages(GIFT_traits(trait_IDs = "{trait_id}"))

        # Write JSON to file to avoid stdout pollution from progress bars
        json_data <- toJSON(traits, auto_unbox = TRUE)
        writeLines(json_data, "{output_path}")
        cat("OK")
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
                timeout=600  # GIFT queries can take a while
            )

            if result.returncode != 0:
                self.logger.error(f"R error: {result.stderr}")
                return []

            # Read JSON from output file
            try:
                with open(output_path, 'r') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self.logger.info(f"Fetched {len(data)} records for trait")
                    return data
                return []
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON parse error: {e}")
                return []
            except FileNotFoundError:
                self.logger.error("R script did not produce output file")
                return []

        finally:
            os.unlink(script_path)
            if os.path.exists(output_path):
                os.unlink(output_path)

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
        # GIFT columns are named trait_value_X.X.X (e.g., trait_value_1.2.2)
        trait_id = self.TRAIT_IDS.get(trait_name, '')
        trait_value = raw_data.get(f'trait_value_{trait_id}') or raw_data.get('trait_value')

        traits = {}

        if trait_name == 'growth_form' and trait_value:
            # Store raw value; will be combined with climber_type later
            traits['_raw_growth_form'] = str(trait_value).lower().strip()
        elif trait_name == 'climber_type' and trait_value:
            # Store raw value; will be combined with growth_form later
            traits['_raw_climber_type'] = str(trait_value).lower().strip()
        elif trait_name == 'max_height' and trait_value:
            try:
                traits['max_height_m'] = float(trait_value)
            except (ValueError, TypeError):
                pass
        elif trait_name == 'nitrogen_fixer' and trait_value:
            traits['nitrogen_fixer'] = trait_value.lower() in ['yes', 'true', '1']
        elif trait_name == 'dispersal_syndrome' and trait_value:
            traits['dispersal_syndrome'] = trait_value
        elif trait_name == 'life_form' and trait_value:
            traits['life_form'] = trait_value

        if traits:
            transformed['traits'] = traits

        return transformed

    def determine_growth_form(
        self,
        trait_1_4_2: Optional[str],
        trait_1_2_2: Optional[str]
    ) -> str:
        """
        Determine growth_form based on Climber.R logic (Renata Rodrigues Lucas).

        Priority rules:
        1. liana (trait_1.4.2) ALWAYS takes priority → "liana"
        2. vine (trait_1.4.2) ALWAYS takes priority → "vine"
        3. self-supporting (trait_1.4.2) defers to trait_1.2.2
        4. NA (trait_1.4.2) defers to trait_1.2.2
        5. herb is normalized to forb

        Args:
            trait_1_4_2: Value from GIFT trait_value_1.4.2 (climber type)
            trait_1_2_2: Value from GIFT trait_value_1.2.2 (growth form)

        Returns:
            Normalized growth form value

        Reference:
            docs/gift.md - Complete documentation of the logic
        """
        # Normalize inputs
        climber = trait_1_4_2.lower().strip() if trait_1_4_2 else None
        growth = trait_1_2_2.lower().strip() if trait_1_2_2 else None

        # Normalize herb → forb
        if growth == 'herb':
            growth = 'forb'
        elif growth == 'herbaceous':
            growth = 'forb'

        # Rule 1: liana ALWAYS takes priority (woody climber)
        if climber == 'liana':
            return 'liana'

        # Rule 2: vine ALWAYS takes priority (herbaceous climber)
        if climber == 'vine':
            return 'vine'

        # Rule 3: self-supporting defers to trait_1.2.2
        if climber == 'self-supporting':
            if growth:
                return self._normalize_growth_form_value(growth)
            return 'other'

        # Rule 4: When climber_type is None/NA, use growth_form
        if climber is None:
            if growth:
                return self._normalize_growth_form_value(growth)
            return 'other'

        # Fallback: use climber_type if it has a value
        if climber:
            return self._normalize_growth_form_value(climber)

        return 'other'

    def _normalize_growth_form_value(self, value: str) -> str:
        """
        Normalize a single growth form value to standard categories.

        Aligned with Climber.R output values.

        Args:
            value: Raw growth form value

        Returns:
            Normalized value from VALID_GROWTH_FORMS
        """
        if not value:
            return 'other'

        value = value.lower().strip()

        # Direct mappings
        direct_map = {
            'tree': 'tree',
            'shrub': 'shrub',
            'subshrub': 'subshrub',
            'palm': 'palm',
            'liana': 'liana',
            'vine': 'vine',
            'forb': 'forb',
            'herb': 'forb',           # herb → forb (Climber.R)
            'herbaceous': 'forb',     # herbaceous → forb
            'graminoid': 'graminoid',
            'grass': 'graminoid',     # grass → graminoid
            'fern': 'fern',
            'bamboo': 'bamboo',
            'succulent': 'succulent',
            'aquatic': 'aquatic',
            'epiphyte': 'epiphyte',
            'other': 'other',
        }

        if value in direct_map:
            return direct_map[value]

        # Partial matching for edge cases
        for key, normalized in direct_map.items():
            if key in value:
                return normalized

        return 'other'

    def combine_species_traits(self, species_data: Dict[str, Dict]) -> Generator[Dict, None, None]:
        """
        Combine growth_form and climber_type for each species using Climber.R logic.

        This method should be called after fetching both trait_1.2.2 and trait_1.4.2
        to properly determine the final growth_form.

        Args:
            species_data: Dict mapping species name to trait data

        Yields:
            Combined species records with determined growth_form
        """
        for species_name, data in species_data.items():
            trait_1_2_2 = data.get('_raw_growth_form')
            trait_1_4_2 = data.get('_raw_climber_type')

            # Determine final growth_form using Climber.R logic
            final_growth_form = self.determine_growth_form(trait_1_4_2, trait_1_2_2)

            # Build output record
            result = {
                'canonical_name': species_name,
                'gift_work_id': data.get('gift_work_id'),
                'genus': data.get('genus'),
                'taxonomic_status': 'accepted',
                'traits': {
                    'growth_form': final_growth_form,
                    'source': 'gift',
                }
            }

            # Add other traits if present
            for key in ['max_height_m', 'nitrogen_fixer', 'dispersal_syndrome', 'life_form']:
                if key in data:
                    result['traits'][key] = data[key]

            # Store raw values for debugging/audit
            if trait_1_2_2:
                result['traits']['_gift_trait_1_2_2'] = trait_1_2_2
            if trait_1_4_2:
                result['traits']['_gift_trait_1_4_2'] = trait_1_4_2

            yield result

    def _clean_species_name(self, name: str) -> str:
        """Clean species name."""
        if not name:
            return ''

        # Remove subspecies, varieties, authors
        parts = name.strip().split()
        if len(parts) >= 2:
            return f"{parts[0]} {parts[1]}"
        return name.strip()


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

    def run(self, mode: str = 'incremental', **kwargs) -> None:
        """
        Run the GIFT crawler with full Climber.R logic.

        Overrides BaseCrawler.run() to use the proper trait combination logic.
        """
        return self.run_with_climber_logic(mode)

    def run_with_climber_logic(self, mode: str = 'incremental') -> None:
        """
        Run the GIFT crawler with full Climber.R logic.

        This method:
        1. Fetches trait_1.2.2 (growth_form) and trait_1.4.2 (climber_type)
        2. Combines them per species using determine_growth_form()
        3. Saves to database with the properly determined growth_form

        Args:
            mode: 'full' or 'incremental'
        """
        self._log_start()

        try:
            # Collect all species data
            species_data: Dict[str, Dict] = defaultdict(dict)

            # Fetch growth_form (1.2.2) and climber_type (1.4.2)
            for trait_name in ['growth_form', 'climber_type']:
                self.logger.info(f"Fetching {trait_name}...")

                for raw_record in self.fetch_data(mode=mode, traits=[trait_name]):
                    transformed = self.transform(raw_record)
                    if not transformed:
                        continue

                    species_name = transformed['canonical_name']
                    traits = transformed.get('traits', {})

                    # Merge into species_data
                    if 'gift_work_id' not in species_data[species_name]:
                        species_data[species_name]['gift_work_id'] = transformed.get('gift_work_id')
                        species_data[species_name]['genus'] = transformed.get('genus')

                    species_data[species_name].update(traits)

            self.logger.info(f"Combining traits for {len(species_data)} species...")

            # Combine traits using Climber.R logic and save
            for record in self.combine_species_traits(species_data):
                self._save(record)
                self.stats['processed'] += 1

            self._log_success()

        except Exception as e:
            self._log_error(str(e))
            raise
