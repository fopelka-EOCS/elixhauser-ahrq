"""
scorer.py - Calculate risk scores from Elixhauser comorbidity flags

This module converts binary comorbidity flags into numerical risk scores
and assigns patients to risk strata (Low/Moderate/High).

CORRECTED v2026-1: Weights sourced directly from CMR_Index_Program_v2026-1.sas
(mwXXX = mortality weights, rwXXX = readmission weights).
Key structural note: the index operates on CMR_CBVD (a single combined
cerebrovascular flag derived by the mapper), NOT on separate CBVD_POA /
CBVD_SQLA flags.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from enum import Enum


class RiskStratum(Enum):
    """Patient risk stratification levels."""
    LOW = "Low"
    MODERATE = "Moderate"
    HIGH = "High"


class ElixhauserScorer:
    """Calculate risk scores and stratify patients by risk level."""

    # ---------------------------------------------------------------
    # AHRQ Mortality Index Weights (v2026-1)
    # Source: CMR_Index_Program_v2026-1.sas  mwXXX variables
    # ---------------------------------------------------------------
    MORTALITY_WEIGHTS = {
        'AIDS':          -4,
        'ALCOHOL':       -1,
        'ANEMDEF':       -3,
        'AUTOIMMUNE':     0,
        'BLDLOSS':       -4,
        'CANCER_LEUK':    9,
        'CANCER_LYMPH':   5,
        'CANCER_METS':   22,
        'CANCER_NSITU':   0,
        'CANCER_SOLID':  10,
        'CBVD':           5,   # combined CMR_CBVD — see mapper._derive_cbvd()
        'COAG':          14,
        'DEMENTIA':       5,
        'DEPRESS':       -8,
        'DIAB_CX':       -2,
        'DIAB_UNCX':      0,
        'DRUG_ABUSE':    -7,
        'HF':            14,
        'HTN_CX':         1,
        'HTN_UNCX':       0,
        'LIVER_MLD':      2,
        'LIVER_SEV':     16,
        'LUNG_CHRONIC':   2,
        'NEURO_MOVT':    -1,
        'NEURO_OTH':     22,
        'NEURO_SEIZ':     2,
        'OBESE':         -7,
        'PARALYSIS':      4,
        'PERIVASC':       3,
        'PSYCHOSES':     -9,
        'PULMCIRC':       4,
        'RENLFL_MOD':     3,
        'RENLFL_SEV':     7,
        'THYROID_HYPO':  -3,
        'THYROID_OTH':   -8,
        'ULCER_PEPTIC':   0,
        'VALVE':          0,
        'WGHTLOSS':      13,
    }

    # ---------------------------------------------------------------
    # AHRQ Readmission Index Weights (v2026-1)
    # Source: CMR_Index_Program_v2026-1.sas  rwXXX variables
    # ---------------------------------------------------------------
    READMISSION_WEIGHTS = {
        'AIDS':           5,
        'ALCOHOL':        3,
        'ANEMDEF':        5,
        'AUTOIMMUNE':     2,
        'BLDLOSS':        2,
        'CANCER_LEUK':   10,
        'CANCER_LYMPH':   7,
        'CANCER_METS':   11,
        'CANCER_NSITU':   0,
        'CANCER_SOLID':   7,
        'CBVD':           0,   # combined CMR_CBVD
        'COAG':           3,
        'DEMENTIA':       1,
        'DEPRESS':        2,
        'DIAB_CX':        4,
        'DIAB_UNCX':      0,
        'DRUG_ABUSE':     6,
        'HF':             7,
        'HTN_CX':         0,
        'HTN_UNCX':       0,
        'LIVER_MLD':      3,
        'LIVER_SEV':     10,
        'LUNG_CHRONIC':   4,
        'NEURO_MOVT':     1,
        'NEURO_OTH':      2,
        'NEURO_SEIZ':     5,
        'OBESE':         -2,
        'PARALYSIS':      3,
        'PERIVASC':       1,
        'PSYCHOSES':      6,
        'PULMCIRC':       3,
        'RENLFL_MOD':     4,
        'RENLFL_SEV':     8,
        'THYROID_HYPO':   0,
        'THYROID_OTH':    0,
        'ULCER_PEPTIC':   2,
        'VALVE':          0,
        'WGHTLOSS':       6,
    }

    def __init__(self, index_type: str = "mortality"):
        """
        Initialize scorer with specified index type.

        Args:
            index_type: Either "mortality" or "readmission"
        """
        if index_type not in ["mortality", "readmission"]:
            raise ValueError("index_type must be 'mortality' or 'readmission'")

        self.index_type = index_type
        self.weights = (
            self.MORTALITY_WEIGHTS if index_type == "mortality"
            else self.READMISSION_WEIGHTS
        )

    def calculate_score(self, comorbidity_flags: Dict[str, bool]) -> float:
        """
        Calculate Elixhauser index score from comorbidity flags.

        Args:
            comorbidity_flags: Dictionary mapping category names to boolean flags.
                               Must include 'CBVD' (the combined cerebrovascular flag
                               produced by ElixhauserMapper, not the raw _POA/_SQLA flags).

        Returns:
            Numerical risk score (sum of weights for flagged categories)
        """
        score = 0
        for category, is_present in comorbidity_flags.items():
            if is_present and category in self.weights:
                score += self.weights[category]
        return score

    def calculate_comorbidity_count(self, comorbidity_flags: Dict[str, bool]) -> int:
        """
        Calculate simple count of comorbidities present.

        Args:
            comorbidity_flags: Dictionary mapping category names to boolean flags

        Returns:
            Count of comorbidities (0-38)
        """
        return sum(1 for flag in comorbidity_flags.values() if flag)

    def stratify_risk(
        self,
        score: float,
        thresholds: Tuple[float, float] = None,
        procedure_type: str = None
    ) -> RiskStratum:
        """
        Assign patient to risk stratum based on score.

        Args:
            score: Elixhauser index score
            thresholds: Optional (low_cutoff, high_cutoff) tuple.
                        Thresholds must be calibrated per procedure/population.
            procedure_type: Reserved for procedure-specific thresholds (future use)

        Returns:
            RiskStratum (LOW, MODERATE, or HIGH)
        """
        if thresholds is None:
            if self.index_type == "mortality":
                thresholds = (5, 15)
            else:
                thresholds = (10, 20)

        low_cutoff, high_cutoff = thresholds

        if score < low_cutoff:
            return RiskStratum.LOW
        elif score < high_cutoff:
            return RiskStratum.MODERATE
        else:
            return RiskStratum.HIGH

    def score_dataframe(
        self,
        df: pd.DataFrame,
        flag_columns: List[str] = None
    ) -> pd.DataFrame:
        """
        Add risk scores to a DataFrame of comorbidity flags.

        Args:
            df: DataFrame with comorbidity flag columns (output of ElixhauserMapper).
                Must contain a 'CBVD' column (combined flag), not CBVD_POA / CBVD_SQLA.
            flag_columns: Optional list of flag column names. If None, uses all
                          columns that match scorer weight keys.

        Returns:
            DataFrame with added columns:
                - elixhauser_score: Numerical risk score
                - comorbidity_count: Count of comorbidities
                - risk_stratum: Low/Moderate/High
        """
        result = df.copy()

        if flag_columns is None:
            flag_columns = [col for col in df.columns if col in self.weights]

        scores = []
        counts = []
        strata = []

        for _, row in df.iterrows():
            flags = {col: bool(row[col]) for col in flag_columns if col in row}
            score = self.calculate_score(flags)
            count = self.calculate_comorbidity_count(flags)
            stratum = self.stratify_risk(score)
            scores.append(score)
            counts.append(count)
            strata.append(stratum.value)

        result['elixhauser_score'] = scores
        result['comorbidity_count'] = counts
        result['risk_stratum'] = strata

        return result

    def get_score_distribution_summary(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Get summary statistics of risk scores by stratum.

        Args:
            df: DataFrame with 'elixhauser_score' and 'risk_stratum' columns

        Returns:
            DataFrame with summary statistics by risk stratum
        """
        summary = df.groupby('risk_stratum')['elixhauser_score'].agg(
            count='count',
            mean_score='mean',
            median_score='median',
            min_score='min',
            max_score='max',
            std_score='std'
        ).reset_index()
        summary['percentage'] = 100 * summary['count'] / summary['count'].sum()
        return summary


