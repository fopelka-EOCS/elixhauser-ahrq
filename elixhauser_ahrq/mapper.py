"""
mapper.py - Assign AHRQ Elixhauser comorbidity measures from ICD-10-CM diagnoses.

A line-by-line reimplementation of AHRQ's CMR_Mapping_Program_v2027-1.sas
(Elixhauser Comorbidity Software Refined for ICD-10-CM, v2027.1):

* Only SECONDARY diagnoses are mapped. The principal diagnosis (SAS DX1) is
  never mapped (SAS loop ``DO I = 2 TO ...``).
* Each secondary code is looked up in AHRQ's $COMFMT format. Labels in the
  VALANYPOA array set POA-independent measures; labels in the VALPOA array,
  and the POA-dependent halves of AHRQ's combined labels, are set only when
  the code is POA-exempt for the discharge's ICD-10-CM version OR its POA
  indicator is ``Y`` or ``W``.
* POA ``N`` or ``U`` on a non-exempt code labelled CBVD_POA sets CBVD_NPOA,
  which suppresses a cerebrovascular sequela from counting as CBVD.
* POA ``1`` and blank are NOT treated as present on admission; such codes
  count only through AHRQ's POA-exempt lists (as in the SAS program).
* When POA indicators are not available at all, the 18 POA-dependent measures
  are missing (``None``), exactly as AHRQ sets them to SAS missing. They are
  never silently scored as absent.
* Exclusions: DIAB_CX > DIAB_UNCX; HTN_CX > HTN_UNCX; CANCER_METS > CANCER_SOLID
  and CANCER_NSITU; CANCER_SOLID > CANCER_NSITU; and, with POA, LIVER_SEV >
  LIVER_MLD and RENLFL_SEV > RENLFL_MOD. Metastatic cancer does NOT suppress
  leukemia or lymphoma.

Input normalisation (not part of the SAS program, which expects clean data):
codes are stripped, upper-cased and have decimal points removed; POA values are
stripped and upper-cased.
"""

import warnings
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from ._data import ahrq_data, icd_version_for_date, MAX_ICD_VERSION, MIN_ICD_VERSION

POA_PRESENT = ("Y", "W")
POA_NOT_PRESENT = ("N", "U")

# AHRQ's combined $COMFMT labels: (POA-independent measures, POA-dependent measures).
# Source: CMR_Mapping_Program_v2027-1.sas lines 237-242 (POA-independent part)
# and lines 269-294 (POA-dependent part). The test suite re-derives this table
# from the SAS text and from AHRQ's reference file.
COMBINED_LABELS: Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...]]] = {
    "DRUGPSYCHOSES":      (("DRUG",),       ("PSYCHOSES",)),
    "HFHTN_CX":           (("HTN_CX",),     ("HF",)),
    "HTN_CXRENLFL_SEV":   (("HTN_CX",),     ("RENLFL_SEV",)),
    "HFHTN_CXRENLFL_SEV": (("HTN_CX",),     ("HF", "RENLFL_SEV")),
    "ALCOHOLLIVER_MLD":   (("ALCOHOL",),    ("LIVER_MLD",)),
    "VALVE_AUTOIMMUNE":   (("AUTOIMMUNE",), ("VALVE",)),
    "CBVD_SQLAPARALYSIS": ((),              ("PARALYSIS", "CBVD_SQLA")),
    "LIVER_MLD_NEURO":    ((),              ("LIVER_MLD", "NEURO_OTH")),
    "NEURO_OTH_SEIZ":     ((),              ("NEURO_OTH", "NEURO_SEIZ")),
    "LIVER_MLD_PULMCIRC": ((),              ("LIVER_MLD", "PULMCIRC")),
}

_INTERMEDIATE = ("CBVD_POA", "CBVD_SQLA")


def _measures() -> List[str]:
    return [m["name"] for m in ahrq_data()["measures"]]


def _poa_dependent() -> frozenset:
    return frozenset(m["name"] for m in ahrq_data()["measures"] if m["poa_dependent"])


