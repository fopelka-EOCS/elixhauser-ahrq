"""
example_usage.py - Demonstration of elixhauser_ahrq package

This script shows how to use the package to:
1. Load AHRQ reference data
2. Map patient diagnoses to comorbidity flags
3. Calculate risk scores
4. Stratify patients by risk level
"""

from elixhauser_ahrq import ElixhauserLoader, ElixhauserMapper, ElixhauserScorer, RiskStratum
import pandas as pd


def example_1_basic_usage():
    """Example 1: Basic usage with a single patient."""
    print("="*70)
    print("EXAMPLE 1: Basic Usage")
    print("="*70)
    
    # Initialize mapper and scorer
    mapper = ElixhauserMapper()
    scorer = ElixhauserScorer(index_type="mortality")
    
    # Patient diagnoses (ICD-10-CM codes)
    patient_dx = [
        "E1122",  # Type 2 diabetes with chronic kidney disease
        "I509",   # Heart failure, unspecified
        "I10",    # Essential hypertension
        "N186"    # End stage renal disease
    ]
    
    print(f"\nPatient Diagnoses: {patient_dx}")
    
    # Map to comorbidity flags
    flags = mapper.map_patient_diagnoses(patient_dx)
    
    print("\nComorbidity Flags:")
    for category, is_present in flags.items():
        if is_present:
            print(f"  ✓ {category}")
    
    # Calculate scores
    score = scorer.calculate_score(flags)
    count = scorer.calculate_comorbidity_count(flags)
    stratum = scorer.stratify_risk(score)
    
    print(f"\nRisk Assessment:")
    print(f"  Elixhauser Score: {score}")
    print(f"  Comorbidity Count: {count}")
    print(f"  Risk Stratum: {stratum.value}")


def example_2_poa_indicators():
    """Example 2: Using Present on Admission (POA) indicators."""
    print("\n\n" + "="*70)
    print("EXAMPLE 2: POA Indicators")
    print("="*70)
    
    mapper = ElixhauserMapper()
    
    # Same diagnoses, different POA status
    diagnoses = ["E119", "R634", "D649"]  # Diabetes, Weight loss, Anemia
    
    # Scenario 1: All present on admission
    print("\nScenario 1: All conditions present on admission")
    poa_all_yes = ["Y", "Y", "Y"]
    flags_1 = mapper.map_patient_diagnoses(diagnoses, poa_all_yes)
    print(f"  WGHTLOSS flagged: {flags_1.get('WGHTLOSS', False)}")
    print(f"  ANEMDEF flagged: {flags_1.get('ANEMDEF', False)}")
    
    # Scenario 2: Weight loss and anemia developed during stay
    print("\nScenario 2: Weight loss & anemia developed during hospitalization")
    poa_mixed = ["Y", "N", "N"]  # Diabetes POA, others developed during stay
    flags_2 = mapper.map_patient_diagnoses(diagnoses, poa_mixed)
    print(f"  WGHTLOSS flagged: {flags_2.get('WGHTLOSS', False)}")
    print(f"  ANEMDEF flagged: {flags_2.get('ANEMDEF', False)}")
    print("\n  (POA-required categories only count if present on admission)")


def example_3_hierarchy_rules():
    """Example 3: Hierarchy rules (complicated overrides uncomplicated)."""
    print("\n\n" + "="*70)
    print("EXAMPLE 3: Hierarchy Rules")
    print("="*70)
    
    mapper = ElixhauserMapper()
    
    # Patient has both uncomplicated and complicated diabetes codes
    dx_both = ["E119", "E1122"]  # Uncomplicated + Complicated
    flags = mapper.map_patient_diagnoses(dx_both)
    
    print("\nDiagnoses: Type 2 diabetes uncomplicated + complicated")
    print(f"  DIAB_UNCX: {flags.get('DIAB_UNCX', False)}")
    print(f"  DIAB_CX: {flags.get('DIAB_CX', False)}")
    print("\n  → Complicated diabetes suppresses uncomplicated (hierarchy rule)")


def example_4_dataframe_processing():
    """Example 4: Processing a DataFrame of multiple patients."""
    print("\n\n" + "="*70)
    print("EXAMPLE 4: DataFrame Processing")
    print("="*70)
    
    # Create sample patient data
    data = {
        'patient_id': [101, 101, 101, 102, 102, 103, 103, 103, 103],
        'diagnosis': ['E119', 'I10', 'I509', 'C349', 'N186', 'F329', 'E6601', 'I2510', 'J449']
    }
    df = pd.DataFrame(data)
    
    print("\nInput Data:")
    print(df)
    
    # Map to comorbidity flags
    mapper = ElixhauserMapper()
    comorbidity_df = mapper.map_dataframe(df, 'patient_id', 'diagnosis')
    
    # Calculate risk scores
    scorer = ElixhauserScorer(index_type="mortality")
    result_df = scorer.score_dataframe(comorbidity_df)
    
    print("\nRisk Scores by Patient:")
    print(result_df[['patient_id', 'elixhauser_score', 'comorbidity_count', 'risk_stratum']])


def example_5_mortality_vs_readmission():
    """Example 5: Compare mortality vs readmission indices."""
    print("\n\n" + "="*70)
    print("EXAMPLE 5: Mortality vs Readmission Indices")
    print("="*70)
    
    mapper = ElixhauserMapper()
    
    # Patient with depression and alcohol abuse
    patient_dx = ["F329", "F10120"]  # Depression, Alcohol abuse
    flags = mapper.map_patient_diagnoses(patient_dx)
    
    # Mortality index
    mort_scorer = ElixhauserScorer(index_type="mortality")
    mort_score = mort_scorer.calculate_score(flags)
    mort_stratum = mort_scorer.stratify_risk(mort_score)
    
    # Readmission index
    readm_scorer = ElixhauserScorer(index_type="readmission")
    readm_score = readm_scorer.calculate_score(flags)
    readm_stratum = readm_scorer.stratify_risk(readm_score)
    
    print("\nPatient: Depression + Alcohol Abuse")
    print(f"\nMortality Index:")
    print(f"  Score: {mort_score}")
    print(f"  Risk: {mort_stratum.value}")
    print(f"\nReadmission Index:")
    print(f"  Score: {readm_score}")
    print(f"  Risk: {readm_stratum.value}")
    print("\n  → Different weights for different outcomes!")


def example_6_reference_data():
    """Example 6: Exploring the reference data."""
    print("\n\n" + "="*70)
    print("EXAMPLE 6: Reference Data Exploration")
    print("="*70)
    
    loader = ElixhauserLoader()
    
    # Summary statistics
    print("\nSummary Statistics:")
    stats = loader.get_summary_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Categories requiring POA
    print("\nCategories Requiring POA Indicators:")
    poa_cats = loader.get_poa_required_categories()
    for cat in poa_cats[:5]:  # Show first 5
        print(f"  - {cat}")
    print(f"  ... and {len(poa_cats) - 5} more")
    
    # ICD-10 codes for a specific category
    print("\nSample ICD-10 Codes for Heart Failure (HF):")
    hf_codes = loader.get_codes_for_category('HF')
    print(hf_codes.head(5))


if __name__ == "__main__":
    print("\n" + "="*70)
    print("ELIXHAUSER-AHRQ PACKAGE DEMONSTRATION")
    print("="*70)
    
    example_1_basic_usage()
    example_2_poa_indicators()
    example_3_hierarchy_rules()
    example_4_dataframe_processing()
    example_5_mortality_vs_readmission()
    example_6_reference_data()
    
    print("\n\n" + "="*70)
    print("DEMONSTRATION COMPLETE")
    print("="*70)
