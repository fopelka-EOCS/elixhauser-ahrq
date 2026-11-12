# Advisory EOCS-ELX-2026-01: elixhauser-ahrq: errors in versions before 2027.1.0, and withdrawal of the former demonstration app

*Issued: 2026-11-12. Corrected: 2026-11-12. The first version of this advisory stated that the dataset correction was published and that the 2026 PyPI releases were yanked; neither had yet happened.*

## Current status (2026-11-12)

| Item | Status |
|---|---|
| elixhauser-ahrq 2027.1.0 (AHRQ v2027.1) | **Published** on PyPI |
| Hugging Face dataset correction | Prepared; **not yet published**. Until it is, do not use the dataset's `van_walraven_mortality_weight` column |
| Calculator (Hugging Face Space) | Rebuilt; **remains Private**. The former app's results should not be used |
| PyPI releases 2026.1.0–2026.1.3 | **Not yet yanked.** Do not use them; upgrade to 2027.1.0 |
| Comparison with executed AHRQ SAS output (T7) | **Pending** |

This table will be updated as each item is completed.

*Applies to:*
- *elixhauser-ahrq 2026.1.0–2026.1.3 (PyPI), and GitHub versions before 2027.1.0;*
- *the former Hugging Face Space `fopelka/elixhauser-risk-calculator`;*
- *the Hugging Face dataset `EOCS-LTD/elixhauser-icd10-mapping` (current public version).*

*Fixed in: elixhauser-ahrq 2027.1.0, which implements AHRQ Elixhauser Comorbidity Software Refined for ICD-10-CM v2027.1.*

## Summary

A review against AHRQ's official Elixhauser Comorbidity Software Refined for ICD-10-CM (SAS programs v2026.1 and v2027.1) found that earlier versions of this package differed from AHRQ's logic in four ways. It also found errors in the demonstration app, the dataset and the documentation. Version 2027.1.0 corrects all of them and updates the package to AHRQ's FY2027 release.

**Anyone who used an earlier version should re-run the analysis with 2027.1.0.** We intend to yank PyPI releases 2026.1.0–2026.1.3. Yanked releases remain installable by exact version pin, so earlier analyses can still be reproduced.

## 1. Logic differences in PyPI releases 2026.1.0–2026.1.3

The index weights in these releases match AHRQ.

| | Defect | Effect on affected patients |
|---|---|---|
| (a) | Metastatic cancer suppressed leukemia and lymphoma; AHRQ does not. | Mortality index under-stated by 9 (leukemia) or 5 (lymphoma); readmission index by 10 or 7. |
| (b) | AHRQ's lists of POA-exempt diagnosis codes were not applied, so exempt codes without a `Y` or `W` POA value were not counted (for example, hemiplegia following stroke, I69.351). | Up to 9 mortality and 3 readmission points omitted per affected code. |
| (c) | A POA value of `1` was treated as present on admission for every code. AHRQ accepts only `Y` or `W` for non-exempt codes. | Conditions arising in hospital could be counted as comorbidities; for example, heart failure adds 14 mortality points. |
| (d) | AHRQ's rule that withholds cerebrovascular disease when a new stroke is not present on admission was never applied. | 5 mortality points added in error. |

Releases 2026.1.0–2026.1.2 also did not include the reference file needed to run with default settings.

## 2. Earlier GitHub versions

Versions on GitHub before 2026-05-08 used incorrect index weights and POA logic. They were corrected after an external comparison with AHRQ's SAS programs. No PyPI release contained those weights.

## 3. Former demonstration app (withdrawn and replaced)

The former Hugging Face app supplied no POA information and treated the first code entered as the principal diagnosis. As a result:
- the 18 measures that require POA (including heart failure, renal failure and coagulopathy) were never counted;
- scores depended on the order in which codes were entered.

Do not use its earlier results. A rebuilt calculator for 2027.1.0, which asks for the principal diagnosis and POA explicitly, is not yet public.

## 4. Dataset

`EOCS-LTD/elixhauser-icd10-mapping` currently contains AHRQ's v2025.1 code mapping and a `van_walraven_mortality_weight` column. That column is not AHRQ's index weight set and should not be used for scoring. A corrected version with AHRQ v2027.1 content and AHRQ's weights is prepared and will replace it.

## 5. Documentation

Earlier documentation:
- called the output a "van Walraven score" (it is AHRQ's Elixhauser index);
- showed a weight table for the original 30 Elixhauser categories rather than AHRQ's 38 measures;
- suggested risk-tier cut-points that had not been validated.

It also described the package as "validated against AHRQ reference outputs" and "CDC-reviewed". Those statements were inaccurate and are withdrawn. A scientist at CDC, acting in an individual technical capacity, compared an earlier version with AHRQ's SAS programs and identified defects that have since been corrected. This was not an institutional review or endorsement.

## What 2027.1.0 has and has not been tested against

- **Data.** Its code lists and weights are generated from AHRQ's SAS programs.
- **Logic.** Its logic agrees with an independent transliteration of AHRQ's SAS logic on 40,000 synthetic discharges.
- **Pending.** Comparison with output from AHRQ's **executed** SAS software (test tier T7) is **pending**: no SAS environment is available to the maintainers. A run-ready kit is published in the repository.
- **Not established.** The package has not been comprehensively validated, and it has not been tested on real-world data.

See [docs/VALIDATION.md](https://github.com/fopelka-EOCS/elixhauser-ahrq/blob/main/docs/VALIDATION.md).

## Intended use

The AHRQ indices were developed for in-hospital mortality and 30-day readmission in adult inpatient discharges with POA indicators. They do not predict surgical complications or episode costs. They should not be applied to data without POA unless that limitation is stated.

## Real-world effect

We have not measured the effect on real-world data, and we cannot identify who used the affected versions.

## Contact

Open an issue at https://github.com/fopelka-EOCS/elixhauser-ahrq/issues.

The authoritative reference is AHRQ HCUP: https://hcup-us.ahrq.gov/toolssoftware/comorbidityicd10/comorbidity_icd10.jsp

This package is maintained by Episodes of Care Solutions (EOCS). It is not affiliated with, reviewed or endorsed by AHRQ or any other government agency.