def label_parts(label: str) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    """Split an AHRQ $COMFMT label into (POA-independent, POA-dependent) measures."""
    data = ahrq_data()
    if label in data["valanypoa"]:
        return (label,), ()
    if label in data["valpoa"]:
        return (), (label,)
    if label in COMBINED_LABELS:
        return COMBINED_LABELS[label]
    raise ValueError(f"Unknown AHRQ comorbidity label {label!r}")


def normalize_code(code) -> str:
    if code is None:
        return ""
    if isinstance(code, float) and code != code:  # NaN
        return ""
    return str(code).strip().upper().replace(".", "")


def normalize_poa(poa) -> str:
    if poa is None:
        return ""
    if isinstance(poa, float) and poa != poa:  # NaN
        return ""
    return str(poa).strip().upper()


@dataclass
class CodeTrace:
    """How one diagnosis code was handled."""
    position: int                       # 1 = principal diagnosis
    code: str                           # normalised code
    poa: Optional[str]                  # normalised POA value, None if POA not available
    ahrq_label: Optional[str]           # AHRQ $COMFMT label, None if the code is not mapped
    poa_independent: Tuple[str, ...] = ()
    poa_dependent: Tuple[str, ...] = ()
    poa_exempt: bool = False
    counted: Tuple[str, ...] = ()        # measures this code set (before exclusions)
    note: str = ""


@dataclass
class ComorbidityResult:
    """Result of assigning the 38 AHRQ Elixhauser measures to one discharge."""
    flags: Dict[str, Optional[bool]]    # 38 measures; None = not assessable (no POA data)
    icd_version: int
    poa_available: bool
    principal_dx: Optional[str]
    trace: List[CodeTrace] = field(default_factory=list)
    cmr_version: str = "2027.1"

    @property
    def present(self) -> List[str]:
        return [m for m, v in self.flags.items() if v]

    @property
    def not_assessable(self) -> List[str]:
        return [m for m, v in self.flags.items() if v is None]

    @property
    def partial(self) -> bool:
        """True when POA-dependent measures could not be assessed."""
        return bool(self.not_assessable)


