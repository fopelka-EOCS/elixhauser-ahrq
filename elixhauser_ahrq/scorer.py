"""
scorer.py - Calculate risk scores from Elixhauser comorbidity flags

This module converts binary comorbidity flags into numerical risk scores
and assigns patients to risk strata (Low/Moderate/High).
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
    
    # AHRQ Mortality Index Weights (v2026.1)
    # These are the published weights for predicting in-hospital mortality
    MORTALITY_WEIGHTS = {
        'AIDS': 11,
        'ALCOHOL': -1,
        'ANEMDEF': 3,
        'AUTOIMMUNE': 0,
        'BLDLOSS': 2,
        'CANCER_LEUK': 7,
        'CANCER_LYMPH': 7,
        'CANCER_METS': 14,
        'CANCER_NSITU': 0,
        'CANCER_SOLID': 7,
        'CBVD_POA': 0,
        'CBVD_SQLA': 5,
        'COAG': 11,
        'DEMENTIA': 6,
        'DEPRESS': -5,
        'DIAB_CX': 0,
        'DIAB_UNCX': 0,
        'DRUG_ABUSE': -7,
        'HF': 9,
        'HTN_CX': -3,
        'HTN_UNCX': -1,
        'LIVER_MLD': 2,
        'LIVER_SEV': 8,
        'LUNG_CHRONIC': 4,
        'NEURO_MOVT': 5,
        'NEURO_OTH': 7,
        'NEURO_SEIZ': 2,
        'OBESE': -3,
        'PARALYSIS': 5,
        'PERIVASC': 4,
        'PSYCHOSES': -5,
        'PULMCIRC': 6,
        'RENLFL_MOD': 3,
        'RENLFL_SEV': 8,
        'THYROID_HYPO': -1,
        'THYROID_OTH': 0,
        'ULCER_PEPTIC': 0,
        'VALVE': 0,
        'WGHTLOSS': 9
    }
    
    # AHRQ Readmission Index Weights (v2026.1)
    # These predict 30-day all-cause readmission
    READMISSION_WEIGHTS = {
        'AIDS': 6,
        'ALCOHOL': 7,
        'ANEMDEF': 5,
        'AUTOIMMUNE': 1,
        'BLDLOSS': 0,
        'CANCER_LEUK': -2,
        'CANCER_LYMPH': 6,
        'CANCER_METS': 7,
        'CANCER_NSITU': -2,
        'CANCER_SOLID': 7,
        'CBVD_POA': 0,
        'CBVD_SQLA': 3,
        'COAG': 11,
        'DEMENTIA': 5,
        'DEPRESS': 5,
        'DIAB_CX': 4,
        'DIAB_UNCX': 0,
        'DRUG_ABUSE': 7,
        'HF': 13,
        'HTN_CX': 3,
        'HTN_UNCX': -2,
        'LIVER_MLD': 3,
        'LIVER_SEV': 10,
        'LUNG_CHRONIC': 6,
        'NEURO_MOVT': 4,
        'NEURO_OTH': 9,
        'NEURO_SEIZ': 3,
        'OBESE': 2,
        'PARALYSIS': 4,
        'PERIVASC': 4,
        'PSYCHOSES': 8,
        'PULMCIRC': 5,
        'RENLFL_MOD': 7,
        'RENLFL_SEV': 11,
        'THYROID_HYPO': 1,
        'THYROID_OTH': 3,
        'ULCER_PEPTIC': 0,
        'VALVE': 0,
        'WGHTLOSS': 8
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
            comorbidity_flags: Dictionary mapping category names to boolean flags
        
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
            thresholds: Optional (low_high_cutoff, moderate_high_cutoff) tuple
            procedure_type: Optional procedure type for procedure-specific thresholds
        
        Returns:
            RiskStratum (LOW, MODERATE, or HIGH)
        """
        if thresholds is None:
            # Default thresholds for mortality index
            # These are illustrative - should be calibrated per procedure
            if self.index_type == "mortality":
                thresholds = (5, 15)  # Low: <5, Moderate: 5-14, High: >=15
            else:
                thresholds = (10, 20)  # For readmission index
        
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
            df: DataFrame with comorbidity flag columns
            flag_columns: Optional list of flag column names. If None, uses all boolean columns.
        
        Returns:
            DataFrame with added columns:
                - elixhauser_score: Numerical risk score
                - comorbidity_count: Count of comorbidities
                - risk_stratum: Low/Moderate/High
        """
        result = df.copy()
        
        if flag_columns is None:
            # Find boolean columns that match Elixhauser categories
            flag_columns = [col for col in df.columns if col in self.weights]
        
        # Calculate scores
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
        summary = df.groupby('risk_stratum')['elixhauser_score'].agg([
            ('count', 'count'),
            ('mean_score', 'mean'),
            ('median_score', 'median'),
            ('min_score', 'min'),
            ('max_score', 'max'),
            ('std_score', 'std')
        ]).reset_index()
        
        # Add percentage
        summary['percentage'] = 100 * summary['count'] / summary['count'].sum()
        
        return summary


if __name__ == "__main__":
    # Demo usage
    print("=== Elixhauser Scorer Demo ===\n")
    
    # Example 1: Calculate score for a patient
    scorer = ElixhauserScorer(index_type="mortality")
    
    patient_flags = {
        'DIAB_CX': True,
        'HF': True,
        'RENLFL_MOD': True,
        'HTN_CX': False,
        'CANCER_METS': False
    }
    
    score = scorer.calculate_score(patient_flags)
    count = scorer.calculate_comorbidity_count(patient_flags)
    stratum = scorer.stratify_risk(score)
    
    print("Example Patient:")
    print(f"Comorbidities: {[k for k, v in patient_flags.items() if v]}")
    print(f"Score: {score}")
    print(f"Count: {count}")
    print(f"Risk Stratum: {stratum.value}")
    
    # Example 2: Compare mortality vs readmission indices
    print("\n\nComparison: Mortality vs Readmission Indices")
    print(f"{'Category':<20} {'Mortality Weight':>20} {'Readmission Weight':>20}")
    print("-" * 65)
    
    categories = ['HF', 'CANCER_METS', 'RENLFL_SEV', 'ALCOHOL', 'DEPRESS']
    for cat in categories:
        mort_wt = ElixhauserScorer.MORTALITY_WEIGHTS.get(cat, 0)
        readm_wt = ElixhauserScorer.READMISSION_WEIGHTS.get(cat, 0)
        print(f"{cat:<20} {mort_wt:>20} {readm_wt:>20}")
