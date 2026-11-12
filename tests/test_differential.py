"""T6: randomized differential test against the independent SAS transliteration.

Synthetic discharges, deliberately enriched with mapped, combined-label,
POA-exempt and cerebrovascular codes, all POA values (Y, N, U, W, 1, blank,
missing), every ICD-10-CM version 33-44 plus out-of-window dates, and records
without POA data. These are stress-test rates, not real-world estimates.

Inputs are restricted to what the SAS program accepts verbatim (upper-case,
no decimals, at most 39 secondary diagnoses), so any difference is a logic
difference, not an input-normalisation difference.
"""
import os
import random

import pytest

from elixhauser_ahrq import icd_version_for, score_discharge
from elixhauser_ahrq._data import ahrq_data

N = int(os.environ.get("ELIX_DIFF_N", "20000"))
SEEDS = [20271, 20272]


def _pools():
    d = ahrq_data()
    comfmt = d["comfmt"]
    mapped = sorted(comfmt)
    combined = sorted(c for c, lab in comfmt.items() if lab not in d["valanypoa"] and lab not in d["valpoa"])
    cbvd = sorted(c for c, lab in comfmt.items() if lab.startswith("CBVD"))
    exempt_mapped = sorted({c for v in d["exempt"].values() for c in v} & set(comfmt))
    exempt_unmapped = sorted(({c for c in d["exempt"][44]} | {c for c in d["exempt"][33]}) - set(comfmt))
    return mapped, combined, cbvd, exempt_mapped, exempt_unmapped


def _records(seed, n):
    mapped, combined, cbvd, exempt_mapped, exempt_unmapped = _pools()
    rng = random.Random(seed)
    poa_values = ["Y", "Y", "Y", "N", "U", "W", "1", "", None]
    for i in range(n):
        k = rng.randint(0, 24)
        dx = []
        for _ in range(k + 1):
            r = rng.random()
            pool = (mapped if r < 0.45 else combined if r < 0.60 else cbvd if r < 0.72
                    else exempt_mapped if r < 0.87 else exempt_unmapped)
            dx.append(rng.choice(pool))
        poa_available = rng.random() < 0.85
        poa = [rng.choice(poa_values) for _ in dx] if poa_available else None
        year = rng.choice([None, 2014, 2015, 2016, 2018, 2020, 2022, 2024, 2025, 2026, 2026, 2027, 2027, 2028])
        dqtr = None if year is None else rng.choice([1, 2, 3, 4])
        yield {"id": i, "year": year, "dqtr": dqtr, "dx": dx, "poa": poa,
               "poa_available": poa_available, "ndx": None}


@pytest.mark.parametrize("seed", SEEDS)
def test_zero_mismatches_against_sas_transliteration(seed, sas_reference):
    mod, fmt, weights = sas_reference
    mismatches = []
    n = 0
    for rec in _records(seed, N):
        n += 1
        ref = mod.assign(rec, fmt)
        ref_ver = ref.pop("ICDVER")
        ref_readm, ref_mort = mod.index(ref, weights)
        ref_flags = {k[4:]: (None if v is None else bool(v)) for k, v in ref.items()}

        poa = rec["poa"][1:] if rec["poa"] is not None else None
        got = score_discharge(rec["dx"][0], rec["dx"][1:], poa,
                              poa_available=rec["poa_available"],
                              icd_version=icd_version_for(rec["year"], rec["dqtr"]))
        if (got["flags"] != ref_flags or got["icd_version"] != ref_ver
                or got["mortality_index"] != ref_mort or got["readmission_index"] != ref_readm):
            mismatches.append(rec["id"])
    assert n == N
    assert not mismatches, f"{len(mismatches)} of {N} records differ; first ids {mismatches[:10]}"