def assign_comorbidities(
    principal_dx,
    secondary_dx: Sequence,
    secondary_poa: Optional[Sequence] = None,
    *,
    poa_available: Optional[bool] = None,
    icd_version: Optional[int] = None,
    discharge_date=None,
) -> ComorbidityResult:
    """Assign the 38 AHRQ Elixhauser Refined measures to one discharge.

    Args:
        principal_dx: The principal diagnosis (never mapped; recorded for the trace).
            Pass None if the record genuinely has no principal diagnosis.
        secondary_dx: Secondary diagnosis codes (SAS DX2, DX3, ...).
        secondary_poa: POA indicators parallel to ``secondary_dx`` (Y, N, U, W,
            1 or blank). Omit when the data carry no POA indicators.
        poa_available: Whether POA indicators exist in the data (SAS macro
            ``%LET POA``). Defaults to ``secondary_poa is not None``.
        icd_version: ICD-10-CM version 33-44 used to choose AHRQ's POA-exempt list.
        discharge_date: Alternatively, the discharge date; the version is derived
            exactly as the SAS program derives it. If neither is given, AHRQ's
            default (version 44, FY2027) applies.
    """
    data = ahrq_data()
    comfmt = data["comfmt"]
    measures = _measures()
    poa_dep_measures = _poa_dependent()

    secondary_dx = list(secondary_dx or [])
    if poa_available is None:
        poa_available = secondary_poa is not None
    if secondary_poa is None:
        secondary_poa = [None] * len(secondary_dx)
    else:
        secondary_poa = list(secondary_poa)
    if len(secondary_poa) != len(secondary_dx):
        raise ValueError("secondary_dx and secondary_poa must have the same length")

    if icd_version is not None and discharge_date is not None:
        raise ValueError("Pass icd_version or discharge_date, not both")
    if icd_version is None:
        icd_version = icd_version_for_date(discharge_date) if discharge_date is not None else MAX_ICD_VERSION
    icd_version = int(icd_version)
    if not (MIN_ICD_VERSION <= icd_version <= MAX_ICD_VERSION):
        raise ValueError(f"icd_version must be {MIN_ICD_VERSION}-{MAX_ICD_VERSION}")
    exempt_list = data["exempt"][icd_version]

    any_poa = {m: False for m in measures if m not in poa_dep_measures}
    poa_flags = {m: False for m in poa_dep_measures if m != "CBVD"}
    poa_flags.update({k: False for k in _INTERMEDIATE})
    cbvd_npoa = False

    principal = normalize_code(principal_dx) or None
    trace: List[CodeTrace] = []
    if principal is not None:
        trace.append(CodeTrace(1, principal, None, comfmt.get(principal),
                               note="principal diagnosis: never mapped (AHRQ maps secondary diagnoses only)"))

    for pos, (raw_code, raw_poa) in enumerate(zip(secondary_dx, secondary_poa), start=2):
        code = normalize_code(raw_code)
        if not code:
            continue
        poa = normalize_poa(raw_poa) if poa_available else None
        label = comfmt.get(code)
        t = CodeTrace(pos, code, poa, label)
        trace.append(t)
        if label is None:
            t.note = "not an Elixhauser comorbidity code"
            continue
        indep, dep = label_parts(label)
        t.poa_independent, t.poa_dependent = indep, dep
        counted = list(indep)
        for m in indep:
            any_poa[m] = True
        if poa_available:
            exempt = code in exempt_list
            t.poa_exempt = exempt
            if exempt or poa in POA_PRESENT:
                for m in dep:
                    poa_flags[m] = True
                counted.extend(dep)
            elif dep:
                t.note = (f"POA '{poa}' is not Y or W: POA-dependent measure(s) "
                          f"{', '.join(dep)} not counted")
            if not exempt and poa in POA_NOT_PRESENT and label == "CBVD_POA":
                cbvd_npoa = True
                t.note = "cerebrovascular event not present on admission (CBVD_NPOA)"
        elif dep:
            t.note = f"POA not available: {', '.join(dep)} not assessable"
        t.counted = tuple(counted)

    flags: Dict[str, Optional[bool]] = dict(any_poa)
    # Exclusions for POA-independent measures (SAS lines 311-317)
    if flags["DIAB_CX"]:
        flags["DIAB_UNCX"] = False
    if flags["HTN_CX"]:
        flags["HTN_UNCX"] = False
    if flags["CANCER_METS"]:
        flags["CANCER_SOLID"] = False
        flags["CANCER_NSITU"] = False
    if flags["CANCER_SOLID"]:
        flags["CANCER_NSITU"] = False

    if poa_available:
        # Exclusions and CBVD derivation for POA-dependent measures (SAS lines 324-326)
        if poa_flags["LIVER_SEV"]:
            poa_flags["LIVER_MLD"] = False
        if poa_flags["RENLFL_SEV"]:
            poa_flags["RENLFL_MOD"] = False
        cbvd = poa_flags["CBVD_POA"] or (
            not poa_flags["CBVD_POA"] and not cbvd_npoa and poa_flags["CBVD_SQLA"])
        for m in poa_dep_measures:
            flags[m] = cbvd if m == "CBVD" else poa_flags[m]
    else:
        for m in poa_dep_measures:
            flags[m] = None

    ordered = {m: (None if flags[m] is None else bool(flags[m])) for m in measures}
    return ComorbidityResult(ordered, icd_version, bool(poa_available), principal, trace,
                             data["cmr_version"])


