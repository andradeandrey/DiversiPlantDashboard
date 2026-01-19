"""
Taxonomic Disambiguation Module for DiversiPlant.

Uses WorldFlora (WFO) as primary source and WCVP as fallback
to resolve species names to accepted taxonomic names.

Author: Stickybit <dev@stickybit.com.br>
"""
import subprocess
import json
import tempfile
import os
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# Try to import rpy2 for faster processing
try:
    import rpy2.robjects as ro
    from rpy2.robjects import pandas2ri
    from rpy2.robjects.packages import importr
    HAS_RPY2 = True
except ImportError:
    HAS_RPY2 = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("crawler.disambiguation")

# Path to WFO backbone data
WFO_BACKBONE_PATH = Path(__file__).parent.parent / "data" / "wfo" / "classification.csv"

# R script template for WFO matching
WFO_MATCH_SCRIPT = '''
library(WorldFlora)
library(jsonlite)

# Load backbone
WFO.data <- read.table("{backbone_path}", sep="\\t", header=TRUE, quote="\\"",
                       fill=TRUE, stringsAsFactors=FALSE, encoding="UTF-8")

# Read species names from input file
species_names <- readLines("{input_file}")

# Match against WFO
result <- WFO.match(spec.data = species_names, WFO.data = WFO.data,
                    Fuzzy.max = 0.1, verbose = FALSE)

# Select relevant columns
output <- result[, c("spec.name.ORIG", "scientificName", "taxonID",
                     "taxonomicStatus", "acceptedNameUsageID", "family",
                     "genus", "specificEpithet", "Matched", "Fuzzy", "Fuzzy.dist")]

# Write JSON output
write(toJSON(output, na="null"), "{output_file}")
'''


