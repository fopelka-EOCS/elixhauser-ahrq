# Changelog

All notable changes to the `elixhauser-ahrq` package are documented in this file.

This project tracks AHRQ's annual Elixhauser Comorbidity Software releases. Version numbers follow the pattern `YYYY.R.P` where `YYYY` is the AHRQ fiscal year, `R` is the AHRQ release within that year, and `P` is the patch version for this Python implementation.

---

## [2026.1.0] — 2026-06-01

### Initial Public Release

**AHRQ Source:** Elixhauser Comorbidity Software Refined for ICD-10-CM, v2026.1 (FY2026, released November 2025)

**Scope:**
- 4,568 ICD-10-CM diagnosis codes mapped to 38 Elixhauser comorbidity categories
- Van Walraven composite scoring with mortality and readmission weight sets
- Python classes: `ElixhauserMapper` (code-to-category mapping) and `ElixhauserScorer` (composite score calculation)
- Original AHRQ SAS programs preserved in `SAS-Programs/` for reference

**CDC Review:**
- CDC reviewed the Python implementation against the AHRQ SAS source
- CDC suggested specific changes to code mapping logic
- Changes were implemented and tested; CDC concurred with the updated implementation
- All 38 comorbidity categories validated against AHRQ reference outputs

**Distribution Channels:**
- GitHub: [github.com/fopelka-EOCS/elixhauser-ahrq](https://github.com/fopelka-EOCS/elixhauser-ahrq) (canonical)
- PyPI: `pip install elixhauser-ahrq`
- Hugging Face Dataset: [EOCS/elixhauser-icd10-mapping](https://huggingface.co/datasets/EOCS/elixhauser-icd10-mapping)
- Hugging Face Space: [EOCS/elixhauser-risk-calculator](https://huggingface.co/spaces/EOCS/elixhauser-risk-calculator)

**Note on AHRQ 2027 Update:**
As of September 2026, AHRQ has not yet published updated variables and weights for FY2027. This package will be updated when the new release is available.

---

## Versioning Policy

- **Major version** (`YYYY`): Tracks the AHRQ fiscal year release. Updated when AHRQ publishes new code mappings, weight changes, or category additions/removals.
- **Minor version** (`R`): Tracks the AHRQ release number within a fiscal year (typically `1`).
- **Patch version** (`P`): Bug fixes, documentation updates, or packaging changes to the Python implementation that do not affect the underlying AHRQ mappings or weights.

When AHRQ publishes a new release:
1. ICD-10-CM mapping tables are updated
2. Van Walraven weights are verified against the new AHRQ source
3. All unit tests are re-run against AHRQ reference outputs
4. A new version is tagged and published to PyPI and Hugging Face

---

## Attribution

This package implements reference data from the Agency for Healthcare Research and Quality (AHRQ) Healthcare Cost and Utilization Project (HCUP). AHRQ HCUP tools are provided for public use.

Source: https://hcup-us.ahrq.gov/toolssoftware/comorbidityicd10/comorbidity_icd10.jsp
