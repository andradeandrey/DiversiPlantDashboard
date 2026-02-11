#!/usr/bin/env python3
"""
Reprocess growth_form values in species_unified to use the 11 standardized values.

Fixes two categories of data:
  1. WCVP-sourced records: Re-classifies using the updated _classify_growth_form()
     with the raw life_form from species_traits + family from species.
  2. Non-standard legacy values: Direct SQL mappings for values from reflora,
     practitioners, etc.

Target values: graminoid, forb, subshrub, shrub, tree, scrambler, vine, liana,
               palm, bamboo, other

Usage:
    .venv/bin/python scripts/reprocess_growth_forms.py [--dry-run]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from crawlers.wcvp import WCVPCrawler

VALID_GROWTH_FORMS = frozenset({
    'graminoid', 'forb', 'subshrub', 'shrub', 'tree',
    'scrambler', 'vine', 'liana', 'palm', 'bamboo', 'other',
})

# Direct mappings for non-standard values (reflora, practitioners, etc.)
LEGACY_MAP = {
    'aquatic': 'other',
    'succulent': 'other',
    'liana/volúvel/trepadeira': 'liana',
    'arbusto|árvore': 'shrub',
    'arbusto|subarbusto|suculenta': 'subshrub',
}


def reprocess_wcvp(engine, dry_run=False):
    """Re-classify all WCVP-sourced growth_form values using updated logic."""
    crawler = WCVPCrawler.__new__(WCVPCrawler)

    with engine.connect() as conn:
        # Fetch all WCVP species that need reclassification
        rows = conn.execute(text("""
            SELECT su.species_id, su.growth_form, st.life_form, s.family
            FROM species_unified su
            JOIN species s ON su.species_id = s.id
            JOIN species_traits st ON su.species_id = st.species_id AND st.source = 'wcvp'
            WHERE su.growth_form_source = 'wcvp'
              AND st.life_form IS NOT NULL
        """)).fetchall()

        total = len(rows)
        updated = 0
        unchanged = 0
        by_change = {}

        for species_id, old_gf, life_form, family in rows:
            family = family or ''
            new_gf = crawler._classify_growth_form(life_form, family)

            if new_gf == old_gf:
                unchanged += 1
                continue

            key = f"{old_gf} -> {new_gf}"
            by_change[key] = by_change.get(key, 0) + 1

            if not dry_run:
                conn.execute(text("""
                    UPDATE species_unified
                    SET growth_form = :new_gf
                    WHERE species_id = :species_id
                      AND growth_form_source = 'wcvp'
                """), {'new_gf': new_gf, 'species_id': species_id})

            updated += 1

        if not dry_run:
            conn.commit()

        print(f"\n[WCVP] Total: {total:,}, Updated: {updated:,}, Unchanged: {unchanged:,}")
        if by_change:
            print("  Changes:")
            for change, count in sorted(by_change.items(), key=lambda x: -x[1]):
                print(f"    {change}: {count:,}")


def reprocess_legacy(engine, dry_run=False):
    """Map non-standard growth_form values to standardized ones."""
    with engine.connect() as conn:
        total_updated = 0

        for old_val, new_val in LEGACY_MAP.items():
            result = conn.execute(text("""
                SELECT COUNT(*) FROM species_unified WHERE growth_form = :old_val
            """), {'old_val': old_val})
            count = result.scalar()

            if count == 0:
                continue

            print(f"  '{old_val}' -> '{new_val}': {count:,} records")

            if not dry_run:
                conn.execute(text("""
                    UPDATE species_unified
                    SET growth_form = :new_val
                    WHERE growth_form = :old_val
                """), {'new_val': new_val, 'old_val': old_val})

            total_updated += count

        # Also fix any remaining 'herb' not caught by WCVP re-classification
        # (e.g. from other sources). Map herb → forb/graminoid by family.
        result = conn.execute(text("""
            SELECT su.species_id, s.family
            FROM species_unified su
            JOIN species s ON su.species_id = s.id
            WHERE su.growth_form = 'herb'
        """)).fetchall()

        if result:
            graminoid_families = {'Poaceae', 'Cyperaceae', 'Juncaceae', 'Typhaceae'}
            herb_to_graminoid = 0
            herb_to_forb = 0

            for species_id, family in result:
                new_gf = 'graminoid' if family in graminoid_families else 'forb'
                if new_gf == 'graminoid':
                    herb_to_graminoid += 1
                else:
                    herb_to_forb += 1

                if not dry_run:
                    conn.execute(text("""
                        UPDATE species_unified
                        SET growth_form = :new_gf
                        WHERE species_id = :species_id
                    """), {'new_gf': new_gf, 'species_id': species_id})

            print(f"  'herb' -> 'graminoid': {herb_to_graminoid:,} records")
            print(f"  'herb' -> 'forb': {herb_to_forb:,} records")
            total_updated += herb_to_graminoid + herb_to_forb

        # Fix remaining 'climber' → vine (conservative default)
        result = conn.execute(text("""
            SELECT COUNT(*) FROM species_unified WHERE growth_form = 'climber'
        """))
        climber_count = result.scalar()
        if climber_count > 0:
            print(f"  'climber' -> 'vine': {climber_count:,} records")
            if not dry_run:
                conn.execute(text("""
                    UPDATE species_unified
                    SET growth_form = 'vine'
                    WHERE growth_form = 'climber'
                """))
            total_updated += climber_count

        if not dry_run:
            conn.commit()

        print(f"\n[Legacy] Total updated: {total_updated:,}")


def verify(engine):
    """Verify all growth_form values are valid."""
    with engine.connect() as conn:
        r = conn.execute(text("""
            SELECT growth_form, COUNT(*) as cnt
            FROM species_unified
            WHERE growth_form IS NOT NULL
            GROUP BY growth_form
            ORDER BY cnt DESC
        """))
        print("\n=== Final growth_form distribution ===")
        invalid = 0
        for gf, count in r:
            marker = '  ' if gf in VALID_GROWTH_FORMS else '✗ '
            print(f"  {marker}{gf}: {count:,}")
            if gf not in VALID_GROWTH_FORMS:
                invalid += count

        r = conn.execute(text("SELECT COUNT(*) FROM species_unified WHERE growth_form IS NULL"))
        null_count = r.scalar()
        print(f"\n  NULL: {null_count:,}")

        if invalid > 0:
            print(f"\n  WARNING: {invalid:,} records with non-standard growth_form values remain")
        else:
            print("\n  All growth_form values are valid.")


def main():
    parser = argparse.ArgumentParser(description='Reprocess growth_form values')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would change without modifying the database')
    args = parser.parse_args()

    db_url = os.environ.get('DATABASE_URL',
                            'postgresql://diversiplant:diversiplant_dev@localhost:5432/diversiplant')
    engine = create_engine(db_url)

    mode = "[DRY RUN] " if args.dry_run else ""
    print(f"{mode}Reprocessing growth_form values...")

    print(f"\n{mode}Phase 1: Re-classifying WCVP-sourced records...")
    reprocess_wcvp(engine, dry_run=args.dry_run)

    print(f"\n{mode}Phase 2: Fixing non-standard legacy values...")
    reprocess_legacy(engine, dry_run=args.dry_run)

    print(f"\n{mode}Phase 3: Verification...")
    verify(engine)


if __name__ == '__main__':
    main()