class TaxonomicDisambiguator:
    """
    Handles taxonomic name resolution using WFO and WCVP.

    Priority:
    1. WorldFlora Online (WFO) - primary source
    2. WCVP data in database - fallback for unmatched
    """

    def __init__(self, db_url: str):
        """Initialize with database connection."""
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)
        self.stats = {
            'total': 0,
            'wfo_matched': 0,
            'wfo_fuzzy': 0,
            'wcvp_matched': 0,
            'unmatched': 0,
            'errors': 0
        }

        # Verify WFO backbone exists
        if not WFO_BACKBONE_PATH.exists():
            raise FileNotFoundError(
                f"WFO backbone not found at {WFO_BACKBONE_PATH}. "
                "Please download from https://www.worldfloraonline.org/downloadData"
            )

        logger.info(f"Using WFO backbone: {WFO_BACKBONE_PATH}")

    def disambiguate_batch(self, species_names: List[str], batch_size: int = 1000) -> List[Dict]:
        """
        Disambiguate a batch of species names.

        Args:
            species_names: List of scientific names to resolve
            batch_size: Number of names to process at once

        Returns:
            List of dicts with disambiguation results
        """
        results = []

        for i in range(0, len(species_names), batch_size):
            batch = species_names[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1} ({len(batch)} names)")

            # First try WFO
            wfo_results = self._match_wfo(batch)

            # Collect unmatched for WCVP fallback
            unmatched = []
            for r in wfo_results:
                if r.get('matched'):
                    results.append(r)
                    if r.get('fuzzy'):
                        self.stats['wfo_fuzzy'] += 1
                    else:
                        self.stats['wfo_matched'] += 1
                else:
                    unmatched.append(r['original_name'])

            # Try WCVP for unmatched
            if unmatched:
                wcvp_results = self._match_wcvp(unmatched)
                for r in wcvp_results:
                    if r.get('matched'):
                        self.stats['wcvp_matched'] += 1
                    else:
                        self.stats['unmatched'] += 1
                    results.append(r)

        self.stats['total'] = len(species_names)
        return results

    def _match_wfo(self, names: List[str]) -> List[Dict]:
        """Match names against WFO using R WorldFlora package."""
        results = []

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f_in:
                f_in.write('\n'.join(names))
                input_file = f_in.name

            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f_out:
                output_file = f_out.name

            # Generate R script
            script = WFO_MATCH_SCRIPT.format(
                backbone_path=str(WFO_BACKBONE_PATH),
                input_file=input_file,
                output_file=output_file
            )

            with tempfile.NamedTemporaryFile(mode='w', suffix='.R', delete=False) as f_script:
                f_script.write(script)
                script_file = f_script.name

            # Execute R script
            result = subprocess.run(
                ['Rscript', script_file],
                capture_output=True,
                text=True,
                timeout=600
            )

            if result.returncode != 0:
                logger.error(f"R script failed: {result.stderr}")
                # Return unmatched for all
                return [{'original_name': n, 'matched': False, 'source': 'wfo'} for n in names]

            # Parse results
            with open(output_file, 'r') as f:
                wfo_data = json.load(f)

            for row in wfo_data:
                matched = row.get('Matched', False)
                results.append({
                    'original_name': row.get('spec.name.ORIG'),
                    'matched': matched,
                    'fuzzy': row.get('Fuzzy', False),
                    'fuzzy_distance': row.get('Fuzzy.dist'),
                    'accepted_name': row.get('scientificName') if matched else None,
                    'wfo_id': row.get('taxonID'),
                    'taxonomic_status': row.get('taxonomicStatus'),
                    'accepted_wfo_id': row.get('acceptedNameUsageID'),
                    'family': row.get('family'),
                    'genus': row.get('genus'),
                    'specific_epithet': row.get('specificEpithet'),
                    'source': 'wfo'
                })

        except subprocess.TimeoutExpired:
            logger.error("WFO matching timed out")
            results = [{'original_name': n, 'matched': False, 'source': 'wfo'} for n in names]
        except Exception as e:
            logger.error(f"WFO matching error: {e}")
            self.stats['errors'] += 1
            results = [{'original_name': n, 'matched': False, 'source': 'wfo'} for n in names]
        finally:
            # Cleanup temp files
            for f in [input_file, output_file, script_file]:
                try:
                    os.unlink(f)
                except:
                    pass

        return results

    def _match_wcvp(self, names: List[str]) -> List[Dict]:
        """Match names against WCVP data in database."""
        results = []

        for name in names:
            matched = False

            # Try exact match first
            with Session(self.engine) as session:
                try:
                    row = session.execute(
                        text("""
                            SELECT id, canonical_name, family, genus, taxonomic_status, wcvp_id
                            FROM species
                            WHERE canonical_name = :name AND wcvp_id IS NOT NULL
                            LIMIT 1
                        """),
                        {'name': name}
                    ).fetchone()

                    if row:
                        results.append({
                            'original_name': name,
                            'matched': True,
                            'fuzzy': False,
                            'accepted_name': row.canonical_name,
                            'wcvp_id': row.wcvp_id,
                            'taxonomic_status': row.taxonomic_status,
                            'family': row.family,
                            'genus': row.genus,
                            'source': 'wcvp'
                        })
                        matched = True

                except Exception as e:
                    logger.debug(f"WCVP exact match error for {name}: {e}")

            if matched:
                continue

            # Try fuzzy match in a separate session (pg_trgm extension required)
            with Session(self.engine) as session:
                try:
                    row = session.execute(
                        text("""
                            SELECT id, canonical_name, family, genus, taxonomic_status, wcvp_id,
                                   similarity(canonical_name, :name) as sim
                            FROM species
                            WHERE wcvp_id IS NOT NULL
                              AND canonical_name % :name
                            ORDER BY sim DESC
                            LIMIT 1
                        """),
                        {'name': name}
                    ).fetchone()

                    if row and row.sim > 0.7:
                        results.append({
                            'original_name': name,
                            'matched': True,
                            'fuzzy': True,
                            'fuzzy_distance': 1 - row.sim,
                            'accepted_name': row.canonical_name,
                            'wcvp_id': row.wcvp_id,
                            'taxonomic_status': row.taxonomic_status,
                            'family': row.family,
                            'genus': row.genus,
                            'source': 'wcvp'
                        })
                        matched = True
                except Exception:
                    # pg_trgm extension not available or other error - skip fuzzy
                    pass

            if not matched:
                results.append({
                    'original_name': name,
                    'matched': False,
                    'source': 'wcvp'
                })

        return results

    def update_species_table(self, results: List[Dict]) -> int:
        """
        Update species table with disambiguation results.

        Adds columns for WFO ID and accepted name reference.

        Returns:
            Number of records updated
        """
        updated = 0

        with Session(self.engine) as session:
            for r in results:
                if not r.get('matched'):
                    continue

                try:
                    # Update species record with disambiguation info
                    if r['source'] == 'wfo':
                        session.execute(
                            text("""
                                UPDATE species
                                SET wfo_id = :wfo_id,
                                    taxonomic_status = COALESCE(taxonomic_status, :status),
                                    family = COALESCE(family, :family),
                                    genus = COALESCE(genus, :genus),
                                    updated_at = NOW()
                                WHERE canonical_name = :name
                            """),
                            {
                                'wfo_id': r.get('wfo_id'),
                                'status': r.get('taxonomic_status', '').lower(),
                                'family': r.get('family'),
                                'genus': r.get('genus'),
                                'name': r['original_name']
                            }
                        )
                    updated += 1

                except Exception as e:
                    logger.warning(f"Failed to update {r['original_name']}: {e}")

            session.commit()

        return updated

    def run_full_disambiguation(self, batch_size: int = 5000) -> Dict:
        """
        Run disambiguation on all species in database.

        Returns:
            Statistics dictionary
        """
        logger.info("Starting full taxonomic disambiguation")

        # Get all species names
        with Session(self.engine) as session:
            rows = session.execute(
                text("SELECT canonical_name FROM species WHERE wfo_id IS NULL ORDER BY canonical_name")
            ).fetchall()

        species_names = [r[0] for r in rows]
        logger.info(f"Found {len(species_names)} species without WFO ID")

        if not species_names:
            logger.info("No species to process")
            return self.stats

        # Process in batches
        results = self.disambiguate_batch(species_names, batch_size=batch_size)

        # Update database
        updated = self.update_species_table(results)
        logger.info(f"Updated {updated} species records")

        # Log statistics
        logger.info(f"Disambiguation complete: {self.stats}")

        return self.stats


