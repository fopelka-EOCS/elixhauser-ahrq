"""
test_regression.py — Elixhauser AHRQ Python Package Regression Tests
=====================================================================

Purpose
-------
Guard against weight drift and logic bugs by anchoring the Python package
output to values derived directly from the AHRQ SAS programs
(CMR_Index_Program_v2026-1.sas, CMR_Mapping_Program_v2026-1.sas).

Test structure
--------------
  Suite A: Weight table integrity (no Excel file required)
  Suite B: Scorer golden records — known flag → known score
  Suite C: POA logic (mapper, no Excel required — uses a patched lookup)
  Suite D: Principal diagnosis exclusion
  Suite E: Loader footer filtering (requires CMR-Reference-File-v2026-1.xlsx)

Run all suites:
    python -m pytest test_regression.py -v

Run only suites that don't need the Excel file:
    python -m pytest test_regression.py -v -m "not requires_excel"

Notes
-----
- All expected scores are computed by hand from the SAS mwXXX / rwXXX weights.
- When AHRQ releases a new version, update EXPECTED_MORTALITY_WEIGHTS and
  EXPECTED_READMISSION_WEIGHTS from the new SAS Index Program, then re-run.
"""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

# ---------------------------------------------------------------------------
# Guard: make sure we can import the corrected package
# ---------------------------------------------------------------------------
try:
    from elixhauser_ahrq.scorer import ElixhauserScorer, RiskStratum
    from elixhauser_ahrq.mapper import ElixhauserMapper, _POA_NEUTRAL, _POA_REQUIRED
    from elixhauser_ahrq.loader import ElixhauserLoader
    PACKAGE_AVAILABLE = True
except ImportError:
    PACKAGE_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not PACKAGE_AVAILABLE,
    reason="elixhauser_ahrq package not importable — check installation"
)


# ===========================================================================
# Ground-truth weight tables (source: CMR_Index_Program_v2026-1.sas)
# ===========================================================================

EXPECTED_MORTALITY_WEIGHTS = {
    'AIDS':          -4,  'ALCOHOL':       -1,  'ANEMDEF':       -3,
    'AUTOIMMUNE':     0,  'BLDLOSS':       -4,  'CANCER_LEUK':    9,
    'CANCER_LYMPH':   5,  'CANCER_METS':   22,  'CANCER_NSITU':   0,
    'CANCER_SOLID':  10,  'CBVD':           5,  'COAG':          14,
    'DEMENTIA':       5,  'DEPRESS':       -8,  'DIAB_CX':       -2,
    'DIAB_UNCX':      0,  'DRUG_ABUSE':    -7,  'HF':            14,
    'HTN_CX':         1,  'HTN_UNCX':       0,  'LIVER_MLD':      2,
    'LIVER_SEV':     16,  'LUNG_CHRONIC':   2,  'NEURO_MOVT':    -1,
    'NEURO_OTH':     22,  'NEURO_SEIZ':     2,  'OBESE':         -7,
    'PARALYSIS':      4,  'PERIVASC':       3,  'PSYCHOSES':     -9,
    'PULMCIRC':       4,  'RENLFL_MOD':     3,  'RENLFL_SEV':     7,
    'THYROID_HYPO':  -3,  'THYROID_OTH':   -8,  'ULCER_PEPTIC':   0,
    'VALVE':          0,  'WGHTLOSS':      13,
}

EXPECTED_READMISSION_WEIGHTS = {
    'AIDS':           5,  'ALCOHOL':        3,  'ANEMDEF':        5,
    'AUTOIMMUNE':     2,  'BLDLOSS':        2,  'CANCER_LEUK':   10,
    'CANCER_LYMPH':   7,  'CANCER_METS':   11,  'CANCER_NSITU':   0,
    'CANCER_SOLID':   7,  'CBVD':           0,  'COAG':           3,
    'DEMENTIA':       1,  'DEPRESS':        2,  'DIAB_CX':        4,
    'DIAB_UNCX':      0,  'DRUG_ABUSE':     6,  'HF':             7,
    'HTN_CX':         0,  'HTN_UNCX':       0,  'LIVER_MLD':      3,
    'LIVER_SEV':     10,  'LUNG_CHRONIC':   4,  'NEURO_MOVT':     1,
    'NEURO_OTH':      2,  'NEURO_SEIZ':     5,  'OBESE':         -2,
    'PARALYSIS':      3,  'PERIVASC':       1,  'PSYCHOSES':      6,
    'PULMCIRC':       3,  'RENLFL_MOD':     4,  'RENLFL_SEV':     8,
    'THYROID_HYPO':   0,  'THYROID_OTH':    0,  'ULCER_PEPTIC':   2,
    'VALVE':          0,  'WGHTLOSS':       6,
}


