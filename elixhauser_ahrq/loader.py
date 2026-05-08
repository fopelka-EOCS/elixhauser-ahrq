"""
loader.py - Load AHRQ Elixhauser reference data from Excel files

This module reads the official AHRQ Elixhauser Comorbidity Software Refined
for ICD-10-CM reference files and provides them as pandas DataFrames.

CORRECTED v2026-1: Filters out the "End of Content" footer row that AHRQ
appends to the DX_to_Comorb_Mapping and Comorbidity_Measures sheets.
Without this filter the row counts report 4568 codes / 39 measures instead
of the correct 4567 codes / 38 measures, and the footer row can propagate
garbage into downstream lookups.
"""

import pandas as pd
from pathlib import Path
from typing import Tuple


# Footer sentinel appended by AHRQ to both sheets
_AHRQ_FOOTER = 'End of Content'


class ElixhauserLoader:
    """Load and provide access to AHRQ Elixhauser reference data."""

    def __init__(self, reference_file_path: str = None):
        """
        Initialize the loader with a reference file.

        Args:
            reference_file_path: Path to the AHRQ CMR-Reference-File Excel file.
                                 If None, uses the bundled v2026.1 file.
        """
        if reference_file_path is None:
            data_dir = Path(__file__).parent / "data"
            reference_file_path = data_dir / "CMR-Reference-File-v2026-1.xlsx"

        self.reference_file = Path(reference_file_path)
        if not self.reference_file.exists():
            raise FileNotFoundError(
                f"AHRQ reference file not found: {self.reference_file}"
            )

        self._comorbidity_measures = None
        self._dx_mapping = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _drop_footer(df: pd.DataFrame) -> pd.DataFrame:
        """
        Remove the AHRQ 'End of Content' sentinel row(s).

        The footer appears in the first column of both sheets.  Any row where
        the first column value equals _AHRQ_FOOTER (case-insensitive, stripped)
        is dropped.
        """
        first_col = df.columns[0]
        mask = df[first_col].astype(str).str.strip().str.lower() == _AHRQ_FOOTER.lower()
        return df[~mask].reset_index(drop=True)

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def comorbidity_measures(self) -> pd.DataFrame:
        """
        Get the list of 38 comorbidity measures.

        Returns:
            DataFrame with columns:
                - Abbreviation: Short name (e.g., 'CMR_AIDS')
                - Comorbidity Description: Full description
                - Uses present on admission (POA) indicators: Yes/No
        """
        if self._comorbidity_measures is None:
            raw = pd.read_excel(
                self.reference_file,
                sheet_name='Comorbidity_Measures',
                skiprows=1
            )
            self._comorbidity_measures = self._drop_footer(raw)
        return self._comorbidity_measures

    @property
    def dx_mapping(self) -> pd.DataFrame:
        """
        Get the ICD-10-CM to comorbidity mapping.

        Returns:
            DataFrame with columns:
                - ICD-10-CM Diagnosis: The diagnosis code (no decimal)
                - ICD-10-CM Code Description: Description of the code
                - # Comorbidities: Number of categories this code maps to
                - [38 comorbidity columns]: Binary flags
        """
        if self._dx_mapping is None:
            raw = pd.read_excel(
                self.reference_file,
                sheet_name='DX_to_Comorb_Mapping',
                skiprows=1
            )
            self._dx_mapping = self._drop_footer(raw)
        return self._dx_mapping

    # ------------------------------------------------------------------
    # Convenience accessors (unchanged from original)
    # ------------------------------------------------------------------

    def get_comorbidity_categories(self) -> list:
        """
        Get list of all comorbidity category abbreviations (strips 'CMR_' prefix).
        """
        measures = self.comorbidity_measures
        categories = measures['Abbreviation \n(SAS Data Element Name)'].str.replace('CMR_', '', regex=False)
        return categories.tolist()

    def get_poa_required_categories(self) -> list:
        """
        Get categories that require POA indicators for assignment.
        """
        measures = self.comorbidity_measures
        poa_col = 'Uses present on admission (POA) indicators for assignment?'
        poa_required = measures[measures[poa_col] == 'Yes']
        categories = poa_required['Abbreviation \n(SAS Data Element Name)'].str.replace('CMR_', '', regex=False)
        return categories.tolist()

    def get_codes_for_category(self, category: str) -> pd.DataFrame:
        """
        Get all ICD-10-CM codes that map to a specific comorbidity category.
        """
        mapping = self.dx_mapping

        if not category.startswith('CMR_'):
            category = category.upper()
        else:
            category = category.replace('CMR_', '')

        category_cols = [col for col in mapping.columns if col.startswith(category)]

        if not category_cols:
            raise ValueError(f"Category '{category}' not found in mapping")

        mask = mapping[category_cols].sum(axis=1) > 0
        return mapping[mask][['ICD-10-CM Diagnosis', 'ICD-10-CM Code Description', '# Comorbidities']]

    def get_summary_stats(self) -> dict:
        """
        Get summary statistics about the reference data.

        Correct v2026-1 counts: 38 measures, 4567 ICD-10-CM codes.
        """
        measures = self.comorbidity_measures
        mapping  = self.dx_mapping

        return {
            'num_comorbidity_measures': len(measures),
            'num_icd10_codes': len(mapping),
            'num_poa_required_measures': len(self.get_poa_required_categories()),
            'codes_with_multiple_categories': int((mapping['# Comorbidities'] > 1).sum()),
            'reference_file': str(self.reference_file.name)
        }


def load_ahrq_data(reference_file_path: str = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Convenience function to load AHRQ reference data.

    Returns:
        Tuple of (comorbidity_measures_df, dx_mapping_df)
    """
    loader = ElixhauserLoader(reference_file_path)
    return loader.comorbidity_measures, loader.dx_mapping


if __name__ == "__main__":
    loader = ElixhauserLoader()

    print("=== AHRQ Elixhauser Reference Data Summary (v2026-1 corrected) ===")
    stats = loader.get_summary_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")
    # Expected: num_comorbidity_measures=38, num_icd10_codes=4567

    print("\n=== First 5 Comorbidity Measures ===")
    print(loader.comorbidity_measures.head())

    print("\n=== Categories Requiring POA Indicators ===")
    print(loader.get_poa_required_categories())
