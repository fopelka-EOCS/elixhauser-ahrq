"""
mapper.py - Map patient ICD-10-CM diagnosis codes to Elixhauser comorbidity categories

This module takes patient diagnosis data and assigns binary flags for each of the
38 Elixhauser comorbidity categories.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from .loader import ElixhauserLoader


class ElixhauserMapper:
    """Map ICD-10-CM codes to Elixhauser comorbidity flags."""
    
    def __init__(self, reference_file_path: str = None):
        """
        Initialize the mapper with AHRQ reference data.
        
        Args:
            reference_file_path: Optional path to AHRQ reference file
        """
        self.loader = ElixhauserLoader(reference_file_path)
        self._setup_lookup_table()
    
    def _setup_lookup_table(self):
        """Create efficient lookup structure for ICD-10 to category mapping."""
        mapping = self.loader.dx_mapping
        
        # Get all comorbidity columns (exclude metadata columns)
        metadata_cols = ['ICD-10-CM Diagnosis', 'ICD-10-CM Code Description', '# Comorbidities']
        self.comorbidity_cols = [col for col in mapping.columns if col not in metadata_cols]
        
        # Create lookup dictionary: ICD-10 code -> category flags
        self.lookup = {}
        for _, row in mapping.iterrows():
            icd_code = row['ICD-10-CM Diagnosis']
            flags = {col: bool(row[col]) for col in self.comorbidity_cols}
            self.lookup[icd_code] = flags
    
    def map_single_code(self, icd10_code: str, poa_indicator: str = None) -> Dict[str, bool]:
        """
        Map a single ICD-10-CM code to comorbidity flags.
        
        Args:
            icd10_code: ICD-10-CM diagnosis code (with or without decimal)
            poa_indicator: Present on Admission indicator (Y/N/U/W/1)
                         Required for 18 measures, optional otherwise
        
        Returns:
            Dictionary mapping category names to boolean flags
        """
        # Remove decimal if present
        code_clean = icd10_code.replace('.', '').upper()
        
        # Look up in reference data
        if code_clean not in self.lookup:
            # Code not in Elixhauser - return all False
            return {col: False for col in self.comorbidity_cols}
        
        flags = self.lookup[code_clean].copy()
        
        # Handle POA indicators for categories that require them
        # POA categories have _POA suffix, sequelae have _SQLA suffix
        if poa_indicator is not None:
            poa_yes = poa_indicator in ['Y', '1']
            
            # For each category with POA variant, apply logic
            for col in self.comorbidity_cols:
                if '_POA' in col:
                    # This category requires POA=Yes
                    if not poa_yes:
                        flags[col] = False
                elif '_SQLA' in col:
                    # Sequelae - requires POA=No (developed during stay)
                    if poa_yes:
                        flags[col] = False
        
        return flags
    
    def map_patient_diagnoses(
        self, 
        diagnosis_codes: List[str],
        poa_indicators: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """
        Map all diagnosis codes for a patient to comorbidity flags.
        
        Args:
            diagnosis_codes: List of ICD-10-CM diagnosis codes for the patient
            poa_indicators: Optional list of POA indicators, same length as diagnosis_codes
        
        Returns:
            Dictionary mapping category names to boolean flags (True if any diagnosis matches)
        """
        if poa_indicators is None:
            poa_indicators = [None] * len(diagnosis_codes)
        
        if len(diagnosis_codes) != len(poa_indicators):
            raise ValueError("diagnosis_codes and poa_indicators must have same length")
        
        # Initialize all flags as False
        patient_flags = {col: False for col in self.comorbidity_cols}
        
        # Map each diagnosis and OR the results
        for dx, poa in zip(diagnosis_codes, poa_indicators):
            code_flags = self.map_single_code(dx, poa)
            for col, flag in code_flags.items():
                if flag:
                    patient_flags[col] = True
        
        # Apply hierarchy rules (e.g., complicated diabetes overrides uncomplicated)
        patient_flags = self._apply_hierarchy_rules(patient_flags)
        
        return patient_flags
    
    def _apply_hierarchy_rules(self, flags: Dict[str, bool]) -> Dict[str, bool]:
        """
        Apply hierarchical exclusion rules per AHRQ methodology.
        
        When both complicated and uncomplicated versions exist, only keep complicated.
        
        Args:
            flags: Dictionary of comorbidity flags
        
        Returns:
            Updated flags with hierarchy rules applied
        """
        # Diabetes: If DIAB_CX present, suppress DIAB_UNCX
        if flags.get('DIAB_CX', False):
            flags['DIAB_UNCX'] = False
        
        # Hypertension: If HTN_CX present, suppress HTN_UNCX
        if flags.get('HTN_CX', False):
            flags['HTN_UNCX'] = False
        
        # Renal failure: If RENLFL_SEV present, suppress RENLFL_MOD
        if flags.get('RENLFL_SEV', False):
            flags['RENLFL_MOD'] = False
        
        # Liver disease: If LIVER_SEV present, suppress LIVER_MLD
        if flags.get('LIVER_SEV', False):
            flags['LIVER_MLD'] = False
        
        # Cancer: If metastatic, suppress solid/leukemia/lymphoma
        if flags.get('CANCER_METS', False):
            flags['CANCER_SOLID'] = False
            flags['CANCER_LEUK'] = False
            flags['CANCER_LYMPH'] = False
        
        return flags
    
    def map_dataframe(
        self,
        df: pd.DataFrame,
        patient_id_col: str,
        diagnosis_col: str,
        poa_col: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Map a DataFrame of patient diagnoses to comorbidity flags.
        
        Args:
            df: DataFrame with patient diagnoses
            patient_id_col: Name of column containing patient/encounter ID
            diagnosis_col: Name of column containing ICD-10-CM codes
            poa_col: Optional name of column containing POA indicators
        
        Returns:
            DataFrame with one row per patient, columns for each comorbidity category
        """
        # Group by patient
        grouped = df.groupby(patient_id_col)
        
        results = []
        for patient_id, group in grouped:
            dx_codes = group[diagnosis_col].tolist()
            poa_indicators = group[poa_col].tolist() if poa_col else None
            
            flags = self.map_patient_diagnoses(dx_codes, poa_indicators)
            
            result = {patient_id_col: patient_id}
            result.update(flags)
            results.append(result)
        
        return pd.DataFrame(results)
    
    def get_category_definitions(self) -> pd.DataFrame:
        """
        Get definitions of all comorbidity categories.
        
        Returns:
            DataFrame with category names and descriptions
        """
        return self.loader.comorbidity_measures