# ===========================================================================
# Suite A — Weight table integrity
# ===========================================================================

class TestWeightTableIntegrity:
    """Verify every weight in both dictionaries against SAS source."""

    def test_mortality_weight_count(self):
        """Exactly 38 mortality weights (one per comorbidity measure)."""
        scorer = ElixhauserScorer(index_type="mortality")
        assert len(scorer.MORTALITY_WEIGHTS) == 38, (
            f"Expected 38 mortality weights, got {len(scorer.MORTALITY_WEIGHTS)}"
        )

    def test_readmission_weight_count(self):
        """Exactly 38 readmission weights."""
        scorer = ElixhauserScorer(index_type="readmission")
        assert len(scorer.READMISSION_WEIGHTS) == 38, (
            f"Expected 38 readmission weights, got {len(scorer.READMISSION_WEIGHTS)}"
        )

    def test_all_mortality_weights_match_sas(self):
        """Every mortality weight must match SAS mwXXX value exactly."""
        scorer = ElixhauserScorer(index_type="mortality")
        mismatches = {}
        for cat, expected in EXPECTED_MORTALITY_WEIGHTS.items():
            actual = scorer.MORTALITY_WEIGHTS.get(cat)
            if actual != expected:
                mismatches[cat] = {'expected': expected, 'actual': actual}
        assert not mismatches, (
            f"Mortality weight mismatches vs SAS:\n"
            + "\n".join(f"  {k}: SAS={v['expected']}, Python={v['actual']}"
                        for k, v in sorted(mismatches.items()))
        )

    def test_all_readmission_weights_match_sas(self):
        """Every readmission weight must match SAS rwXXX value exactly."""
        scorer = ElixhauserScorer(index_type="readmission")
        mismatches = {}
        for cat, expected in EXPECTED_READMISSION_WEIGHTS.items():
            actual = scorer.READMISSION_WEIGHTS.get(cat)
            if actual != expected:
                mismatches[cat] = {'expected': expected, 'actual': actual}
        assert not mismatches, (
            f"Readmission weight mismatches vs SAS:\n"
            + "\n".join(f"  {k}: SAS={v['expected']}, Python={v['actual']}"
                        for k, v in sorted(mismatches.items()))
        )

    def test_no_split_cbvd_keys(self):
        """Scorer must use combined CBVD key, not CBVD_POA or CBVD_SQLA."""
        scorer_m = ElixhauserScorer(index_type="mortality")
        scorer_r = ElixhauserScorer(index_type="readmission")
        for scorer in (scorer_m, scorer_r):
            assert 'CBVD_POA' not in scorer.weights, \
                "CBVD_POA must not be a scorer key — use combined CBVD"
            assert 'CBVD_SQLA' not in scorer.weights, \
                "CBVD_SQLA must not be a scorer key — use combined CBVD"
            assert 'CBVD' in scorer.weights, \
                "Combined CBVD key must be present in scorer weights"

    @pytest.mark.parametrize("cat,expected", [
        ('AIDS',        -4),  # Qunna's example — was 11 in buggy version
        ('HF',          14),  # Qunna's example — was 9
        ('WGHTLOSS',    13),  # Qunna's example — was 9
        ('NEURO_OTH',   22),  # Largest weight, was wrong at 7
        ('CANCER_METS', 22),  # Critical cancer weight, was 14
        ('PSYCHOSES',   -9),  # Large negative, was -5
        ('THYROID_OTH', -8),  # Was 0 — completely missed
    ])
    def test_mortality_spot_checks(self, cat, expected):
        """Key mortality weights cited in external review and other critical values."""
        scorer = ElixhauserScorer(index_type="mortality")
        assert scorer.MORTALITY_WEIGHTS[cat] == expected, (
            f"Mortality {cat}: expected {expected}, got {scorer.MORTALITY_WEIGHTS[cat]}"
        )

    @pytest.mark.parametrize("cat,expected", [
        ('CANCER_LEUK',  10),  # Was -2 in buggy version
        ('HF',            7),  # Was 13
        ('OBESE',        -2),  # Was +2
        ('ULCER_PEPTIC',  2),  # Was 0
    ])
    def test_readmission_spot_checks(self, cat, expected):
        """Key readmission weights that were significantly wrong."""
        scorer = ElixhauserScorer(index_type="readmission")
        assert scorer.READMISSION_WEIGHTS[cat] == expected, (
            f"Readmission {cat}: expected {expected}, got {scorer.READMISSION_WEIGHTS[cat]}"
        )


