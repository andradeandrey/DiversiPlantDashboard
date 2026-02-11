"""WCVP (World Checklist of Vascular Plants) crawler.

Supports two CSV formats:
  - Legacy (sftp.kew.org/WCVP/wcvp.zip): wcvp_names.csv with columns
    plant_name_id, taxon_status, taxon_rank, taxon_name, lifeform_description, etc.
  - Darwin Core Archive (data/wcvp/): wcvp_taxon.csv with columns
    taxonid, taxonomicstatus, taxonrank, scientfiicname, dynamicproperties, etc.
"""
from typing import Generator, Dict, Any, Optional
import json
import requests
import zipfile
import csv
import io
import os
import sys
import tempfile
from sqlalchemy import text
from sqlalchemy.orm import Session
from .base import BaseCrawler

# Increase CSV field size limit for large WCVP fields
csv.field_size_limit(sys.maxsize)

# Column mappings for the two known WCVP CSV formats
# Legacy format: downloaded from sftp.kew.org (wcvp_names.csv)
LEGACY_COLS = {
    'names_file': 'wcvp_names.csv',
    'taxon_id': 'plant_name_id',
    'taxon_status': 'taxon_status',
    'taxon_rank': 'taxon_rank',
    'taxon_name': 'taxon_name',
    'genus': 'genus',
    'family': 'family',
    'accepted_id': 'accepted_plant_name_id',
    'lifeform': 'lifeform_description',
    'climate': 'climate_description',
    # Distribution columns
    'dist_taxon_id': 'plant_name_id',
    'dist_tdwg': 'area_code_l3',
    'dist_introduced_check': lambda row: row.get('introduced') == '1',
    'dist_doubtful_check': lambda row: row.get('location_doubtful') == '1',
    'dist_extinct_check': lambda row: row.get('extinct') == '1',
    'dist_endemic_check': lambda row: row.get('endemic', '0'),
}

# Darwin Core Archive format: from POWO/WCVP DwC-A download (wcvp_taxon.csv)
DWC_COLS = {
    'names_file': 'wcvp_taxon.csv',
    'taxon_id': 'taxonid',
    'taxon_status': 'taxonomicstatus',
    'taxon_rank': 'taxonrank',
    'taxon_name': 'scientfiicname',  # Note: typo in WCVP data (double 'i')
    'genus': 'genus',
    'family': 'family',
    'accepted_id': 'acceptednameusageid',
    'lifeform': None,  # Stored in dynamicproperties JSON
    'climate': None,    # Stored in dynamicproperties JSON
    'dynamicproperties': 'dynamicproperties',
    # Distribution columns
    'dist_taxon_id': 'coreid',
    'dist_tdwg': 'locationid',  # Has TDWG: prefix
    'dist_tdwg_prefix': 'TDWG:',
    'dist_introduced_check': lambda row: (row.get('establishmentmeans') or '').lower() == 'introduced',
    'dist_doubtful_check': lambda row: (row.get('occurrencestatus') or '').lower() == 'doubtful',
    'dist_extinct_check': lambda row: (row.get('threatstatus') or '').lower() == 'extinct',
    'dist_endemic_check': lambda _row: '0',
}


