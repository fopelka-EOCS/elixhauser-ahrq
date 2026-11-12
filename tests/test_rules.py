"""T4: rule cases, including every defect found in 2026 (kept as permanent regressions).

Each case states the expected AHRQ result by hand AND is checked against the
independent SAS transliteration (validation/sas_reference.py).

Regression history (see CHANGELOG):
  R1  wrong index weights (fixed 2026-05-08; now compiled from SAS)
  R2  metastatic cancer suppressed leukemia/lymphoma (reported by an external
      reviewer in May/July 2026; not applied until this release)
  R3  POA-exempt codes required POA = Y/W/1 (exempt lists ignored)
  R4  POA "1" accepted as present for every code
  R5  CBVD not-on-admission override unreachable (new stroke + old sequela -> CBVD)
  R6  no POA data silently scored POA-dependent measures as absent
  R7  calculator treated the first typed code as a comorbidity / order-dependent
"""
import itertools
import warnings

import pytest

from elixhauser_ahrq import (ElixhauserMapper, ElixhauserScorer, assign_comorbidities,
                             icd_version_for_date, score_discharge)

M = ElixhauserScorer("mortality").weights
R = ElixhauserScorer("readmission").weights

CASES = [
    # id, principal, secondary, poa, kwargs, expected present measures
    ("R2 METS+leukemia", "Z5111", ["C7800", "C9100"], ["Y", "Y"], {}, {"CANCER_METS", "CANCER_LEUK"}),
    ("R2 METS+lymphoma", "Z5111", ["C7800", "C8590"], ["Y", "Y"], {}, {"CANCER_METS", "CANCER_LYMPH"}),
    ("R2 METS+in situ", "Z5111", ["C7800", "D0510"], ["Y", "Y"], {}, {"CANCER_METS"}),
    ("R2 METS+solid+lymphoma", "Z5111", ["C7800", "C189", "C8590"], ["Y", "Y", "Y"], {}, {"CANCER_METS", "CANCER_LYMPH"}),
    ("SOLID suppresses NSITU", "Z5111", ["C189", "D0510"], ["Y", "Y"], {}, {"CANCER_SOLID"}),
    ("R3 exempt sequela POA blank", "I214", ["I69351"], [""], {}, {"CBVD", "PARALYSIS"}),
    ("R3 exempt sequela POA U", "I214", ["I69351"], ["U"], {}, {"CBVD", "PARALYSIS"}),
    ("R3 exempt sequela POA N", "I214", ["I69351"], ["N"], {}, {"CBVD", "PARALYSIS"}),
    ("R4 HF POA 1", "I214", ["I5022"], ["1"], {}, set()),
    ("HF POA Y", "I214", ["I5022"], ["Y"], {}, {"HF"}),
    ("HF POA W", "I214", ["I5022"], ["W"], {}, {"HF"}),
    ("HF POA N", "I214", ["I5022"], ["N"], {}, set()),
    ("HF POA U", "I214", ["I5022"], ["U"], {}, set()),
    ("HF POA blank", "I214", ["I5022"], [""], {}, set()),
    ("R5 new stroke N + sequela Y", "S7200XA", ["I63213", "I69918"], ["N", "Y"], {}, set()),
    ("R5 new stroke U + sequela Y", "S7200XA", ["I63213", "I69918"], ["U", "Y"], {}, set()),
    ("stroke on admission wins over another N", "S7200XA", ["I63213", "I639"], ["Y", "N"], {}, {"CBVD"}),
    ("sequela alone Y", "S7200XA", ["I69918"], ["Y"], {}, {"CBVD"}),
    ("R7 principal only", "I5022", [], [], {}, set()),
    ("R7 principal repeated as secondary", "I5022", ["I5022"], ["Y"], {}, {"HF"}),
    ("DIAB_CX > DIAB_UNCX", "I214", ["E119", "E1122"], ["Y", "Y"], {}, {"DIAB_CX"}),
    ("HTN_CX > HTN_UNCX", "I214", ["I10", "I129"], ["Y", "Y"], {}, {"HTN_CX"}),
    ("LIVER_SEV > LIVER_MLD", "I214", ["K7030", "K766"], ["Y", "Y"], {}, {"LIVER_SEV"}),
    ("RENLFL_MOD alone", "I214", ["N1831"], ["Y"], {}, {"RENLFL_MOD"}),
    ("LIVER_MLD alone", "I214", ["K7030"], ["Y"], {}, {"LIVER_MLD"}),
    ("RENLFL_SEV > RENLFL_MOD", "I214", ["N1831", "N186"], ["Y", "Y"], {}, {"RENLFL_SEV"}),
    ("combined HTN/HF/CKD label, POA N", "I214", ["I130"], ["N"], {}, {"HTN_CX"}),
    ("combined HTN/HF/CKD label, POA Y", "I214", ["I132"], ["Y"], {}, {"HTN_CX", "HF", "RENLFL_SEV"}),
    # FY2027 changes (v2026.1 -> v2027.1)
    ("FY27 C7831 added to METS", "I214", ["C7831"], ["Y"], {}, {"CANCER_METS"}),
    ("FY27 C7983 added to METS", "I214", ["C7983"], ["N"], {}, {"CANCER_METS"}),
    ("FY27 D6911 COAG POA Y", "I214", ["D6911"], ["Y"], {}, {"COAG"}),
    ("FY27 D6919 COAG POA N", "I214", ["D6919"], ["N"], {}, set()),
    ("FY27 K740A LIVER_MLD", "I214", ["K740A"], ["Y"], {}, {"LIVER_MLD"}),
    ("FY27 K7683 LIVER_MLD", "I214", ["K7683"], ["W"], {}, {"LIVER_MLD"}),
    ("FY27 Z6818 exempt in v44, POA N", "I214", ["Z6818"], ["N"], {"icd_version": 44}, {"WGHTLOSS"}),
    ("FY27 Z6818 not exempt in v43, POA N", "I214", ["Z6818"], ["N"], {"icd_version": 43}, set()),
    ("FY27 F0670 removed from DEMENTIA", "I214", ["F0670", "F0671"], ["Y", "Y"], {}, set()),
    ("FY27 DRUG rename", "I214", ["F1120"], ["Y"], {}, {"DRUG"}),
]


