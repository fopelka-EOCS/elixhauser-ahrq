"""T1-T3: the bundled data and the mapper's tables equal AHRQ's own files.

Nothing here compares against hand-typed expectations: every expected value is
read from AHRQ's SAS programs or reference workbook at test time.
"""
import re
import subprocess
import sys

import pandas as pd
import pytest

from elixhauser_ahrq import ElixhauserScorer
from elixhauser_ahrq._data import ahrq_data
from elixhauser_ahrq.mapper import COMBINED_LABELS, label_parts

from conftest import MAPPING_PROGRAM, REFERENCE_FILE, ROOT


def test_bundled_data_is_a_fresh_build_of_the_sas_programs():
    """tools/build_data.py --check: bundled file is byte-identical to a rebuild."""
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "build_data.py"), "--check"],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr


# T1 ---------------------------------------------------------------------
@pytest.mark.parametrize("kind", ["mortality", "readmission"])
def test_weights_equal_independent_parse_of_index_program(sas_reference, kind):
    _, _, weights = sas_reference
    expected = {k[4:]: v for k, v in weights[kind].items()}
    actual = ElixhauserScorer(kind).weights
    assert len(expected) == 38
    assert actual == expected


def test_v2027_spot_weights():
    """Values quoted in the FY2027 impact assessment, read from the SAS index program."""
    m, r = ElixhauserScorer("mortality").weights, ElixhauserScorer("readmission").weights
    assert (m["DRUG"], r["DRUG"]) == (-7, 6)
    assert (m["CANCER_METS"], r["CANCER_METS"]) == (22, 11)
    assert "DRUG_ABUSE" not in m and "CBVD_POA" not in m and "CBVD" in m


# T2 ---------------------------------------------------------------------
@pytest.fixture(scope="module")
def reference_workbook():
    df = pd.read_excel(REFERENCE_FILE, sheet_name="DX_to_Comorb_Mapping", skiprows=1, dtype=str)
    df = df[df.iloc[:, 0].str.strip().str.lower() != "end of content"]
    measures = pd.read_excel(REFERENCE_FILE, sheet_name="Comorbidity_Measures", skiprows=1, dtype=str)
    measures = measures[measures.iloc[:, 0].str.strip().str.lower() != "end of content"]
    return df, measures


def test_code_set_equals_reference_workbook(reference_workbook):
    df, _ = reference_workbook
    assert set(df["ICD-10-CM Diagnosis"].str.strip()) == set(ahrq_data()["comfmt"])
    assert len(ahrq_data()["comfmt"]) == 4573


def test_every_code_maps_to_the_workbook_measures(reference_workbook):
    """Each code's (POA-independent + POA-dependent) measures equal the workbook flags."""
    df, _ = reference_workbook
    cols = list(df.columns[3:])
    assert len(cols) == 39  # 37 measures + CBVD_POA + CBVD_SQLA
    comfmt = ahrq_data()["comfmt"]
    mismatches = []
    for _, row in df.iterrows():
        code = row["ICD-10-CM Diagnosis"].strip()
        wb = {c for c in cols if str(row[c]).strip() in ("1", "1.0")}
        indep, dep = label_parts(comfmt[code])
        if set(indep) | set(dep) != wb:
            mismatches.append((code, comfmt[code], sorted(wb)))
    assert not mismatches, mismatches[:10]


def test_poa_dependence_equals_workbook(reference_workbook):
    _, measures = reference_workbook
    poa_col = [c for c in measures.columns if "present on admission" in c.lower()][0]
    name_col = measures.columns[0]
    wb = {r[name_col].strip()[4:] for _, r in measures.iterrows() if r[poa_col].strip() == "Yes"}
    pkg = {m["name"] for m in ahrq_data()["measures"] if m["poa_dependent"]}
    assert pkg == wb
    assert len(pkg) == 18


# T2b: the combined-label table equals the SAS mapping program's IF statements
def _sas_if_assignments(text, start_marker, end_marker):
    seg = text[text.index(start_marker):text.index(end_marker)]
    found = {}
    for m in re.finditer(r'IF\s+DXVALUE\s*=\s*"(\w+)"\s+THEN\s+(?:DO;(.*?)END;|(CMR_\w+)\s*=\s*1)',
                         seg, re.DOTALL):
        label = m.group(1)
        targets = re.findall(r"CMR_(\w+)\s*=\s*1", m.group(2)) if m.group(2) else [m.group(3)[4:]]
        found.setdefault(label, []).extend(targets)
    return found


def test_combined_labels_equal_sas_mapping_program():
    text = MAPPING_PROGRAM.read_text(encoding="latin-1")
    neutral = _sas_if_assignments(text, "Assign Comorbidities that are neutral to POA", "%if &POA. = 1 %then %do;\n         /*")
    dependent = _sas_if_assignments(text, "DO K = 1 TO 19;", "requiring that the diagnosis is not POA")
    derived = {}
    for label in set(neutral) | set(dependent):
        derived[label] = (tuple(neutral.get(label, ())), tuple(dependent.get(label, ())))
    assert derived == COMBINED_LABELS


def test_every_comfmt_label_is_handled():
    for label in set(ahrq_data()["comfmt"].values()):
        label_parts(label)  # raises on an unknown label


# T3 ---------------------------------------------------------------------
def test_exempt_lists_equal_independent_parse(sas_reference):
    _, fmt, _ = sas_reference
    ref = fmt.exempt_sets()
    data = ahrq_data()["exempt"]
    assert sorted(data) == list(range(33, 45))
    for v in range(33, 45):
        assert data[v] == ref[v], f"exempt list v{v} differs"


def test_comfmt_equals_independent_parse(sas_reference):
    _, fmt, _ = sas_reference
    assert ahrq_data()["comfmt"] == fmt.comfmt