class TaxonomicDisambiguatorFast:
    """
    Fast taxonomic disambiguator using rpy2.

    Loads WFO backbone once and keeps it in memory for all batches.
    Much faster than subprocess approach for large datasets.
    """

    def __init__(self, db_url: str):
        """Initialize with database connection and load WFO backbone."""
        if not HAS_RPY2:
            raise RuntimeError("rpy2 is required for TaxonomicDisambiguatorFast. Install with: pip install rpy2")

        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)
        self.stats = {
            'total': 0,
            'wfo_matched': 0,
            'wfo_fuzzy': 0,
            'wcvp_matched': 0,
            'unmatched': 0,
            'errors': 0
        }

        # Verify WFO backbone exists
        if not WFO_BACKBONE_PATH.exists():
            raise FileNotFoundError(
                f"WFO backbone not found at {WFO_BACKBONE_PATH}. "
                "Please download from https://www.worldfloraonline.org/downloadData"
            )

        logger.info(f"Using WFO backbone: {WFO_BACKBONE_PATH}")
        logger.info("Loading WFO backbone into R memory (this may take a few minutes)...")

        # Initialize rpy2 and load packages
        pandas2ri.activate()
        self.worldflora = importr('WorldFlora')
        self.jsonlite = importr('jsonlite')

        # Load backbone into R global environment
        ro.r(f'''
            WFO.data <- read.table("{WFO_BACKBONE_PATH}", sep="\\t", header=TRUE, quote="\\"",
                                   fill=TRUE, stringsAsFactors=FALSE, encoding="UTF-8")
        ''')
        logger.info("WFO backbone loaded into memory")

    def _match_wfo_batch(self, names: List[str]) -> List[Dict]:
        """Match a batch of names against WFO using in-memory data."""
        results = []

        try:
            # Create R vector from names
            r_names = ro.StrVector(names)
            ro.globalenv['species_names'] = r_names

            # Run WFO.match
            ro.r('''
                result <- WFO.match(spec.data = species_names, WFO.data = WFO.data,
                                    Fuzzy.max = 0.1, verbose = FALSE)
                output <- result[, c("spec.name.ORIG", "scientificName", "taxonID",
                                     "taxonomicStatus", "acceptedNameUsageID", "family",
                                     "genus", "specificEpithet", "Matched", "Fuzzy", "Fuzzy.dist")]
            ''')

            # Convert to Python via JSON
            json_str = ro.r('toJSON(output, na="null")')[0]
            wfo_data = json.loads(json_str)

            for row in wfo_data:
                matched = row.get('Matched', False)
                results.append({
                    'original_name': row.get('spec.name.ORIG'),
                    'matched': matched,
                    'fuzzy': row.get('Fuzzy', False),
                    'fuzzy_distance': row.get('Fuzzy.dist'),
                    'accepted_name': row.get('scientificName') if matched else None,
                    'wfo_id': row.get('taxonID'),
                    'taxonomic_status': row.get('taxonomicStatus'),
                    'accepted_wfo_id': row.get('acceptedNameUsageID'),
                    'family': row.get('family'),
                    'genus': row.get('genus'),
                    'specific_epithet': row.get('specificEpithet'),
                    'source': 'wfo'
                })

        except Exception as e:
            logger.error(f"WFO matching error: {e}")
            self.stats['errors'] += 1
            results = [{'original_name': n, 'matched': False, 'source': 'wfo'} for n in names]

        return results

    def disambiguate_batch(self, species_names: List[str], batch_size: int = 1000) -> List[Dict]:
        """Disambiguate a batch of species names using in-memory WFO data."""
        results = []
        total_batches = (len(species_names) + batch_size - 1) // batch_size

        for i in range(0, len(species_names), batch_size):
            batch = species_names[i:i+batch_size]
            batch_num = i // batch_size + 1
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} names)")

            # Match against WFO
            wfo_results = self._match_wfo_batch(batch)

            # Collect unmatched for WCVP fallback
            unmatched = []
            for r in wfo_results:
                if r.get('matched'):
                    results.append(r)
                    if r.get('fuzzy'):
                        self.stats['wfo_fuzzy'] += 1
                    else:
                        self.stats['wfo_matched'] += 1
                else:
                    unmatched.append(r['original_name'])

            # Try WCVP for unmatched
            if unmatched:
                wcvp_results = self._match_wcvp(unmatched)
                for r in wcvp_results:
                    if r.get('matched'):
                        self.stats['wcvp_matched'] += 1
                    else:
                        self.stats['unmatched'] += 1
                    results.append(r)

            # Log progress
            matched_so_far = self.stats['wfo_matched'] + self.stats['wfo_fuzzy'] + self.stats['wcvp_matched']
            logger.info(f"  Batch complete: {matched_so_far} matched, {self.stats['unmatched']} unmatched")

        self.stats['total'] = len(species_names)
        return results

    def _match_wcvp(self, names: List[str]) -> List[Dict]:
        """Match names against WCVP data in database."""
        results = []

        for name in names:
            matched = False

            # Try exact match first
            with Session(self.engine) as session:
                try:
                    row = session.execute(
                        text("""
                            SELECT id, canonical_name, family, genus, taxonomic_status, wcvp_id
                            FROM species
                            WHERE canonical_name = :name AND wcvp_id IS NOT NULL
                            LIMIT 1
                        """),
                        {'name': name}
                    ).fetchone()

                    if row:
                        results.append({
                            'original_name': name,
                            'matched': True,
                            'fuzzy': False,
                            'accepted_name': row.canonical_name,
                            'wcvp_id': row.wcvp_id,
                            'taxonomic_status': row.taxonomic_status,
                            'family': row.family,
                            'genus': row.genus,
                            'source': 'wcvp'
                        })
                        matched = True

                except Exception as e:
                    logger.debug(f"WCVP exact match error for {name}: {e}")

            if not matched:
                results.append({
                    'original_name': name,
                    'matched': False,
                    'source': 'wcvp'
                })

        return results

    def update_species_table(self, results: List[Dict]) -> int:
        """Update species table with disambiguation results."""
        updated = 0

        with Session(self.engine) as session:
            for r in results:
                if not r.get('matched'):
                    continue

                try:
                    if r['source'] == 'wfo':
                        session.execute(
                            text("""
                                UPDATE species
                                SET wfo_id = :wfo_id,
                                    taxonomic_status = COALESCE(taxonomic_status, :status),
                                    family = COALESCE(family, :family),
                                    genus = COALESCE(genus, :genus),
                                    updated_at = NOW()
                                WHERE canonical_name = :name
                            """),
                            {
                                'wfo_id': r.get('wfo_id'),
                                'status': r.get('taxonomic_status', '').lower(),
                                'family': r.get('family'),
                                'genus': r.get('genus'),
                                'name': r['original_name']
                            }
                        )
                    updated += 1

                except Exception as e:
                    logger.warning(f"Failed to update {r['original_name']}: {e}")

            session.commit()

        return updated

    def run_full_disambiguation(self, batch_size: int = 1000) -> Dict:
        """Run disambiguation on all species in database."""
        logger.info("Starting full taxonomic disambiguation (fast mode)")

        # Get all species names
        with Session(self.engine) as session:
            rows = session.execute(
                text("SELECT canonical_name FROM species WHERE wfo_id IS NULL ORDER BY canonical_name")
            ).fetchall()

        species_names = [r[0] for r in rows]
        logger.info(f"Found {len(species_names)} species without WFO ID")

        if not species_names:
            logger.info("No species to process")
            return self.stats

        # Process in batches
        results = self.disambiguate_batch(species_names, batch_size=batch_size)

        # Update database
        updated = self.update_species_table(results)
        logger.info(f"Updated {updated} species records")

        # Log statistics
        logger.info(f"Disambiguation complete: {self.stats}")

        return self.stats


