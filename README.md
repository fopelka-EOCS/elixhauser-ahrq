# elixhauser-ahrq

[![PyPI version](https://img.shields.io/pypi/v/elixhauser-ahrq.svg)](https://pypi.org/project/elixhauser-ahrq/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

**A Python reimplementation of AHRQ's Elixhauser Comorbidity Software Refined for ICD-10-CM, v2027.1 (FY2027).**

It assigns AHRQ's 38 Elixhauser comorbidity measures from the secondary diagnoses on an inpatient discharge. It honours present-on-admission (POA) indicators and AHRQ's POA-exempt lists, and computes AHRQ's two indices: in-hospital mortality and 30-day all-cause readmission. The v2027.1 release covers ICD-10-CM codes from October 2015 through September 2027.

> **Advisory: versions before 2027.1.0 contained errors.**
> - **Wrong weights.** GitHub versions before 2026-05-08 contained incorrect index weights and POA logic.
> - **Defects in 2026.1.0–2026.1.3:**
>   - metastatic cancer suppressed leukemia and lymphoma;
>   - POA-exempt codes were not honoured;
>   - a POA value of `1` was accepted as present on admission;
>   - the cerebrovascular "not present on admission" rule could not fire.
> - **Calculator.** The former Hugging Face calculator treated the first code entered as a comorbidity and gave order-dependent results.
>
> All of these are corrected in 2027.1.0. See [CHANGELOG.md](CHANGELOG.md). Results produced with earlier versions should be re-run.

This is an independent implementation. It is not produced, reviewed or endorsed by AHRQ.

## Installation

```bash
pip install elixhauser-ahrq
```

## Quick start

Give the principal diagnosis separately. AHRQ never maps it. Give each secondary diagnosis with its POA indicator.

```python
>>> from elixhauser_ahrq import score_discharge
>>> r = score_discharge(
...     principal_dx="I214",                                  # NSTEMI: not a comorbidity
...     secondary_dx=["I5022", "E1122", "N186", "C7800", "I69351"],
...     secondary_poa=["Y", "Y", "N", "Y", ""],               # I69351 is POA-exempt
...     discharge_date="2026-11-02",                          # selects AHRQ's FY2027 exempt list
... )
>>> r["present"]
['CANCER_METS', 'CBVD', 'HF', 'DIAB_CX', 'PARALYSIS']
>>> r["mortality_index"], r["readmission_index"], r["partial"]
(43, 25, False)

```

ESRD (`N186`) is not counted: renal failure requires POA = Y or W, and it was coded N.

**Without POA data**, AHRQ cannot assess 18 of the 38 measures. The package returns them as `None`, and the index is flagged as **partial**:

```python
>>> r = score_discharge("I214", ["I5022", "E1122", "N186", "C7800", "I69351"])
>>> r["present"], r["mortality_index"], r["partial"], len(r["not_assessable"])
(['CANCER_METS', 'DIAB_CX'], 20, True, 18)

```

### Rules implemented (from AHRQ's SAS mapping program)

| Rule | Behaviour |
|---|---|
| Principal diagnosis | Never mapped. Only secondary diagnoses are mapped. |
| POA-dependent measures (18) | Counted only if POA = `Y` or `W`, or if the code is on AHRQ's POA-exempt list for the discharge's ICD-10-CM version. `N`, `U`, `1` and blank do not count. |
| No POA data | The 18 POA-dependent measures are not assessable (`None`), and the index is partial. |
| Cerebrovascular disease | Counted if a stroke code is present on admission, or a sequela code is present and no stroke is coded "not present on admission". |
| Exclusions | Complicated diabetes overrides uncomplicated. Complicated hypertension overrides uncomplicated. Metastatic cancer overrides solid tumour and in situ. Solid tumour overrides in situ. Severe liver disease overrides mild. Severe renal failure overrides moderate. Metastatic cancer does **not** override leukemia or lymphoma. |
| ICD-10-CM version | Derived from the discharge date as in AHRQ's program. With no date, AHRQ's default applies (version 44, FY2027). Dates outside October 2015 to September 2027 produce a warning. |

## API

```python
from elixhauser_ahrq import assign_comorbidities, ElixhauserMapper, ElixhauserScorer

res = assign_comorbidities("I214", ["I5022"], ["Y"], discharge_date="2026-11-02")
res.flags            # {measure: True / False / None} for all 38 measures
res.trace            # per-code explanation: AHRQ label, POA, exemption, what was counted

ElixhauserScorer("mortality").calculate_score(res.flags)
ElixhauserScorer("readmission").calculate_score(res.flags)

# Long-format DataFrames: one row per diagnosis, with a sequence column (1 = principal)
flags_df = ElixhauserMapper().map_dataframe(df, "encounter_id", "dx", poa_col="poa",
                                            dx_sequence_col="dx_seq",
                                            discharge_date_col="discharge_date")
scored = ElixhauserScorer("mortality").score_dataframe(flags_df)
```

`ElixhauserMapper().map_patient_diagnoses(codes, poa)` remains for compatibility. It treats `codes[0]` as the principal diagnosis.

## Indices and risk tiers

The indices are AHRQ's in-hospital mortality and 30-day readmission indices (Moore et al., 2017). The weights come from AHRQ's SAS index program, so they match AHRQ exactly. They are **not** the van Walraven (2009) score.

**AHRQ publishes no risk tiers.** `stratify_risk` therefore requires thresholds you have validated for your own population and outcome.

## Intended use and limitations

- **Intended population.** Adult inpatient discharges with ICD-10-CM diagnoses and, ideally, POA indicators. The indices were developed to predict in-hospital mortality and 30-day readmission.
- **Not intended for:** predicting complications or cost; outpatient or professional claims without POA; or individual clinical decisions.
- **Claims without POA.** Inferring POA from claims (for example, with lookback windows) is a user-side assumption that AHRQ does not provide. It has not been validated here.
- **Normalisation, not part of AHRQ's program.** Codes are upper-cased and have decimals removed. POA values are upper-cased. AHRQ's program caps diagnoses at its `NUMDX` setting (40 by default); this package maps every secondary diagnosis given.

## Validation status

This package reimplements AHRQ's Elixhauser Comorbidity Software Refined for ICD-10-CM (SAS programs, v2027.1).

On every build:
- its code lists, POA-exempt lists and weights are regenerated from AHRQ's SAS programs and must be identical;
- its mapping is checked code by code against AHRQ's reference workbook;
- its logic is checked on rule cases and on 40,000 randomized synthetic discharges against an independent transliteration of AHRQ's SAS mapping and index programs.

AHRQ does not publish reference output files. This release has **not** been compared with output from AHRQ's SAS software itself, or with real-world data. See [docs/VALIDATION.md](docs/VALIDATION.md) for exactly what has and has not been tested.

## Use with PACES and other episode methods

This package implements AHRQ's method only. For episode-based work, callers must decide which diagnoses represent baseline risk; for EOCS methods, pass baseline-window diagnoses only. Any such window, and any risk tiers, belong to the calling method, not to this package. EOCS's quality-risk stratification methodology is separate and is not part of this package.

## Versioning

`YYYY.R.P`: AHRQ fiscal year, AHRQ release, and the patch of this implementation. Patch releases can change results when they correct defects; the CHANGELOG says so whenever they do.

| Package | AHRQ release | Codes | Status |
|---|---|---|---|
| 2027.1.0 | v2027.1 (FY2027) | 4,573 | Current |
| 2026.1.0–2026.1.3 | v2026.1 | 4,567 | **Superseded. Contains defects; do not use.** |

## Citation

See [CITATION.cff](CITATION.cff). Please also cite AHRQ's software:

> Agency for Healthcare Research and Quality. Elixhauser Comorbidity Software Refined for ICD-10-CM, v2027.1. Healthcare Cost and Utilization Project (HCUP). https://hcup-us.ahrq.gov/toolssoftware/comorbidityicd10/comorbidity_icd10.jsp

## License and attribution

MIT License. The code lists and weights come from AHRQ HCUP's Elixhauser Comorbidity Software Refined for ICD-10-CM, which AHRQ provides for public use. AHRQ's SAS programs, reference file, change log and user guide are included unmodified in `SAS-Programs/`.

## References

- Elixhauser A, Steiner C, Harris DR, Coffey RM. Comorbidity measures for use with administrative data. *Medical Care* 1998;36(1):8–27.
- Moore BJ, White S, Washington R, Coenen N, Elixhauser A. Identifying increased risk of readmission and in-hospital mortality using hospital administrative data: the AHRQ Elixhauser Comorbidity Index. *Medical Care* 2017;55(7):698–705.