class WCVPCrawler(BaseCrawler):
    """
    Crawler for World Checklist of Vascular Plants.

    Source: Royal Botanic Gardens, Kew
    Coverage: ~350,000 accepted vascular plant species
    Data: Taxonomic backbone, distribution, synonyms

    Auto-detects CSV format (legacy vs Darwin Core Archive).
    """

    name = 'wcvp'

    DOWNLOAD_URL = 'https://sftp.kew.org/pub/data-repositories/WCVP/'
    DISTRIBUTION_FILE = 'wcvp_distribution.csv'

    def __init__(self, db_url: str):
        super().__init__(db_url)
        self.session = requests.Session()
        self._data_dir: Optional[str] = None
        self._cols: Dict = {}  # Active column mapping

    def _detect_format(self, data_dir: str) -> Dict:
        """
        Auto-detect CSV format by checking which names file exists
        and reading its header.
        """
        for fmt in [DWC_COLS, LEGACY_COLS]:
            names_file = os.path.join(data_dir, fmt['names_file'])
            if os.path.exists(names_file):
                # Verify by reading header
                with open(names_file, 'r', encoding='utf-8') as f:
                    header = f.readline().strip()
                    if fmt['taxon_id'] in header.split('|'):
                        self.logger.info(
                            f"Detected format: {'DwC-A' if fmt is DWC_COLS else 'Legacy'} "
                            f"(file: {fmt['names_file']})"
                        )
                        return fmt

        # Fallback: try legacy
        self.logger.warning("Could not auto-detect format, falling back to legacy")
        return LEGACY_COLS

    def fetch_data(self, mode='incremental', **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        Fetch species data from WCVP.

        Args:
            mode: 'full' or 'incremental'
            **kwargs: data_path (local dir), max_records (int)

        Yields:
            Species data rows
        """
        data_path = kwargs.get('data_path', None)
        max_records = kwargs.get('max_records', None)

        if data_path and os.path.exists(data_path):
            self._data_dir = data_path
        else:
            self._data_dir = self._download_data()

        if not self._data_dir:
            self.logger.error("Failed to obtain WCVP data")
            return

        # Auto-detect format
        self._cols = self._detect_format(self._data_dir)

        names_file = os.path.join(self._data_dir, self._cols['names_file'])
        if not os.path.exists(names_file):
            self.logger.error(f"Names file not found: {names_file}")
            return

        self.logger.info(f"Processing WCVP names from: {names_file}")
        count = 0

        with open(names_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='|')

            for row in reader:
                if row.get(self._cols['taxon_status']) != 'Accepted':
                    continue
                if row.get(self._cols['taxon_rank']) != 'Species':
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
        cache_dir = os.path.join(tempfile.gettempdir(), 'wcvp_cache')

        # Check for either format's names file
        for fname in ['wcvp_taxon.csv', 'wcvp_names.csv']:
            if os.path.exists(os.path.join(cache_dir, fname)):
                self.logger.info("Using cached WCVP data")
                return cache_dir

        self.logger.info("Downloading WCVP data...")

        try:
            zip_url = f"{self.DOWNLOAD_URL}wcvp.zip"
            response = self.session.get(zip_url, stream=True, timeout=300)
            response.raise_for_status()

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
        Handles both legacy and DwC-A formats.
        """
        cols = self._cols

        transformed = {
            'canonical_name': raw_data.get(cols['taxon_name'], ''),
            'genus': raw_data.get(cols['genus'], ''),
            'family': raw_data.get(cols['family'], ''),
            'wcvp_id': raw_data.get(cols['taxon_id']),
            'taxonomic_status': 'accepted',
        }

        traits = {}

        family = raw_data.get(cols['family'], '')

        # Extract lifeform/climate — depends on format
        if cols.get('dynamicproperties'):
            # DwC-A format: traits in JSON dynamicproperties
            dynamic_props = raw_data.get(cols['dynamicproperties'], '')
            if dynamic_props:
                try:
                    props = json.loads(dynamic_props)
                    life_form = props.get('lifeform', '')
                    if life_form:
                        traits['growth_form'] = self._classify_growth_form(life_form, family)
                        traits['life_form'] = life_form
                    climate = props.get('climate', '')
                    if climate:
                        traits['climate'] = climate
                except (json.JSONDecodeError, TypeError):
                    pass
        else:
            # Legacy format: traits in dedicated columns
            life_form = raw_data.get(cols['lifeform'], '')
            if life_form:
                traits['growth_form'] = self._classify_growth_form(life_form, family)
                traits['life_form'] = life_form

        if traits:
            transformed['traits'] = traits

        return transformed

    # Families whose herbaceous members should be classified as graminoid
    _GRAMINOID_FAMILIES = frozenset({'Poaceae', 'Cyperaceae', 'Juncaceae', 'Typhaceae'})

    # Layer 1: Direct mappings (no family condition needed)
    _DIRECT_MAP = {
        # Epiphytes → other
        'epiphyte': 'other',
        'hemiepiphyte': 'other',
        'pseudobulbous epiphyte': 'other',
        'hemiparasitic epiphyte': 'other',
        'epiphyte or lithophyte': 'other',
        'pseudobulbous epiphyte or lithophyte': 'other',
        'succulent epiphyte': 'other',
        'epiphytic shrub': 'other',
        'epiphytic rhizomatous subshrub': 'other',
        'subshrub or epiphyte': 'other',
        'pseudobulbous geophyte or epiphyte': 'other',
        # Unusual/hybrid forms → other
        'rheophyte': 'other',
        'myco-heterotroph': 'other',
        'parasite': 'other',
        'saprophyte': 'other',
        'free-floating aquatic': 'other',
        'submerged aquatic': 'other',
        'carnivorous': 'other',
        'herbaceous tree': 'other',
        'climbing herbaceous tree': 'other',
        'holoparasitic perennial': 'other',
        'holomycotrophic rhizomatous geophyte': 'other',
        'scrambling shrub or liana': 'other',
        'shrub or liana': 'other',
        'scrambling perennial or subshrub': 'other',
        # Shrub-or-tree variants with no height data → other (xlsx fallback)
        'succulent shrub or tree': 'other',
        'tuberous shrub or tree': 'other',
        # Scramblers
        'scrambler': 'scrambler',
        'scrambling shrub': 'scrambler',
        'scrambling subshrub': 'scrambler',
        'scrambling succulent shrub': 'scrambler',
        'scrambling tuberous geophyte': 'scrambler',
        'scrambling shrub or tree': 'scrambler',
        'scrambling subshrub or shrub': 'scrambler',
        'scrambling tree': 'scrambler',
        'scrambling perennial': 'scrambler',
        'scrambling rhizomatous geophyte': 'scrambler',
        # Climbing woody → liana
        'climbing shrub': 'liana',
        'climbing subshrub': 'liana',
        'climbing succulent shrub': 'liana',
        'climbing shrub or liana': 'liana',
        'climbing shrub or tree': 'liana',
        # Climbing non-woody → vine
        'climbing annual': 'vine',
        # Trees
        'tree': 'tree',
        'succulent tree': 'tree',
        # Shrubs (including tuberous/succulent)
        'shrub': 'shrub',
        'succulent shrub': 'shrub',
        'tuberous shrub': 'shrub',
        'hemiepiphytic shrub': 'shrub',
        'perennial or shrub': 'shrub',
        # Subshrubs
        'subshrub': 'subshrub',
        'succulent subshrub': 'subshrub',
        'epiphytic subshrub': 'subshrub',
        'epiphytic caudex subshrub': 'subshrub',
        'tuberous subshrub': 'subshrub',
        'succulent tuberous subshrub': 'subshrub',
        'hydrophytic subshrub': 'subshrub',
        'hydrosubshrub': 'subshrub',
        'semisucculent subshrub': 'subshrub',
        # Bamboo
        'bamboo': 'bamboo',
        'herbaceous bamboo': 'bamboo',
        # Forb-like specifics
        'pseudobulbous lithophyte': 'forb',
    }

    # Layer 2: Lifeforms resolved by family (graminoid if grass family, else forb)
    _FAMILY_CONDITIONAL = frozenset({
        'annual',
        'biennial',
        'tuberous geophyte',
        'bulbous geophyte',
        'rhizomatous geophyte',
        'corm geophyte',
        'helophyte',
        'hydroannual',
        'hemiparasitic annual',
        'holoparasitic annual',
        'semisucculent perennial',
        'succulent annual',
        'succulent biennial',
        'annual or biennial',
        'perennial or rhizomatous geophyte',
        'perennial or tuberous geophyte',
        'perennial or bulbous geophyte',
        'perennial or corm geophyte',
        # Moved from _DIRECT_MAP — xlsx says family-conditional
        'lithophyte',
        'holoparasite',
        # Compound forms — without woodiness data, default to family-conditional
        'subshrub or perennial',
        'annual, perennial or subshrub',
        'epiphytic perennial or subshrub',
    })

    # Layer 3: Complex conditionals — fixed defaults (no height/woodiness data)
    # Sub-group A: herbaceous perennials → graminoid/forb by family
    _PERENNIAL_HERBS = frozenset({
        'perennial',
        'monocarpic perennial',
        'hydroperennial',
        'hemiparasitic perennial',
        'succulent perennial',
        'tuberous perennial',
        'perennial or subshrub',
        'annual or subshrub',
        'biennial or subshrub',
        'annual or perennial',
        'perennial or annual',
        'annual or biennial or perennial',
    })

    # Sub-group B: shrub-or-tree ambiguous → default shrub (conservative)
    _SHRUB_OR_TREE = frozenset({
        'shrub or tree',
    })

    # Sub-group C: subshrub-or-shrub ambiguous → default subshrub (conservative)
    _SUBSHRUB_OR_SHRUB = frozenset({
        'subshrub or shrub',
        'succulent subshrub or shrub',
        'semisucculent subshrub or shrub',
    })

    # Sub-group D: climbers without clear woodiness → default vine (GIFT corrects to liana if woody)
    _CLIMBER_DEFAULTS = frozenset({
        'climber',
        'climbing perennial',
        'climbing tuberous geophyte',
        'climbing caudex geophyte',
        'climbing epiphyte',
    })

    def _classify_growth_form(self, life_form: str, family: str) -> str:
        """
        Classify WCVP lifeform into one of 11 standardized growth forms.

        Uses Renata's 96-rule mapping table with 3-layer logic:
          - Rule 0: Family override (Arecaceae → palm)
          - Layer 1: Direct mappings (~40 lifeforms)
          - Layer 2: Family-conditional (graminoid vs forb)
          - Layer 3: Complex conditionals with conservative defaults

        Always returns a value (never None).

        Args:
            life_form: WCVP lifeform_description (e.g. "perennial", "climbing shrub")
            family: Taxonomic family (e.g. "Poaceae", "Fabaceae")

        Returns:
            One of: graminoid, forb, subshrub, shrub, tree, scrambler, vine, liana, palm, bamboo, other
        """
        lf = life_form.strip().lower()
        is_grass = family in self._GRAMINOID_FAMILIES

        # Rule 0: Family overrides (general priority from xlsx)
        if family == 'Arecaceae':
            return 'palm'
        if family in ('Cyperaceae', 'Juncaceae', 'Typhaceae'):
            return 'graminoid'

        # Layer 1: Direct map
        if lf in self._DIRECT_MAP:
            return self._DIRECT_MAP[lf]

        # Layer 2: Family-conditional (graminoid vs forb)
        if lf in self._FAMILY_CONDITIONAL:
            return 'graminoid' if is_grass else 'forb'

        # Layer 3A: Perennial herbs → graminoid/forb by family
        if lf in self._PERENNIAL_HERBS:
            return 'graminoid' if is_grass else 'forb'

        # Layer 3B: Shrub or tree → shrub (conservative)
        if lf in self._SHRUB_OR_TREE:
            return 'shrub'

        # Layer 3C: Subshrub or shrub → subshrub (conservative)
        if lf in self._SUBSHRUB_OR_SHRUB:
            return 'subshrub'

        # Layer 3D: Climbers without woodiness info → vine (GIFT corrects later)
        if lf in self._CLIMBER_DEFAULTS:
            return 'vine'

        # Layer 4: Keyword-based fallback for compound lifeforms not in exact maps
        # Order matters: more specific keywords first
        if 'bamboo' in lf:
            return 'bamboo'
        if lf.startswith('scrambling '):
            return 'scrambler'
        if lf.startswith('climbing ') or lf.startswith('epiphytic climbing ') or lf.endswith(' climber'):
            # Woody climbing → liana, otherwise → vine
            if 'shrub' in lf or 'tree' in lf or 'liana' in lf:
                return 'liana'
            return 'vine'
        if 'climber' in lf:
            return 'vine'
        if 'liana' in lf:
            return 'liana'
        if ' tree' in lf or lf.startswith('tree'):
            return 'tree'
        if 'subshrub' in lf:
            return 'subshrub'
        if 'shrub' in lf:
            return 'shrub'
        # Herbaceous/geophyte forms
        if any(kw in lf for kw in ('annual', 'biennial', 'perennial',
                                    'geophyte', 'helophyte', 'hydro')):
            return 'graminoid' if is_grass else 'forb'
        # Epiphytes, lithophytes, parasites, mycotrophs, aquatics
        if any(kw in lf for kw in ('epiphyt', 'lithophyt', 'parasit',
                                    'mycotroph', 'aquatic', 'saprophyt')):
            return 'other'

        # Final fallback: unrecognized lifeform
        return 'other'

    def _read_dist_row(self, row: Dict) -> Optional[Dict]:
        """
        Parse a distribution CSV row using the active column mapping.
        Returns None if the row should be skipped.
        """
        cols = self._cols

        taxon_id = row.get(cols['dist_taxon_id'])
        raw_tdwg = row.get(cols['dist_tdwg'], '')

        # Strip TDWG: prefix if present (DwC-A format)
        prefix = cols.get('dist_tdwg_prefix', '')
        tdwg_code = raw_tdwg.replace(prefix, '') if prefix and raw_tdwg else raw_tdwg

        if not taxon_id or not tdwg_code:
            return None

        # Skip doubtful occurrences
        if cols['dist_doubtful_check'](row):
            return None

        is_introduced = cols['dist_introduced_check'](row)
        is_extinct = cols['dist_extinct_check'](row)
        endemic_val = cols['dist_endemic_check'](row)

        return {
            'taxon_id': taxon_id,
            'tdwg_code': tdwg_code,
            'establishment_means': 'introduced' if is_introduced else 'native',
            'endemic': endemic_val if isinstance(endemic_val, str) else ('1' if endemic_val else '0'),
            'introduced': '1' if is_introduced else '0',
        }

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

        cols = self._cols

        with open(dist_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='|')

            for row in reader:
                parsed = self._read_dist_row(row)
                if not parsed:
                    continue

                is_introduced = parsed['introduced'] == '1'
                yield {
                    'wcvp_id': parsed['taxon_id'],
                    'tdwg_code': parsed['tdwg_code'],
                    'native': not is_introduced,
                    'introduced': is_introduced,
                    'doubtful': False,  # Already filtered out
                    'extinct': cols['dist_extinct_check'](row),
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

        if not self._data_dir or not self._cols:
            return synonyms

        cols = self._cols
        names_file = os.path.join(self._data_dir, cols['names_file'])

        with open(names_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='|')

            for row in reader:
                if row.get(cols['accepted_id']) == wcvp_id:
                    if row.get(cols['taxon_status']) == 'Synonym':
                        synonyms.append(row.get(cols['taxon_name']))

        return synonyms

    def run(self, mode: str = 'incremental', **kwargs):
        """
        Execute the crawler with distribution data.

        Args:
            mode: 'full' for complete refresh, 'incremental' for updates only
            **kwargs: Additional arguments (data_path, max_records, skip_distribution)
        """
        # First run the base crawler for species data
        super().run(mode=mode, **kwargs)

        # Then process distribution data
        if kwargs.get('skip_distribution', False):
            self.logger.info("Skipping distribution data (skip_distribution=True)")
            return

        self.logger.info("Processing WCVP distribution data...")
        self._save_distribution_data()

    def _save_distribution_data(self):
        """
        Save distribution data to wcvp_distribution table.
        """
        if not self._data_dir:
            self.logger.error("Data directory not set, cannot process distribution")
            return

        dist_file = os.path.join(self._data_dir, self.DISTRIBUTION_FILE)
        if not os.path.exists(dist_file):
            self.logger.warning(f"Distribution file not found: {dist_file}")
            return

        self.logger.info(f"Processing distribution from: {dist_file}")

        dist_count = 0
        skipped = 0
        batch_size = 10000
        batch = []

        with open(dist_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='|')

            for row in reader:
                parsed = self._read_dist_row(row)
                if not parsed:
                    skipped += 1
                    continue

                batch.append(parsed)

                if len(batch) >= batch_size:
                    self._save_distribution_batch(batch)
                    dist_count += len(batch)
                    self.logger.info(f"Distribution progress: {dist_count} records")
                    batch = []

            # Save remaining batch
            if batch:
                self._save_distribution_batch(batch)
                dist_count += len(batch)

        self.logger.info(f"Completed distribution: {dist_count} records saved, {skipped} skipped")

    def _save_distribution_batch(self, batch: list):
        """Save a batch of distribution records."""
        with Session(self.engine) as session:
            for record in batch:
                try:
                    session.execute(
                        text("""
                            INSERT INTO wcvp_distribution
                                (taxon_id, tdwg_code, establishment_means, endemic, introduced)
                            VALUES
                                (:taxon_id, :tdwg_code, :establishment_means, :endemic, :introduced)
                            ON CONFLICT (taxon_id, tdwg_code) DO UPDATE SET
                                establishment_means = EXCLUDED.establishment_means,
                                endemic = EXCLUDED.endemic,
                                introduced = EXCLUDED.introduced
                        """),
                        record
                    )
                except Exception as e:
                    self.logger.debug(f"Error saving distribution: {e}")

            session.commit()