class ElixhauserMapper:
    """Map ICD-10-CM codes to the 38 AHRQ Elixhauser Refined comorbidity measures (v2027.1)."""

    def __init__(self, reference_file_path: str = None):
        if reference_file_path is not None:
            warnings.warn(
                "reference_file_path is ignored: since 2027.1.0 the mapping is compiled from "
                "AHRQ's SAS format program (see tools/build_data.py). Use ElixhauserLoader "
                "to explore a reference file.", DeprecationWarning, stacklevel=2)
        self.data = ahrq_data()
        self.cmr_version = self.data["cmr_version"]
        self.measures = _measures()

    # -- full result ---------------------------------------------------
    def assign(self, principal_dx, secondary_dx, secondary_poa=None, **kwargs) -> ComorbidityResult:
        """See :func:`assign_comorbidities`."""
        return assign_comorbidities(principal_dx, secondary_dx, secondary_poa, **kwargs)

    # -- convenience ---------------------------------------------------
    def describe_code(self, icd10_code, icd_version: int = MAX_ICD_VERSION) -> dict:
        """AHRQ label, measures and POA-exemption status of a single code."""
        code = normalize_code(icd10_code)
        label = self.data["comfmt"].get(code)
        indep, dep = label_parts(label) if label else ((), ())
        return {
            "code": code,
            "ahrq_label": label,
            "poa_independent": [m if m not in _INTERMEDIATE else "CBVD" for m in indep],
            "poa_dependent": [m if m not in _INTERMEDIATE else "CBVD" for m in dep],
            "poa_exempt": code in self.data["exempt"][int(icd_version)],
        }

    def map_single_code(self, icd10_code, poa_indicator=None, **kwargs) -> Dict[str, Optional[bool]]:
        """Flags produced by one code when it is a secondary diagnosis."""
        poa = None if poa_indicator is None else [poa_indicator]
        return assign_comorbidities(None, [icd10_code], poa, **kwargs).flags

    def map_patient_diagnoses(
        self,
        diagnosis_codes: Sequence,
        poa_indicators: Optional[Sequence] = None,
        *,
        principal_included: bool = True,
        **kwargs,
    ) -> Dict[str, Optional[bool]]:
        """Flags for one discharge from a diagnosis list.

        By default ``diagnosis_codes[0]`` is the PRINCIPAL diagnosis and is not
        mapped (as in AHRQ's SAS program). Pass ``principal_included=False`` if
        the list holds secondary diagnoses only. ``poa_indicators`` is parallel
        to ``diagnosis_codes``. Without ``poa_indicators`` the 18 POA-dependent
        measures are returned as None (not assessable).
        """
        codes = list(diagnosis_codes)
        poa = None if poa_indicators is None else list(poa_indicators)
        if poa is not None and len(poa) != len(codes):
            raise ValueError("diagnosis_codes and poa_indicators must have the same length")
        if principal_included:
            principal, codes = (codes[0] if codes else None), codes[1:]
            poa = None if poa is None else poa[1:]
        else:
            principal = None
        return assign_comorbidities(principal, codes, poa, **kwargs).flags

    def map_dataframe(
        self,
        df,
        patient_id_col: str,
        diagnosis_col: str,
        poa_col: Optional[str] = None,
        dx_sequence_col: Optional[str] = None,
        *,
        poa_available: Optional[bool] = None,
        discharge_date_col: Optional[str] = None,
    ):
        """Map a long-format DataFrame (one row per diagnosis) to one row per discharge.

        The row with the lowest ``dx_sequence_col`` value (1 = principal) is the
        principal diagnosis. Without ``dx_sequence_col`` the first row of each
        discharge is taken as principal, and a warning is issued.
        Flag columns use pandas' nullable boolean dtype; <NA> means not assessable.
        """
        import pandas as pd

        if dx_sequence_col is None:
            warnings.warn("No dx_sequence_col given: the first row of each discharge is "
                          "treated as the principal diagnosis.", UserWarning, stacklevel=2)
        if poa_available is None:
            poa_available = poa_col is not None
        rows = []
        for pid, group in df.groupby(patient_id_col, sort=False):
            if dx_sequence_col is not None:
                group = group.sort_values(dx_sequence_col, kind="stable")
            codes = group[diagnosis_col].tolist()
            poa = group[poa_col].tolist() if poa_col is not None else None
            kwargs = {"poa_available": poa_available}
            if discharge_date_col is not None:
                kwargs["discharge_date"] = group[discharge_date_col].iloc[0]
            res = assign_comorbidities(codes[0] if codes else None, codes[1:],
                                       None if poa is None else poa[1:], **kwargs)
            row = {patient_id_col: pid}
            row.update(res.flags)
            row["ICD_VERSION"] = res.icd_version
            row["POA_AVAILABLE"] = res.poa_available
            rows.append(row)
        out = pd.DataFrame(rows)
        for m in self.measures:
            if m in out.columns:
                out[m] = out[m].astype("boolean")
        return out

    def get_category_definitions(self):
        """The 38 measures with AHRQ labels and POA dependence."""
        import pandas as pd
        return pd.DataFrame(self.data["measures"])