# ===========================================================================
# Suite B — Scorer golden records
# ===========================================================================

class TestScorerGoldenRecords:
    """
    Golden records: known comorbidity flag sets with scores manually computed
    from SAS weights.  If any score changes, a weight was altered.
    """

    def test_golden_mortality_high_acuity(self):
        """
        Patient: HF + CANCER_METS + RENLFL_MOD
        Expected mortality: 14 + 22 + 3 = 39
        Expected readmission: 7 + 11 + 4 = 22
        """
        flags = {'HF': True, 'CANCER_METS': True, 'RENLFL_MOD': True,
                 'CBVD': False}
        scorer = ElixhauserScorer(index_type="mortality")
        assert scorer.calculate_score(flags) == 39

    def test_golden_readmission_high_acuity(self):
        flags = {'HF': True, 'CANCER_METS': True, 'RENLFL_MOD': True,
                 'CBVD': False}
        scorer = ElixhauserScorer(index_type="readmission")
        assert scorer.calculate_score(flags) == 22

    def test_golden_mortality_negative_net(self):
        """
        Patient: AIDS + DEPRESS + PSYCHOSES (all large negative mortality weights)
        Expected mortality: -4 + (-8) + (-9) = -21
        """
        flags = {'AIDS': True, 'DEPRESS': True, 'PSYCHOSES': True}
        scorer = ElixhauserScorer(index_type="mortality")
        assert scorer.calculate_score(flags) == -21

    def test_golden_readmission_mixed(self):
        """
        Patient: COAG + LIVER_SEV + DIAB_CX + OBESE
        Expected readmission: 3 + 10 + 4 + (-2) = 15
        """
        flags = {'COAG': True, 'LIVER_SEV': True, 'DIAB_CX': True, 'OBESE': True}
        scorer = ElixhauserScorer(index_type="readmission")
        assert scorer.calculate_score(flags) == 15

    def test_golden_no_comorbidities(self):
        """Patient with no comorbidities must score 0."""
        flags = {k: False for k in EXPECTED_MORTALITY_WEIGHTS}
        scorer_m = ElixhauserScorer(index_type="mortality")
        scorer_r = ElixhauserScorer(index_type="readmission")
        assert scorer_m.calculate_score(flags) == 0
        assert scorer_r.calculate_score(flags) == 0

    def test_golden_all_comorbidities_mortality(self):
        """
        All 38 comorbidities present — score equals sum of all mortality weights.
        Expected: sum(EXPECTED_MORTALITY_WEIGHTS.values())
        """
        flags = {k: True for k in EXPECTED_MORTALITY_WEIGHTS}
        scorer = ElixhauserScorer(index_type="mortality")
        expected_total = sum(EXPECTED_MORTALITY_WEIGHTS.values())
        assert scorer.calculate_score(flags) == expected_total

    def test_golden_cbvd_scoring(self):
        """
        CBVD combined flag should use the single CBVD key.
        Mortality weight for CBVD = 5.
        """
        flags = {'CBVD': True}
        scorer = ElixhauserScorer(index_type="mortality")
        assert scorer.calculate_score(flags) == 5

    def test_risk_stratification_low(self):
        scorer = ElixhauserScorer(index_type="mortality")
        assert scorer.stratify_risk(2).value == "Low"

    def test_risk_stratification_moderate(self):
        scorer = ElixhauserScorer(index_type="mortality")
        assert scorer.stratify_risk(10).value == "Moderate"

    def test_risk_stratification_high(self):
        scorer = ElixhauserScorer(index_type="mortality")
        assert scorer.stratify_risk(15).value == "High"


# ===========================================================================
# Suite C — POA logic (mapper, no Excel required)
# ===========================================================================