def _oracle(sas_reference, principal, secondary, poa, kwargs, poa_available=True):
    mod, fmt, weights = sas_reference
    year, dqtr = None, None
    if kwargs.get("icd_version") == 43:
        year, dqtr = 2026, 2
    rec = {"dx": [principal] + list(secondary), "poa": [""] + list(poa) if poa is not None else None,
           "poa_available": poa_available, "year": year, "dqtr": dqtr, "ndx": None}
    out = mod.assign(rec, fmt)
    out.pop("ICDVER")
    readm, mort = mod.index(out, weights)
    return {k[4:]: v for k, v in out.items()}, mort, readm


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_rule_case(case, sas_reference):
    _, principal, secondary, poa, kwargs, expected = case
    res = score_discharge(principal, secondary, poa, **kwargs)
    assert set(res["present"]) == expected
    assert res["mortality_index"] == sum(M[m] for m in expected)
    assert res["readmission_index"] == sum(R[m] for m in expected)
    assert not res["partial"]
    flags, mort, readm = _oracle(sas_reference, principal, secondary, poa, kwargs)
    assert {k for k, v in flags.items() if v == 1} == expected
    assert (mort, readm) == (res["mortality_index"], res["readmission_index"])


def test_r2_scores_rise_with_leukemia():
    res = score_discharge("Z5111", ["C7800", "C9100"], ["Y", "Y"])
    assert (res["mortality_index"], res["readmission_index"]) == (31, 21)


def test_r3_exempt_sequela_score():
    res = score_discharge("I214", ["I69351"], [""])
    assert (res["mortality_index"], res["readmission_index"]) == (9, 3)


def test_r6_no_poa_is_partial_not_zero(sas_reference):
    res = score_discharge("I214", ["I5022", "E119", "C7800"])
    assert res["poa_available"] is False
    assert res["partial"] is True
    assert res["flags"]["HF"] is None and res["flags"]["CBVD"] is None
    assert len(res["not_assessable"]) == 18
    assert set(res["present"]) == {"DIAB_UNCX", "CANCER_METS"}
    flags, mort, readm = _oracle(sas_reference, "I214", ["I5022", "E119", "C7800"], None, {}, poa_available=False)
    assert {k for k, v in flags.items() if v is None} == set(res["not_assessable"])
    assert (mort, readm) == (res["mortality_index"], res["readmission_index"])


def test_r6_combined_label_without_poa_sets_only_neutral_half():
    flags = assign_comorbidities("I214", ["I132"]).flags
    assert flags["HTN_CX"] is True and flags["HF"] is None and flags["RENLFL_SEV"] is None


