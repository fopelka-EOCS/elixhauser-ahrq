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