def _build_mock_mapper():
    """
    Return an ElixhauserMapper with a patched loader so no Excel file is needed.
    The mock lookup table has a few synthetic ICD-10 codes for testing.
    """
    # Simulate the columns the real loader would produce
    all_cols = list(EXPECTED_MORTALITY_WEIGHTS.keys()) + ['CBVD_POA', 'CBVD_SQLA']

    # Synthetic lookup:
    #   'E119' (diabetes uncomplicated) → DIAB_UNCX
    #   'I509' (heart failure) → HF (POA-required)
    #   'Z8673' (CBVD sequela history) → CBVD_SQLA (POA-required)
    #   'I639'  (acute stroke, no POA) → CBVD_POA (POA-required)
    lookup = {
        'E119':  {**{c: False for c in all_cols}, 'DIAB_UNCX': True},
        'I509':  {**{c: False for c in all_cols}, 'HF': True},
        'Z8673': {**{c: False for c in all_cols}, 'CBVD_SQLA': True},
        'I639':  {**{c: False for c in all_cols}, 'CBVD_POA': True},
    }

    mock_loader = MagicMock()
    mock_loader.dx_mapping = pd.DataFrame()   # not used directly after patch

    mapper = ElixhauserMapper.__new__(ElixhauserMapper)
    mapper.loader = mock_loader
    mapper.comorbidity_cols = all_cols
    mapper.lookup = lookup
    return mapper


class TestPOALogic:

    def test_poa_neutral_set_contains_expected_categories(self):
        """Spot-check POA-neutral set from SAS COMANYPOA array."""
        for cat in ('AIDS', 'ALCOHOL', 'DIAB_CX', 'CANCER_METS', 'HTN_CX', 'OBESE'):
            assert cat in _POA_NEUTRAL, f"{cat} should be POA-neutral"

    def test_poa_required_set_contains_expected_categories(self):
        """Spot-check POA-required set from SAS COMPOA array."""
        for cat in ('HF', 'COAG', 'ANEMDEF', 'PARALYSIS', 'WGHTLOSS', 'VALVE',
                    'CBVD_POA', 'CBVD_SQLA'):
            assert cat in _POA_REQUIRED, f"{cat} should be POA-required"

    def test_poa_neutral_category_set_regardless_of_poa(self):
        """POA-neutral categories (e.g. DIAB_UNCX) should be flagged
        regardless of whether POA indicator is Y, N, or absent."""
        mapper = _build_mock_mapper()
        # Pass E119 (DIAB_UNCX) as secondary dx with POA=N
        # Principal = dummy, secondary = E119 with POA=N
        flags = mapper.map_patient_diagnoses(['DUMMY', 'E119'], [None, 'N'])
        assert flags.get('DIAB_UNCX') is True, \
            "DIAB_UNCX (POA-neutral) should be True regardless of POA indicator"

    def test_poa_required_category_suppressed_when_poa_no(self):
        """HF (POA-required) must NOT be flagged when POA='N'."""
        mapper = _build_mock_mapper()
        flags = mapper.map_patient_diagnoses(['DUMMY', 'I509'], [None, 'N'])
        assert flags.get('HF') is False, \
            "HF (POA-required) must be False when POA='N'"

    def test_poa_required_category_set_when_poa_yes(self):
        """HF must be flagged when POA='Y'."""
        mapper = _build_mock_mapper()
        flags = mapper.map_patient_diagnoses(['DUMMY', 'I509'], [None, 'Y'])
        assert flags.get('HF') is True, \
            "HF (POA-required) must be True when POA='Y'"

    def test_w_indicator_treated_as_poa_yes(self):
        """
        POA='W' (clinically undetermined) must be treated as present-on-admission,
        matching SAS: DXPOA(I) IN ("Y","W").
        """
        mapper = _build_mock_mapper()
        flags = mapper.map_patient_diagnoses(['DUMMY', 'I509'], [None, 'W'])
        assert flags.get('HF') is True, \
            "POA='W' must be treated as present-on-admission (matches SAS)"

    def test_cbvd_sqla_requires_poa_yes(self):
        """
        CBVD_SQLA is inside SAS COMPOA (POA=Yes required).
        Python was previously treating _SQLA as POA=No — verify fix.
        """
        mapper = _build_mock_mapper()
        # With POA=Y: CBVD_SQLA should fire, and combined CBVD=True
        flags_poa_yes = mapper.map_patient_diagnoses(['DUMMY', 'Z8673'], [None, 'Y'])
        assert flags_poa_yes.get('CBVD') is True, \
            "CBVD_SQLA with POA=Y should produce combined CBVD=True"

        # With POA=N: CBVD_SQLA should not fire
        flags_poa_no = mapper.map_patient_diagnoses(['DUMMY', 'Z8673'], [None, 'N'])
        assert flags_poa_no.get('CBVD') is False, \
            "CBVD_SQLA with POA=N should produce combined CBVD=False"

    def test_cbvd_combined_derivation_poa_present(self):
        """
        SAS: CMR_CBVD = 1 if CMR_CBVD_POA=1.
        CBVD_POA code with POA=Y should set combined CBVD=True.
        """
        mapper = _build_mock_mapper()
        flags = mapper.map_patient_diagnoses(['DUMMY', 'I639'], [None, 'Y'])
        assert flags.get('CBVD') is True, \
            "CBVD_POA code with POA=Y should produce combined CBVD=True"

    def test_cbvd_combined_derivation_npoa(self):
        """
        SAS: CBVD_NPOA (code present, POA=N/U) alone should NOT produce CMR_CBVD=1.
        Only POA-present CBVD or sequela creates the combined flag.
        """
        mapper = _build_mock_mapper()
        # I639 with POA=N → CBVD_NPOA hit only → CBVD combined = False
        flags = mapper.map_patient_diagnoses(['DUMMY', 'I639'], [None, 'N'])
        assert flags.get('CBVD') is False, \
            "CBVD code with POA=N (CBVD_NPOA) should NOT produce combined CBVD=True"