def test_r7_order_independence():
    sec = ["C7800", "C9100", "I5022", "I69351", "E1122", "E119", "N186", "N184"]
    poa = ["Y", "Y", "Y", "", "Y", "Y", "Y", "N"]
    baseline = score_discharge("I214", sec, poa)
    for perm in itertools.islice(itertools.permutations(range(len(sec))), 0, 2000, 7):
        r = score_discharge("I214", [sec[i] for i in perm], [poa[i] for i in perm])
        assert r["flags"] == baseline["flags"]


def test_legacy_list_api_treats_first_code_as_principal():
    m = ElixhauserMapper()
    assert m.map_patient_diagnoses(["I5022"], ["Y"])["HF"] is False
    assert m.map_patient_diagnoses(["I214", "I5022"], ["Y", "Y"])["HF"] is True
    assert m.map_patient_diagnoses(["I5022"], ["Y"], principal_included=False)["HF"] is True


def test_input_normalisation():
    """Decimals, case and whitespace in codes; case in POA (SAS expects clean input)."""
    res = score_discharge(" i21.4 ", ["i50.22 "], ["y"])
    assert res["present"] == ["HF"]


def test_icd_version_from_discharge_date():
    assert icd_version_for_date("2015-10-01") == 33
    assert icd_version_for_date("2026-09-30") == 43
    assert icd_version_for_date("2026-10-01") == 44
    assert icd_version_for_date("2027-09-30") == 44
    with pytest.warns(UserWarning):
        assert icd_version_for_date("2027-10-01") == 44
    with pytest.warns(UserWarning):
        assert icd_version_for_date("2015-09-30") == 44  # AHRQ ELSE branch


def test_discharge_date_selects_exempt_list():
    assert score_discharge("I214", ["Z6818"], ["N"], discharge_date="2026-10-15")["present"] == ["WGHTLOSS"]
    assert score_discharge("I214", ["Z6818"], ["N"], discharge_date="2026-09-15")["present"] == []


def test_drug_abuse_alias_is_deprecated():
    with pytest.warns(DeprecationWarning):
        assert ElixhauserScorer("mortality").calculate_score({"DRUG_ABUSE": True}) == -7


def test_no_default_risk_tiers():
    with pytest.raises(ValueError):
        ElixhauserScorer("mortality").stratify_risk(10)
    assert ElixhauserScorer("mortality").stratify_risk(10, (5, 15)).value == "Moderate"


def test_dataframe_api_matches_single_record():
    import pandas as pd
    df = pd.DataFrame({
        "enc": [1, 1, 1, 2, 2],
        "seq": [2, 1, 3, 1, 2],
        "dx": ["I5022", "I214", "C9100", "I5022", "E119"],
        "poa": ["Y", "", "Y", "Y", "N"],
    })
    out = ElixhauserMapper().map_dataframe(df, "enc", "dx", "poa", "seq")
    scored = ElixhauserScorer("mortality").score_dataframe(out)
    row1 = scored[scored.enc == 1].iloc[0]
    row2 = scored[scored.enc == 2].iloc[0]
    assert bool(row1["HF"]) and bool(row1["CANCER_LEUK"]) and row1["elixhauser_score"] == M["HF"] + M["CANCER_LEUK"]
    assert not bool(row2["HF"]) and bool(row2["DIAB_UNCX"])  # I5022 is principal for encounter 2


def test_dataframe_without_poa_has_na_and_partial_flag():
    import pandas as pd
    df = pd.DataFrame({"enc": [1, 1], "seq": [1, 2], "dx": ["I214", "I5022"]})
    out = ElixhauserMapper().map_dataframe(df, "enc", "dx", dx_sequence_col="seq")
    assert pd.isna(out.loc[0, "HF"])
    scored = ElixhauserScorer("mortality").score_dataframe(out)
    assert bool(scored.loc[0, "index_partial"])


def test_trace_explains_each_code():
    res = assign_comorbidities("I5022", ["I5022", "Z0000", "I69351"], ["N", "Y", ""])
    by_pos = {t.position: t for t in res.trace}
    assert "principal" in by_pos[1].note
    assert by_pos[2].counted == () and "not Y or W" in by_pos[2].note
    assert by_pos[3].ahrq_label is None
    assert by_pos[4].poa_exempt and set(by_pos[4].counted) == {"PARALYSIS", "CBVD_SQLA"}
