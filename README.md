# elixhauser-ahrq

Python package for AHRQ Elixhauser Comorbidity Index calculation using ICD-10-CM diagnosis codes.

## Quick Start
```python
from elixhauser_ahrq import ElixhauserMapper, ElixhauserScorer

mapper = ElixhauserMapper()
patient_dx = ["E119", "I10", "I509"]
flags = mapper.map_patient_diagnoses(patient_dx)

scorer = ElixhauserScorer(index_type="mortality")
score = scorer.calculate_score(flags)
print(f"Score: {score}")
```

## Installation
```bash
cd C:\Users\FGOpe\elixhauser-ahrq
python -m pip install -e . --break-system-packages
```
## License & Related Products

### This Package (MIT License)

`elixhauser-ahrq` is **open source** under the MIT License. You are free to use, modify, and distribute this package for any purpose, including commercial use.

This package provides:
- AHRQ Elixhauser Comorbidity Index v2026.1 implementation
- ICD-10-CM to comorbidity category mapping (4,568 codes)
- Risk scoring with AHRQ-validated weights
- Python classes for integration into your analytics pipelines

### EOCS Analytics Platform (Commercial License)

For organizations using the PACES episode grouper, **EOCS Analytics** is a separate commercial product that transforms PACES outputs into actionable dashboards.

EOCS Analytics includes:
- dbt transformation models for Snowflake, PostgreSQL, BigQuery, and other databases
- Pre-built dashboard queries (Surgeon, Facility, Payer perspectives)
- Risk stratification using this Elixhauser package
- Complication flagging and sequelae linkage
- Implementation support and documentation

**Key differentiator:** EOCS Analytics runs entirely in YOUR environment. No data leaves your security boundary. No SaaS fees. You own the code.

For licensing information: [fopelka@eocs.ltd](mailto:fopelka@eocs.ltd) | [www.eocs.ltd](https://www.eocs.ltd)

---

## Attribution

This package uses reference data from the Agency for Healthcare Research and Quality (AHRQ) Healthcare Cost and Utilization Project (HCUP). AHRQ HCUP tools are provided for public use.

For more information: https://hcup-us.ahrq.gov/toolssoftware/comorbidityicd10/comorbidity_icd10.jsp
