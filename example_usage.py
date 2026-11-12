"""example_usage.py - worked examples for elixhauser-ahrq 2027.1.0 (AHRQ v2027.1)."""

import pandas as pd

from elixhauser_ahrq import (ElixhauserMapper, ElixhauserScorer, assign_comorbidities,
                             score_discharge)


def single_discharge():
    print("1. One discharge with POA indicators")
    r = score_discharge("I214", ["I5022", "E1122", "N186", "C7800", "I69351"],
                        ["Y", "Y", "N", "Y", ""], discharge_date="2026-11-02")
    print("   present:", r["present"])
    print("   mortality index:", r["mortality_index"], "| readmission index:", r["readmission_index"])


def explain_each_code():
    print("2. Why each code did or did not count")
    res = assign_comorbidities("I214", ["I5022", "I63213", "I69918", "Z6818"], ["N", "N", "Y", "N"],
                               discharge_date="2026-12-01")
    for t in res.trace:
        print(f"   DX{t.position} {t.code:8} label={t.ahrq_label} poa={t.poa} exempt={t.poa_exempt} "
              f"counted={list(t.counted)} {t.note}")
    print("   present:", res.present)


def without_poa():
    print("3. Data without POA indicators: a partial index")
    r = score_discharge("I214", ["I5022", "E119"])
    print("   present:", r["present"], "| not assessable:", len(r["not_assessable"]),
          "| partial:", r["partial"], "| mortality index:", r["mortality_index"])


def dataframe():
    print("4. Long-format DataFrame")
    df = pd.DataFrame({
        "encounter": [1, 1, 1, 2, 2],
        "dx_seq": [1, 2, 3, 1, 2],
        "dx": ["I214", "I5022", "C9100", "K8000", "E119"],
        "poa": ["Y", "Y", "Y", "Y", "Y"],
        "discharge_date": ["2026-11-02"] * 3 + ["2027-01-15"] * 2,
    })
    flags = ElixhauserMapper().map_dataframe(df, "encounter", "dx", poa_col="poa", dx_sequence_col="dx_seq",
                                             discharge_date_col="discharge_date")
    scored = ElixhauserScorer("mortality").score_dataframe(flags)
    print(scored[["encounter", "HF", "CANCER_LEUK", "DIAB_UNCX", "elixhauser_score", "index_partial"]])


if __name__ == "__main__":
    single_discharge()
    explain_each_code()
    without_poa()
    dataframe()
