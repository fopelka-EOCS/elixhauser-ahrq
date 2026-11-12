"""
scorer.py - AHRQ Elixhauser Comorbidity Index (in-hospital mortality and
30-day readmission), as computed by CMR_Index_Program_v2027-1.sas.

The weights are compiled from AHRQ's SAS index program (never hand-copied).
Each index is the sum of the weights of the measures present. Measures that
could not be assessed (None, because POA indicators were unavailable) are
ignored, as SAS ``sum(of ...)`` ignores missing values; such an index is a
PARTIAL index and must be labelled as such.

These are AHRQ's indices for in-hospital mortality and 30-day all-cause
readmission. They are not the van Walraven (2009) score, and AHRQ publishes no
risk tiers. ``stratify_risk`` therefore requires explicit, user-validated
thresholds.
"""

import warnings
from enum import Enum
from typing import Dict, List, Optional, Tuple

from ._data import ahrq_data

_ALIASES = {"DRUG_ABUSE": "DRUG"}  # renamed by AHRQ in v2027.1


def _weights(kind: str) -> Dict[str, int]:
    return dict(ahrq_data()["weights"][kind])


class RiskStratum(Enum):
    """Illustrative strata; AHRQ defines none. Thresholds must be validated locally."""
    LOW = "Low"
    MODERATE = "Moderate"
    HIGH = "High"


def _canonical(name: str) -> str:
    key = str(name)
    if key.upper().startswith("CMR_"):
        key = key[4:]
    if key in _ALIASES:
        warnings.warn(f"'{key}' was renamed '{_ALIASES[key]}' by AHRQ in v2027.1; "
                      "the old name will be removed in a future release.",
                      DeprecationWarning, stacklevel=4)
        key = _ALIASES[key]
    return key


class ElixhauserScorer:
    """Compute AHRQ's Elixhauser mortality or readmission index (v2027.1 weights)."""

    MORTALITY_WEIGHTS: Dict[str, int] = _weights("mortality")
    READMISSION_WEIGHTS: Dict[str, int] = _weights("readmission")

    def __init__(self, index_type: str = "mortality"):
        if index_type not in ("mortality", "readmission"):
            raise ValueError("index_type must be 'mortality' or 'readmission'")
        self.index_type = index_type
        self.weights = dict(self.MORTALITY_WEIGHTS if index_type == "mortality"
                            else self.READMISSION_WEIGHTS)

    def calculate_score(self, comorbidity_flags: Dict[str, Optional[bool]]) -> int:
        """Sum of weights for measures flagged present (None = not assessable, ignored)."""
        score = 0
        for name, present in comorbidity_flags.items():
            key = _canonical(name)
            if key in self.weights and present is not None and bool(present):
                score += self.weights[key]
        return score

    def is_partial(self, comorbidity_flags: Dict[str, Optional[bool]]) -> bool:
        """True if any of the 38 measures is missing or not assessable."""
        seen = {_canonical(k): v for k, v in comorbidity_flags.items()}
        return any(seen.get(m) is None for m in self.weights)

    def calculate_comorbidity_count(self, comorbidity_flags: Dict[str, Optional[bool]]) -> int:
        """Number of the 38 measures flagged present."""
        return sum(1 for k, v in comorbidity_flags.items()
                   if _canonical(k) in self.weights and v is not None and bool(v))

    def stratify_risk(self, score: float, thresholds: Tuple[float, float] = None,
                      procedure_type: str = None) -> RiskStratum:
        """Assign a stratum using (low_cutoff, high_cutoff) that YOU have validated.

        AHRQ publishes no risk tiers for these indices, so no default is provided.
        """
        if thresholds is None:
            raise ValueError(
                "AHRQ publishes no risk tiers for the Elixhauser indices. Pass thresholds="
                "(low_cutoff, high_cutoff) validated for your population and outcome.")
        low_cutoff, high_cutoff = thresholds
        if score < low_cutoff:
            return RiskStratum.LOW
        if score < high_cutoff:
            return RiskStratum.MODERATE
        return RiskStratum.HIGH

    def score_dataframe(self, df, flag_columns: List[str] = None,
                        thresholds: Tuple[float, float] = None):
        """Add ``elixhauser_score``, ``comorbidity_count`` and ``index_partial`` columns
        (and ``risk_stratum`` only when validated ``thresholds`` are supplied)."""
        import pandas as pd

        if flag_columns is None:
            flag_columns = [c for c in df.columns if _canonical(c) in self.weights]
        result = df.copy()
        scores, counts, partial = [], [], []
        for _, row in df[flag_columns].iterrows():
            flags = {c: (None if pd.isna(row[c]) else bool(row[c])) for c in flag_columns}
            scores.append(self.calculate_score(flags))
            counts.append(self.calculate_comorbidity_count(flags))
            partial.append(self.is_partial(flags))
        result["elixhauser_score"] = scores
        result["comorbidity_count"] = counts
        result["index_partial"] = partial
        if thresholds is not None:
            result["risk_stratum"] = [self.stratify_risk(s, thresholds).value for s in scores]
        return result

    def get_score_distribution_summary(self, df):
        """Summary statistics of ``elixhauser_score`` (by ``risk_stratum`` if present)."""
        if "risk_stratum" in df.columns:
            g = df.groupby("risk_stratum")["elixhauser_score"]
        else:
            g = df.assign(_all="all").groupby("_all")["elixhauser_score"]
        summary = g.agg(count="count", mean_score="mean", median_score="median",
                        min_score="min", max_score="max", std_score="std").reset_index()
        summary["percentage"] = 100 * summary["count"] / summary["count"].sum()
        return summary


def score_discharge(principal_dx, secondary_dx, secondary_poa=None, **kwargs) -> dict:
    """One-call scoring of a discharge: flags, both AHRQ indices, and provenance.

    Accepts the same arguments as :func:`elixhauser_ahrq.assign_comorbidities`.
    """
    from . import __version__
    from .mapper import assign_comorbidities

    res = assign_comorbidities(principal_dx, secondary_dx, secondary_poa, **kwargs)
    mort = ElixhauserScorer("mortality")
    readm = ElixhauserScorer("readmission")
    return {
        "flags": res.flags,
        "present": res.present,
        "not_assessable": res.not_assessable,
        "mortality_index": mort.calculate_score(res.flags),
        "readmission_index": readm.calculate_score(res.flags),
        "partial": res.partial,
        "icd_version": res.icd_version,
        "poa_available": res.poa_available,
        "principal_dx": res.principal_dx,
        "trace": res.trace,
        "ahrq_version": res.cmr_version,
        "package_version": __version__,
    }
