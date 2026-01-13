"""
elixhauser_ahrq - Python package for AHRQ Elixhauser Comorbidity Index

This package provides tools to:
1. Load AHRQ Elixhauser reference data
2. Map ICD-10-CM diagnosis codes to comorbidity categories
3. Calculate risk scores and stratify patients

Based on: AHRQ Elixhauser Comorbidity Software Refined for ICD-10-CM v2026.1
"""

__version__ = "0.1.0"
__author__ = "Frank Opelka, MD - Episodes of Care Solutions (EOCS)"

from .loader import ElixhauserLoader, load_ahrq_data
from .mapper import ElixhauserMapper
from .scorer import ElixhauserScorer, RiskStratum

__all__ = [
    'ElixhauserLoader',
    'load_ahrq_data',
    'ElixhauserMapper',
    'ElixhauserScorer',
    'RiskStratum',
]
