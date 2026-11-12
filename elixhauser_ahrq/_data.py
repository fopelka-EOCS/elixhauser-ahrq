"""Access to the bundled AHRQ data (compiled from AHRQ's SAS programs by
``tools/build_data.py``; never edited by hand)."""

import datetime as _dt
import gzip
import json
import warnings
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "cmr_v2027_1.json.gz"

#: ICD-10-CM versions covered by AHRQ's POA-exempt lists in this release.
MIN_ICD_VERSION = 33   # FY2016 (October 2015 - September 2016)
MAX_ICD_VERSION = 44   # FY2027 (October 2026 - September 2027)


@lru_cache(maxsize=1)
def ahrq_data() -> dict:
    with gzip.open(DATA_FILE, "rb") as fh:
        data = json.loads(fh.read().decode("utf-8"))
    data["exempt"] = {int(k): frozenset(v) for k, v in data["exempt"].items()}
    return data


def icd_version_for(year=None, quarter=None) -> int:
    """ICD-10-CM version (ICDVER) exactly as CMR_Mapping_Program_v2027-1.sas
    assigns it from discharge YEAR and calendar quarter DQTR.

    October-December of year Y belong to fiscal year Y+1. Any date outside
    October 2015 - September 2027, or a missing date, falls to AHRQ's ELSE
    branch, which is version 44.
    """
    if year is None or quarter is None:
        return MAX_ICD_VERSION
    fiscal_year = year + 1 if quarter == 4 else year
    if quarter not in (1, 2, 3, 4) or not (2016 <= fiscal_year <= 2027):
        return MAX_ICD_VERSION
    return MIN_ICD_VERSION + (fiscal_year - 2016)


def icd_version_for_date(discharge_date) -> int:
    """ICD-10-CM version for a discharge date (``datetime.date`` or 'YYYY-MM-DD').

    Warns when the date is outside the window this AHRQ release covers
    (October 2015 - September 2027); the result then follows AHRQ's default.
    """
    if discharge_date is None:
        return MAX_ICD_VERSION
    if isinstance(discharge_date, str):
        discharge_date = _dt.date.fromisoformat(discharge_date[:10])
    if isinstance(discharge_date, _dt.datetime):
        discharge_date = discharge_date.date()
    if not (_dt.date(2015, 10, 1) <= discharge_date <= _dt.date(2027, 9, 30)):
        warnings.warn(
            f"Discharge date {discharge_date} is outside the window covered by AHRQ "
            "Elixhauser Comorbidity Software Refined v2027.1 (October 2015 - September 2027). "
            "Codes introduced after September 2027 will not be recognised; use the AHRQ "
            "release for that fiscal year.",
            stacklevel=3,
        )
    quarter = (discharge_date.month - 1) // 3 + 1
    return icd_version_for(discharge_date.year, quarter)
