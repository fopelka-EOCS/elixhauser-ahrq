"""
mapper.py - Map patient ICD-10-CM diagnosis codes to Elixhauser comorbidity categories

This module takes patient diagnosis data and assigns binary flags for each of the
38 Elixhauser comorbidity categories.

CORRECTED v2026-1 fixes:
  1. POA: accepts Y, W, and 1 as present-on-admission (SAS uses Y and W).
  2. POA category sets are hardcoded from the SAS COMANYPOA / COMPOA arrays,
     not inferred from column name suffixes.
  3. CBVD logic: tracks CBVD_POA, CBVD_SQLA, and CBVD_NPOA separately, then
     derives the combined CMR_CBVD flag per SAS derivation logic.
  4. Principal diagnosis exclusion: diagnosis_codes[0] is treated as the
     principal diagnosis and excluded from comorbidity mapping, matching
     the SAS DO I = 2 TO ... loop.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from .loader import ElixhauserLoader


# ---------------------------------------------------------------------------
# POA category sets — sourced from CMR_Mapping_Program_v2026-1.sas arrays
# ---------------------------------------------------------------------------

# COMANYPOA (20 categories): assigned regardless of POA status
_POA_NEUTRAL = frozenset({
    'AIDS', 'ALCOHOL', 'AUTOIMMUNE', 'LUNG_CHRONIC', 'DEMENTIA', 'DEPRESS',
    'DIAB_UNCX', 'DIAB_CX', 'DRUG_ABUSE', 'HTN_UNCX', 'HTN_CX',
    'THYROID_HYPO', 'THYROID_OTH', 'CANCER_LYMPH', 'CANCER_LEUK',
    'CANCER_METS', 'OBESE', 'PERIVASC', 'CANCER_SOLID', 'CANCER_NSITU',
})

# COMPOA (19 categories): assigned only when POA = Y, W, or exempt
_POA_REQUIRED = frozenset({
    'ANEMDEF', 'BLDLOSS', 'HF', 'COAG', 'LIVER_MLD', 'LIVER_SEV',
    'NEURO_MOVT', 'NEURO_SEIZ', 'NEURO_OTH', 'PARALYSIS', 'PSYCHOSES',
    'PULMCIRC', 'RENLFL_MOD', 'RENLFL_SEV', 'ULCER_PEPTIC', 'WGHTLOSS',
    'CBVD_POA', 'CBVD_SQLA', 'VALVE',
})

# CBVD_NPOA: assigned only when POA = N or U
_CBVD_NPOA_CATEGORY = 'CBVD_POA'   # the source code value that maps to CBVD_NPOA


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

        metadata_cols = ['ICD-10-CM Diagnosis', 'ICD-10-CM Code Description', '# Comorbidities']
        self.comorbidity_cols = [col for col in mapping.columns if col not in metadata_cols]

        self.lookup = {}
        for _, row in mapping.iterrows():
            icd_code = row['ICD-10-CM Diagnosis']
            flags = {col: bool(row[col]) for col in self.comorbidity_cols}
            self.lookup[icd_code] = flags

    # ------------------------------------------------------------------
    # Single-code mapping
    # ------------------------------------------------------------------

    def map_single_code(
        self,
        icd10_code: str,
        poa_indicator: str = None
    ) -> Dict[str, bool]:
        """
        Map a single ICD-10-CM code to raw comorbidity category flags.

        This method returns the low-level _POA / _SQLA / _NPOA flags as
        produced by the reference file.  Callers should use
        map_patient_diagnoses() which aggregates these correctly.

        Args:
            icd10_code: ICD-10-CM diagnosis code (with or without decimal)
            poa_indicator: Present on Admission indicator (Y/W/N/U/1)
                Y, W, 1  => present on admission
                N, U     => NOT present on admission

        Returns:
            Dictionary mapping raw category names to boolean flags
        """
        code_clean = icd10_code.replace('.', '').upper().strip()

        if code_clean not in self.lookup:
            return {col: False for col in self.comorbidity_cols}

        flags = self.lookup[code_clean].copy()

        if poa_indicator is not None:
            poa_str = str(poa_indicator).upper().strip()
            # SAS: POA=Yes means Y or W (also accept 1 for numeric encoding)
            poa_yes = poa_str in ('Y', 'W', '1')
            poa_no  = poa_str in ('N', 'U')

            for col in self.comorbidity_cols:
                cat = col  # category name as stored in the mapping

                if cat in _POA_REQUIRED:
                    # These categories require POA = Yes (Y or W)
                    if not poa_yes:
                        flags[col] = False

        return flags

    # ------------------------------------------------------------------
    # Patient-level aggregation
    # ------------------------------------------------------------------

    def map_patient_diagnoses(
        self,
        diagnosis_codes: List[str],
        poa_indicators: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """
        Map all diagnosis codes for a patient to comorbidity flags.

        IMPORTANT: diagnosis_codes[0] is treated as the PRINCIPAL diagnosis
        and is excluded from comorbidity mapping, matching the SAS program
        which iterates from DX(2) onward.  If your list already excludes the
        principal diagnosis, pass skip_principal=False.

        Args:
            diagnosis_codes: Full list of ICD-10-CM codes, principal dx first
            poa_indicators:  Parallel list of POA indicators (same length)

        Returns:
            Dictionary of 38 comorbidity flags plus 'CBVD' combined flag
        """
        if poa_indicators is None:
            poa_indicators = [None] * len(diagnosis_codes)

        if len(diagnosis_codes) != len(poa_indicators):
            raise ValueError("diagnosis_codes and poa_indicators must have same length")

        # Initialize tracking flags
        patient_flags  = {col: False for col in self.comorbidity_cols}
        cbvd_poa_hit   = False   # CBVD code present AND POA = Y/W
        cbvd_sqla_hit  = False   # CBVD sequela code AND POA = Y/W
        cbvd_npoa_hit  = False   # CBVD code present AND POA = N/U

        # --- Skip diagnosis_codes[0] (principal diagnosis) ---
        secondary_pairs = list(zip(diagnosis_codes, poa_indicators))[1:]

        for dx, poa in secondary_pairs:
            if not dx or str(dx).strip() == '':
                continue

            code_flags = self.map_single_code(dx, poa)

            poa_str = str(poa).upper().strip() if poa is not None else ''
            poa_yes = poa_str in ('Y', 'W', '1')
            poa_no  = poa_str in ('N', 'U')

            for col, flag in code_flags.items():
                if not flag:
                    continue

                cat = col

                if cat in _POA_NEUTRAL:
                    patient_flags[col] = True

                elif cat in _POA_REQUIRED:
                    if cat == 'CBVD_POA' and poa_yes:
                        cbvd_poa_hit = True
                        patient_flags[col] = True
                    elif cat == 'CBVD_SQLA' and poa_yes:
                        cbvd_sqla_hit = True
                        patient_flags[col] = True
                    elif cat not in ('CBVD_POA', 'CBVD_SQLA'):
                        if poa_yes:
                            patient_flags[col] = True

                # CBVD_NPOA: code mapped to CBVD_POA category but POA = N/U
                if col == 'CBVD_POA' and flag and poa_no:
                    cbvd_npoa_hit = True

        # --- Derive combined CMR_CBVD per SAS logic ---
        # CMR_CBVD = 1 if CMR_CBVD_POA=1
        #            OR (CMR_CBVD_POA=0 AND CMR_CBVD_NPOA=0 AND CMR_CBVD_SQLA=1)
        cbvd_combined = cbvd_poa_hit or (
            not cbvd_poa_hit and not cbvd_npoa_hit and cbvd_sqla_hit
        )
        patient_flags['CBVD'] = cbvd_combined

        # Remove the raw intermediate CBVD flags from output
        for raw in ('CBVD_POA', 'CBVD_SQLA'):
            patient_flags.pop(raw, None)

        # Apply hierarchy rules
        patient_flags = self._apply_hierarchy_rules(patient_flags)

        return patient_flags

    # ------------------------------------------------------------------
    # Hierarchy rules (unchanged from original, confirmed correct)
    # ------------------------------------------------------------------

    def _apply_hierarchy_rules(self, flags: Dict[str, bool]) -> Dict[str, bool]:
        """
        Apply hierarchical exclusion rules per AHRQ methodology.
        """
        if flags.get('DIAB_CX', False):
            flags['DIAB_UNCX'] = False

        if flags.get('HTN_CX', False):
            flags['HTN_UNCX'] = False

        if flags.get('RENLFL_SEV', False):
            flags['RENLFL_MOD'] = False

        if flags.get('LIVER_SEV', False):
            flags['LIVER_MLD'] = False

        if flags.get('CANCER_METS', False):
            flags['CANCER_SOLID'] = False
            flags['CANCER_LEUK']  = False
            flags['CANCER_LYMPH'] = False

        if flags.get('CANCER_SOLID', False):
            flags['CANCER_NSITU'] = False

        return flags

    # ------------------------------------------------------------------
    # DataFrame-level mapping
    # ------------------------------------------------------------------

    def map_dataframe(
        self,
        df: pd.DataFrame,
        patient_id_col: str,
        diagnosis_col: str,
        poa_col: Optional[str] = None,
        dx_sequence_col: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Map a DataFrame of patient diagnoses to comorbidity flags.

        The DataFrame should be in long format (one row per diagnosis per patient).
        Rows with the lowest dx_sequence value (or first appearance) per patient
        are treated as the principal diagnosis and excluded.

        Args:
            df:               Long-format DataFrame with patient diagnoses
            patient_id_col:   Column containing patient/encounter ID
            diagnosis_col:    Column containing ICD-10-CM codes
            poa_col:          Optional column containing POA indicators
            dx_sequence_col:  Optional column with diagnosis sequence number
                              (1=principal). If None, first row per patient is principal.

        Returns:
            Wide DataFrame with one row per patient and 38 comorbidity columns
        """
        grouped = df.groupby(patient_id_col)
        results = []

        for patient_id, group in grouped:
            if dx_sequence_col and dx_sequence_col in group.columns:
                group = group.sort_values(dx_sequence_col)

            dx_codes      = group[diagnosis_col].tolist()
            poa_indicators = group[poa_col].tolist() if poa_col else None

            flags = self.map_patient_diagnoses(dx_codes, poa_indicators)

            result = {patient_id_col: patient_id}
            result.update(flags)
            results.append(result)

        return pd.DataFrame(results)

    def get_category_definitions(self) -> pd.DataFrame:
        """Get definitions of all comorbidity categories."""
        return self.loader.comorbidity_measures


if __name__ == "__main__":
    mapper = ElixhauserMapper()

    print("=== Elixhauser Mapper Demo (v2026-1 corrected) ===\n")

    # Note: first element is always the PRINCIPAL diagnosis and is excluded.
    print("Example: Patient with multiple diagnoses")
    # dx[0] = principal, dx[1..n] = secondary
    patient_dx = ["I509", "E119", "I10", "N186"]
    patient_flags = mapper.map_patient_diagnoses(patient_dx)
    print(f"Principal dx (excluded): {patient_dx[0]}")
    print(f"Secondary dx mapped:    {patient_dx[1:]}")
    print("Comorbidity flags set:")
    for cat, flag in sorted(patient_flags.items()):
        if flag:
            print(f"  {cat}")