if __name__ == "__main__":
    # Demo usage
    mapper = ElixhauserMapper()
    
    print("=== Elixhauser Mapper Demo ===\n")
    
    # Example 1: Single code
    print("Example 1: Single diagnosis code")
    code = "E119"  # Type 2 diabetes without complications
    flags = mapper.map_single_code(code)
    print(f"ICD-10: {code}")
    print("Comorbidity flags:")
    for cat, flag in flags.items():
        if flag:
            print(f"  - {cat}: {flag}")
    
    # Example 2: Patient with multiple diagnoses
    print("\n\nExample 2: Patient with multiple diagnoses")
    patient_dx = ["E119", "I10", "I509", "N186"]  # Diabetes, HTN, CHF, CKD
    patient_flags = mapper.map_patient_diagnoses(patient_dx)
    print(f"Diagnoses: {patient_dx}")
    print("Comorbidity flags:")
    for cat, flag in patient_flags.items():
        if flag:
            print(f"  - {cat}: {flag}")
    
    # Example 3: Hierarchy rule
    print("\n\nExample 3: Hierarchy rule (complicated overrides uncomplicated)")
    both_diabetes = ["E119", "E1122"]  # Uncomplicated + Complicated
    both_flags = mapper.map_patient_diagnoses(both_diabetes)
    print(f"Diagnoses: {both_diabetes}")
    print("DIAB_UNCX:", both_flags.get('DIAB_UNCX', False))
    print("DIAB_CX:", both_flags.get('DIAB_CX', False))
    print("(Note: Complicated diabetes suppresses uncomplicated)")
