#!/usr/bin/env python3
"""Test the disambiguation module with a small batch."""
import sys
sys.path.insert(0, '/Users/andreyandrade/Code/DiversiPlantDashboard-sticky')

from crawlers.disambiguation import TaxonomicDisambiguator

# Test with a small batch
test_names = [
    "Araucaria angustifolia",
    "Passiflora edulis",
    "Euterpe edulis",
    "Mangifera indica",
    "Theobroma cacao",
    "Coffea arabica",
    "Musa paradisiaca",  # banana - might have synonym issues
    "Zea mays",
    "Oryza sativa",
    "Invalid species name",
    "Araucaria angustifola",  # typo - should fuzzy match
]

db_url = "postgresql://diversiplant:diversiplant_dev@localhost:5432/diversiplant"

print("Testing TaxonomicDisambiguator...")
print(f"Test names: {test_names}\n")

disambiguator = TaxonomicDisambiguator(db_url)
results = disambiguator.disambiguate_batch(test_names, batch_size=100)

print("\nResults:")
print("-" * 80)
for r in results:
    status = "✓" if r.get('matched') else "✗"
    fuzzy = " (fuzzy)" if r.get('fuzzy') else ""
    source = r.get('source', 'unknown')
    accepted = r.get('accepted_name', 'N/A')
    wfo_id = r.get('wfo_id', 'N/A')

    print(f"{status} {r['original_name']:<30} → {accepted:<30} [{source}{fuzzy}] WFO:{wfo_id}")

print("\nStatistics:")
print(f"  Total: {disambiguator.stats['total']}")
print(f"  WFO exact: {disambiguator.stats['wfo_matched']}")
print(f"  WFO fuzzy: {disambiguator.stats['wfo_fuzzy']}")
print(f"  WCVP: {disambiguator.stats['wcvp_matched']}")
print(f"  Unmatched: {disambiguator.stats['unmatched']}")
