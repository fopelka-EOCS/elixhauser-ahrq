"""
elixhauser_ahrq - Python reimplementation of AHRQ's Elixhauser Comorbidity
Software Refined for ICD-10-CM, v2027.1 (FY2027; ICD-10-CM codes October 2015
through September 2027).

* Assigns the 38 AHRQ Elixhauser comorbidity measures from secondary diagnoses,
  honouring present-on-admission (POA) indicators and AHRQ's POA-exempt lists.
* Computes AHRQ's in-hospital mortality and 30-day readmission indices.

Code lists, POA-exempt lists and weights are compiled from AHRQ's SAS programs.
This is an independent implementation; it is not produced, reviewed or endorsed
by AHRQ. See docs/VALIDATION.md for exactly what has and has not been tested.
"""

__version__ = "2027.1.0"
AHRQ_VERSION = "2027.1"
__author__ = "Frank G. Opelka, MD, FACS - Episodes of Care Solutions (EOCS)"

from .loader import ElixhauserLoader, load_ahrq_data
from .mapper import (ElixhauserMapper, ComorbidityResult, CodeTrace,
                     assign_comorbidities)
from .scorer import ElixhauserScorer, RiskStratum, score_discharge
from ._data import icd_version_for, icd_version_for_date

__all__ = [
    "AHRQ_VERSION",
    "ElixhauserLoader",
    "load_ahrq_data",
    "ElixhauserMapper",
    "ComorbidityResult",
    "CodeTrace",
    "assign_comorbidities",
    "ElixhauserScorer",
    "RiskStratum",
    "score_discharge",
    "icd_version_for",
    "icd_version_for_date",
]