class TaxonomicDisambiguatorSQL:
    """
    SQL-based taxonomic disambiguator.

    Uses WFO backbone table in PostgreSQL for fast matching.
    Much faster than R-based approaches for large datasets.
    """

    def __init__(self, db_url: str):
        """Initialize with database connection."""
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)
        self.stats = {
            'total': 0,
            'wfo_matched': 0,
            'wfo_fuzzy': 0,
            'wcvp_matched': 0,
            'unmatched': 0,
            'errors': 0
        }

        # Verify WFO backbone table exists
        with Session(self.engine) as session:
            result = session.execute(text("SELECT COUNT(*) FROM wfo_backbone"))
            count = result.scalar()
            if count == 0:
                raise RuntimeError("WFO backbone table is empty. Run import first.")
            logger.info(f"Using WFO backbone table with {count:,} records")

    def run_full_disambiguation(self, batch_size: int = 10000) -> Dict:
        """
        Run disambiguation using SQL JOINs - much faster than R.

        This method updates the species table directly using SQL.
        """
        logger.info("Starting SQL-based taxonomic disambiguation")

        # Step 1: Direct match on scientific_name
        logger.info("Step 1: Matching species by scientific name...")
        with Session(self.engine) as session:
            result = session.execute(text("""
                UPDATE species s
                SET wfo_id = w.taxon_id,
                    taxonomic_status = COALESCE(s.taxonomic_status, LOWER(w.taxonomic_status)),
                    family = COALESCE(s.family, w.family),
                    genus = COALESCE(s.genus, w.genus),
                    updated_at = NOW()
                FROM wfo_backbone w
                WHERE s.wfo_id IS NULL
                  AND s.canonical_name = w.scientific_name
                  AND w.taxon_rank = 'species'
            """))
            session.commit()
            exact_matches = result.rowcount
            self.stats['wfo_matched'] = exact_matches
            logger.info(f"  Exact matches: {exact_matches:,}")

        # Step 2: Match by genus + specific_epithet
        logger.info("Step 2: Matching by genus + epithet...")
        with Session(self.engine) as session:
            result = session.execute(text("""
                UPDATE species s
                SET wfo_id = w.taxon_id,
                    taxonomic_status = COALESCE(s.taxonomic_status, LOWER(w.taxonomic_status)),
                    family = COALESCE(s.family, w.family),
                    genus = COALESCE(s.genus, w.genus),
                    updated_at = NOW()
                FROM wfo_backbone w
                WHERE s.wfo_id IS NULL
                  AND s.genus = w.genus
                  AND SPLIT_PART(s.canonical_name, ' ', 2) = w.specific_epithet
                  AND w.taxon_rank = 'species'
            """))
            session.commit()
            genus_matches = result.rowcount
            self.stats['wfo_matched'] += genus_matches
            logger.info(f"  Genus+epithet matches: {genus_matches:,}")

        # Step 3: Count remaining unmatched
        with Session(self.engine) as session:
            result = session.execute(text("SELECT COUNT(*) FROM species WHERE wfo_id IS NULL"))
            unmatched = result.scalar()
            self.stats['unmatched'] = unmatched

        # Get total
        with Session(self.engine) as session:
            result = session.execute(text("SELECT COUNT(*) FROM species"))
            self.stats['total'] = result.scalar()

        logger.info(f"Disambiguation complete: {self.stats}")
        return self.stats


