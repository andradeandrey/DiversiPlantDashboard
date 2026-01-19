⏺ Taxonomic disambiguation complete!

  Summary:
  ┌───────────────┬─────────┬────────────┐
  │    Metric     │  Count  │ Percentage │
  ├───────────────┼─────────┼────────────┤
  │ Total species │ 448,749 │ 100%       │
  ├───────────────┼─────────┼────────────┤
  │ With WFO ID   │ 400,809 │ 89.3%      │
  ├───────────────┼─────────┼────────────┤
  │ Unmatched     │ 47,940  │ 10.7%      │
  └───────────────┴─────────┴────────────┘
  Implementation details:
  1. Downloaded WFO Taxonomic Backbone (1.5M records, 859MB)
  2. Imported backbone into PostgreSQL table wfo_backbone
  3. Created SQL-based disambiguator - completes in ~3 minutes vs hours for R
  4. Created 3 modes: sql (fastest), rpy2, subprocess

  Unmatched species include:
  - Hybrid names (×)
  - Fossil species
  - Regional species not in WFO
  - Some misspellings

  The module is at crawlers/disambiguation.py and can be run with:
  from crawlers.disambiguation import run_disambiguation
  stats = run_disambiguation(db_url, mode='sql')

✻ Churned for 1h 8m 12s

⏺ Background command "Test fast disambiguation mode" completed (exit code 0)

⏺ Both background tasks completed successfully. The taxonomic disambiguation is now fully implemented and operational:

  - WFO backbone imported: 1,521,202 records
  - Species disambiguated: 400,809 of 448,749 (89.3%)

  The SQL-based approach proved dramatically faster than the R-based methods - completing the full 448K species in ~3 minutes versus the estimated 12+ hours for the R subprocess approach.