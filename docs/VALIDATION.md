# Validation record: elixhauser-ahrq 2027.1.0

**Target:** AHRQ Elixhauser Comorbidity Software Refined for ICD-10-CM, v2027.1 (FY2027).
**Release-candidate status:** all tiers T1–T6 pass, and the mutation check passes. T7 has not been done.

## AHRQ sources

The files were downloaded from https://hcup-us.ahrq.gov/toolssoftware/comorbidityicd10/comorbidity_icd10.jsp on 2026-11-10.

| File | SHA-256 |
|---|---|
| `CMR_v2027-1.zip` (as downloaded) | `51d86f158bc8b92f3d5bf98884a961d18d465913c72a22298a439f6184ea7100` |
| `SAS-Programs/CMR_Format_Program_v2027-1.sas` | `d363d76e8ea87620c0fc39c2cde119a72d809b3e31a9086c8a6390d9c80e9d52` |
| `SAS-Programs/CMR_Mapping_Program_v2027-1.sas` | `fe5e8984201db535c8df3314ad261536e308e596bf97bafd3a6752ea99399545` |
| `SAS-Programs/CMR_Index_Program_v2027-1.sas` | `a4b714ea0c23e2a95eecd7af6cd8c48ffec4a689631ab42d60c27a93e1fe31b3` |
| `SAS-Programs/CMR-Reference-File-v2027-1.xlsx` | `32ab1cdd158e362e20cdaaf989f17d9405bb69a9bc8735a7c5e676ba0ea50946` |
| `SAS-Programs/CMR-ChangeLog-v20261-v20271.xlsx` | `b3a9df7d4643205ce0e6e97c1dceef9d3f0a101d5ab68a88cea72d69e7ebed04` |
| `SAS-Programs/CMR-User-Guide-v2027-1.pdf` | `7329a8426b208f180669d57a74bea5ccb5cd664a9f88ac02d1d366df50b130d4` |

The files in `SAS-Programs/` are the zip's contents, unmodified.

## Test tiers

| Tier | What it checks | Expected values come from | Result |
|---|---|---|---|
| T0 | The bundled data file is byte-identical to a fresh build from the SAS programs (`tools/build_data.py --check`) | AHRQ SAS programs | Pass |
| T1 | All 38 mortality and 38 readmission weights | An independent parse of `CMR_Index_Program` | 76/76 equal |
| T2 | Each of the 4,573 codes maps to exactly the measures flagged in AHRQ's reference workbook. The 18 POA-dependent measures equal the workbook's. The table of combined labels equals the IF statements in `CMR_Mapping_Program`. | AHRQ reference workbook and mapping program | 100% equal |
| T3 | POA-exempt lists for ICD-10-CM versions 33–44, and the `$COMFMT` code map | An independent parse of `CMR_Format_Program` | Equal sets |
| T4 | 38 rule cases plus API tests. Each rule case gives a hand-stated expected result and is also checked against the SAS transliteration. The cases cover: metastatic cancer with leukemia, lymphoma, in situ and solid tumour; POA-exempt sequelae with blank, N and U; POA `1`, `Y`, `W`, `N`, `U` and blank; the cerebrovascular "not on admission" rule; principal-only and principal repeated; every exclusion; combined labels with and without POA; all 8 FY2027 additions; the DEMENTIA removals; the `DRUG` rename; Z6818 exempt in version 44 but not 43; no-POA partial indices; order independence; discharge-date version selection; the DataFrame API; and the per-code trace. | AHRQ rules, and the SAS transliteration | All pass |
| T5 | README examples (doctest) and `example_usage.py` are executed | Package output | Pass |
| T6 | Randomized differential test: 2 seeds × 20,000 synthetic discharges, with 0–25 secondary diagnoses each. The data are enriched with combined-label, cerebrovascular and POA-exempt codes, all POA values, versions 33–44, out-of-window dates, and 15% of records without POA. Checks: all 38 flags (including not-assessable), ICD-10-CM version, and both indices. | `validation/sas_reference.py`, an independent line-by-line transliteration of AHRQ's SAS mapping and index programs. It was written from the SAS programs alone, without access to this package's code. See `validation/SAS_REFERENCE_NOTES.md`. | **0 mismatches in 40,000** |
| M | Mutation check: each 2026 defect (R2–R7) is re-planted in a copy, and the suite must fail | `validation/mutation_check.py` | Every mutation caught; control passes |
| T7 | Field-by-field comparison with output from AHRQ's SAS software itself, on 2,000 synthetic discharges with and without POA | AHRQ SAS v2027.1, run with the kit from `validation/make_t7_kit.py` and compared by `validation/t7_compare.py` | **Not done**: no SAS environment is available to the maintainers; the kit is ready for anyone with SAS |

## What this does and does not establish

- **Established.** The package's tables are AHRQ's tables, and the package's logic agrees with a faithful reading of AHRQ's SAS logic on a large, deliberately adversarial synthetic sample.
- **Not established.**
  - Agreement with **executed** SAS output (T7). AHRQ publishes no reference output files, and no SAS environment was used.
  - Behaviour on **real-world data**.
  - Use on **outpatient or professional claims**, or on claims whose POA has been inferred rather than coded.
  - Any predictive performance beyond AHRQ's intended uses: in-hospital mortality and 30-day readmission.

T6 compares two implementations of one reading of the SAS programs. A misreading shared by both would not be caught. The two were written independently to reduce that risk; only T7 removes it.

## Known departures from AHRQ's SAS program (input handling only)

1. **Codes** are stripped, upper-cased and have decimal points removed. SAS expects clean codes and would not map `i50.22`.
2. **POA values** are stripped and upper-cased. SAS would treat a lowercase `y` as not present.
3. **No `NUMDX` cap.** AHRQ's program examines at most `NUMDX` diagnoses (default 40, set by the user). This package maps every secondary diagnosis supplied.

None of these changes the result for input in AHRQ's documented format.

## External review history

- **May 2026.** A health scientist at CDC, acting in an individual technical capacity, compared an earlier version of this package with AHRQ's SAS programs on 10,000 records and identified defects in weights and POA handling. These were corrected on 2026-05-08.
- **July 2026.** The same reviewer reported and supplied the correction for the remaining hierarchy defect (R2). It was not applied until 2027.1.0.
- **Scope.** This was not a CDC institutional review, validation or endorsement. The defects corrected in 2027.1.0 under R3–R6 were found later and were not part of that review.

## Reproduce

```bash
pip install -e ".[dev]"
python tools/build_data.py --check
python -m pytest tests
python validation/mutation_check.py
python validation/make_t7_kit.py      # then run validation/t7_kit/RUN_T7.sas in SAS
python validation/t7_compare.py validation/t7_kit/sas_output.csv
```