def run_disambiguation(db_url: str, batch_size: int = 10000, mode: str = 'sql'):
    """Run the disambiguation process.

    Args:
        db_url: Database connection URL
        batch_size: Number of names per batch
        mode: 'sql' (fastest), 'rpy2', or 'subprocess'
    """
    if mode == 'sql':
        logger.info("Using SQL mode (wfo_backbone table)")
        disambiguator = TaxonomicDisambiguatorSQL(db_url)
    elif mode == 'rpy2' and HAS_RPY2:
        logger.info("Using rpy2 mode (in-memory WFO backbone)")
        disambiguator = TaxonomicDisambiguatorFast(db_url)
    else:
        if mode == 'rpy2' and not HAS_RPY2:
            logger.warning("rpy2 not available, falling back to subprocess mode")
        disambiguator = TaxonomicDisambiguator(db_url)

    stats = disambiguator.run_full_disambiguation(batch_size=batch_size)
    return stats


if __name__ == "__main__":
    import sys

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("Error: DATABASE_URL environment variable not set")
        sys.exit(1)

    stats = run_disambiguation(db_url)
    print(f"\nDisambiguation Statistics:")
    print(f"  Total processed: {stats['total']}")
    print(f"  WFO matched (exact): {stats['wfo_matched']}")
    print(f"  WFO matched (fuzzy): {stats['wfo_fuzzy']}")
    print(f"  WCVP matched: {stats['wcvp_matched']}")
    print(f"  Unmatched: {stats['unmatched']}")
    print(f"  Errors: {stats['errors']}")