if __name__ == "__main__":
    print("=== Elixhauser Scorer Demo (v2026-1 corrected weights) ===\n")

    scorer = ElixhauserScorer(index_type="mortality")

    # Note: CBVD is the combined flag, not CBVD_POA or CBVD_SQLA
    patient_flags = {
        'DIAB_CX': True,
        'HF': True,
        'RENLFL_MOD': True,
        'HTN_CX': False,
        'CANCER_METS': False,
        'CBVD': False,
    }

    score = scorer.calculate_score(patient_flags)
    count = scorer.calculate_comorbidity_count(patient_flags)
    stratum = scorer.stratify_risk(score)

    print("Example Patient:")
    print(f"Comorbidities: {[k for k, v in patient_flags.items() if v]}")
    print(f"Score: {score}")
    print(f"Count: {count}")
    print(f"Risk Stratum: {stratum.value}")

    print("\nComparison: Mortality vs Readmission Indices")
    print(f"{'Category':<20} {'Mortality Weight':>20} {'Readmission Weight':>20}")
    print("-" * 65)

    categories = ['HF', 'CANCER_METS', 'RENLFL_SEV', 'ALCOHOL', 'DEPRESS', 'AIDS', 'WGHTLOSS']
    for cat in categories:
        mort_wt = ElixhauserScorer.MORTALITY_WEIGHTS.get(cat, 0)
        readm_wt = ElixhauserScorer.READMISSION_WEIGHTS.get(cat, 0)
        print(f"{cat:<20} {mort_wt:>20} {readm_wt:>20}")
