# Changelog

Versions follow `YYYY.R.P`: AHRQ fiscal year, AHRQ release, and the patch of this implementation. A patch can change results when it corrects a defect; such changes are marked **Behaviour change**.

---

## [2027.1.0] (release candidate, unreleased)

**AHRQ source:** Elixhauser Comorbidity Software Refined for ICD-10-CM, v2027.1 (FY2027). It covers ICD-10-CM codes from October 2015 through September 2027. AHRQ's SAS programs, reference file, change log and user guide are in `SAS-Programs/`.

### AHRQ changes from v2026.1 to v2027.1
- **8 codes added:**
  - CANCER_METS: C7831, C7832, C7983;
  - COAG: D6911, D6919;
  - LIVER_MLD: K740A, K7683;
  - WGHTLOSS: Z6818 (POA-exempt).
- **2 codes removed from DEMENTIA:** F0670, F0671. This is retroactive, because the mapping covers all years from October 2015.
- **Rename:** `DRUG_ABUSE` becomes `DRUG` ("Drug use disorders"). The old key is still accepted by the scorer, with a `DeprecationWarning`.
- **Relabel:** ALCOHOL becomes "Alcohol-related disorders".
- **New POA-exempt list** for ICD-10-CM version 44 (FY2027).
- **Weights:** no change.
- **Totals:** 4,573 codes and 38 measures.

### Corrections (Behaviour change: results differ from 2026.1.x)
- **Metastatic cancer no longer suppresses leukemia or lymphoma.** It suppresses only solid tumour and in situ, as in AHRQ's program. An external reviewer reported this in May 2026 and supplied the correction in July 2026; it was not applied until this release.
- **POA-exempt codes are honoured** using AHRQ's exempt list for the discharge's ICD-10-CM version (33–44). New `discharge_date` / `icd_version` arguments select the list.
- **POA `1` is no longer treated as present on admission.** Only `Y` and `W` are, as in AHRQ's program. `1` and blank count only through the exempt lists.
- **Cerebrovascular "not present on admission" rule now applies.** A stroke coded N or U on a non-exempt code stops a sequela from counting as cerebrovascular disease.
- **Without POA data, the 18 POA-dependent measures are returned as `None` (not assessable)**, no longer silently `False`. Indices are marked partial (`index_partial`, `partial`).
- **No default risk tiers.** `stratify_risk` requires explicit thresholds. AHRQ publishes none, and the former defaults were never validated.

### Implementation
- **Generated, not hand-copied.** Code lists, exempt lists, weights, labels and POA classes are compiled from AHRQ's SAS programs by `tools/build_data.py`. The bundled data no longer depend on the reference workbook at run time, and every wheel carries them. (2026.1.0–2026.1.2 wheels could fail to load the reference file.)
- **New API:**
  - `assign_comorbidities()` and `score_discharge()` take an explicit principal diagnosis and return a per-code trace;
  - `map_dataframe()` takes `discharge_date_col` and warns if no diagnosis sequence is given;
  - `__version__` now reports the package version (it said `0.1.0`).
- **New tests:**
  - parity with AHRQ's SAS programs and reference workbook;
  - rule cases for every defect above;
  - a 40,000-record differential test against an independent SAS transliteration (`validation/`);
  - executed README examples;
  - a mutation check showing the suite catches each historical defect.

### Documentation
- The README describes AHRQ's indices, not "van Walraven" scores. The incorrect 30-category weight table is removed.
- The statements "validated against AHRQ reference outputs" and "CDC-reviewed / CDC concurred" are withdrawn. They described an individual reviewer's comparison, not an institutional review. See `docs/VALIDATION.md`.
- EOCS commercial material and episode risk tiers are removed. The package implements AHRQ's method only.

---

## History of defects in earlier versions

- **GitHub versions before 2026-05-08** contained incorrect index weights and POA logic. On 2026-05-08 these were corrected after an external reviewer compared the package with AHRQ's SAS programs.
- **2026.1.0–2026.1.3** (PyPI, 2026) carried the defects corrected in 2027.1.0 above. They are superseded and should not be used.

## [2026.1.3] and earlier

v2026.1-based releases. Superseded; see "History of defects" above.

---

Source: https://hcup-us.ahrq.gov/toolssoftware/comorbidityicd10/comorbidity_icd10.jsp