# ===========================================================================
# Suite D — Principal diagnosis exclusion
# ===========================================================================

class TestPrincipalDiagnosisExclusion:

    def test_principal_dx_not_mapped(self):
        """
        The first element of diagnosis_codes is the principal diagnosis
        and must be excluded from comorbidity mapping (matches SAS DO I=2).
        """
        mapper = _build_mock_mapper()

        # Only one code — and it's the principal — so nothing should be flagged
        flags_principal_only = mapper.map_patient_diagnoses(['I509'], ['Y'])
        assert flags_principal_only.get('HF') is False, \
            "Principal diagnosis alone (index 0) must NOT be mapped to comorbidities"

    def test_secondary_dx_is_mapped(self):
        """
        The second element onward IS mapped.
        """
        mapper = _build_mock_mapper()
        flags = mapper.map_patient_diagnoses(['DUMMY', 'I509'], [None, 'Y'])
        assert flags.get('HF') is True, \
            "Secondary diagnosis (index 1) must be mapped"

    def test_principal_excluded_secondary_included(self):
        """
        If the same code appears as both principal and secondary, only the
        secondary occurrence should trigger the flag.
        """
        mapper = _build_mock_mapper()
        # I509 as principal: should NOT flag HF
        flags_principal = mapper.map_patient_diagnoses(['I509'], ['Y'])
        assert not flags_principal.get('HF'), "Principal I509 must not flag HF"

        # I509 as secondary: should flag HF (with POA=Y)
        flags_secondary = mapper.map_patient_diagnoses(['OTHER', 'I509'], [None, 'Y'])
        assert flags_secondary.get('HF'), "Secondary I509 (POA=Y) must flag HF"


# ===========================================================================
# Suite E — Loader footer filtering  (requires Excel file)
# ===========================================================================

@pytest.mark.requires_excel
class TestLoaderFooterFiltering:
    """
    These tests require the bundled CMR-Reference-File-v2026-1.xlsx to be
    present in elixhauser_ahrq/data/.
    """

    def test_dx_mapping_row_count(self):
        """DX_to_Comorb_Mapping must contain exactly 4567 codes (not 4568)."""
        loader = ElixhauserLoader()
        n = len(loader.dx_mapping)
        assert n == 4567, (
            f"Expected 4567 ICD-10 codes; got {n}. "
            f"Check that 'End of Content' footer row is filtered."
        )

    def test_comorbidity_measure_count(self):
        """Comorbidity_Measures sheet must contain exactly 38 measures (not 39)."""
        loader = ElixhauserLoader()
        n = len(loader.comorbidity_measures)
        assert n == 38, (
            f"Expected 38 comorbidity measures; got {n}. "
            f"Check that 'End of Content' footer row is filtered."
        )

    def test_no_end_of_content_in_icd_codes(self):
        """'End of Content' must not appear as an ICD-10 code in the lookup."""
        loader = ElixhauserLoader()
        icd_col = 'ICD-10-CM Diagnosis'
        bad_rows = loader.dx_mapping[
            loader.dx_mapping[icd_col].astype(str).str.lower().str.contains('end of content', na=False)
        ]
        assert len(bad_rows) == 0, (
            "'End of Content' footer row leaked into dx_mapping"
        )

    def test_summary_stats_correct(self):
        """get_summary_stats() must return the correct v2026-1 row counts."""
        loader = ElixhauserLoader()
        stats = loader.get_summary_stats()
        assert stats['num_comorbidity_measures'] == 38
        assert stats['num_icd10_codes'] == 4567


# ===========================================================================
# Entry point for direct execution
# ===========================================================================

if __name__ == "__main__":
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        capture_output=False
    )
    sys.exit(result.returncode)
