import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SAS = ROOT / "SAS-Programs"
FORMAT_PROGRAM = SAS / "CMR_Format_Program_v2027-1.sas"
MAPPING_PROGRAM = SAS / "CMR_Mapping_Program_v2027-1.sas"
INDEX_PROGRAM = SAS / "CMR_Index_Program_v2027-1.sas"
REFERENCE_FILE = SAS / "CMR-Reference-File-v2027-1.xlsx"


@pytest.fixture(scope="session")
def sas_reference():
    """The independent SAS transliteration (validation/sas_reference.py) and its parsed inputs."""
    spec = importlib.util.spec_from_file_location("sas_reference", ROOT / "validation" / "sas_reference.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fmt, weights = mod.load(str(FORMAT_PROGRAM), str(INDEX_PROGRAM))
    return mod, fmt, weights
