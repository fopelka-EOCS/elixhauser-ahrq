"""Build the corrected FY2027 files for the Hugging Face dataset
EOCS-LTD/elixhauser-icd10-mapping from AHRQ's v2027.1 files.

Usage (from the repository root):  python tools/build_hf_dataset.py <output_dir>

Writes:
  elixhauser_icd10_mapping.csv  every code x 39 mapping columns, copied from AHRQ's
                                reference workbook (DX_to_Comorb_Mapping), footer removed
  comorbidity_measures.csv      38 measures: AHRQ label, POA dependence, and AHRQ's
                                mortality and readmission index weights (from the SAS index program)
  poa_exempt_codes.csv          AHRQ POA-exempt codes by ICD-10-CM version (33-44)
  README.md                     dataset card

Each output is checked against the package's SAS-derived data before it is written.
"""
import csv
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elixhauser_ahrq import __version__  # noqa: E402
from elixhauser_ahrq._data import ahrq_data  # noqa: E402
from elixhauser_ahrq.mapper import label_parts  # noqa: E402

WORKBOOK = ROOT / "SAS-Programs" / "CMR-Reference-File-v2027-1.xlsx"
CARD = ROOT / "tools" / "hf_dataset_card.md"


def main(out_dir: str) -> int:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    data = ahrq_data()

    wb = pd.read_excel(WORKBOOK, sheet_name="DX_to_Comorb_Mapping", skiprows=1, dtype=str)
    wb = wb[wb.iloc[:, 0].str.strip().str.lower() != "end of content"].copy()
    cols = list(wb.columns[3:])
    mapping = pd.DataFrame({
        "icd10cm_code": wb.iloc[:, 0].str.strip(),
        "icd10cm_description": wb.iloc[:, 1].str.strip(),
        "comorbidity_count": wb.iloc[:, 2].astype(float).astype(int),
    })
    for c in cols:
        mapping[c] = wb[c].astype(float).fillna(0).astype(int)

    # Check against the SAS-derived data
    assert set(mapping.icd10cm_code) == set(data["comfmt"]) and len(mapping) == 4573
    for _, r in mapping.iterrows():
        indep, dep = label_parts(data["comfmt"][r.icd10cm_code])
        assert {c for c in cols if r[c] == 1} == set(indep) | set(dep), r.icd10cm_code
    mapping.to_csv(out / "elixhauser_icd10_mapping.csv", index=False, lineterminator="\n")

    w = data["weights"]
    measures = pd.DataFrame([{
        "abbreviation": m["name"],
        "description": m["label"],
        "requires_poa": "Yes" if m["poa_dependent"] else "No",
        "ahrq_mortality_index_weight": w["mortality"][m["name"]],
        "ahrq_readmission_index_weight": w["readmission"][m["name"]],
    } for m in data["measures"]])
    assert len(measures) == 38 and (measures.requires_poa == "Yes").sum() == 18
    measures.to_csv(out / "comorbidity_measures.csv", index=False, lineterminator="\n")

    with open(out / "poa_exempt_codes.csv", "w", newline="\n", encoding="utf-8") as fh:
        wr = csv.writer(fh, lineterminator="\n")
        wr.writerow(["icd10cm_version", "icd10cm_code"])
        for v, codes in sorted(data["exempt"].items()):
            for c in sorted(codes):
                wr.writerow([v, c])

    (out / "README.md").write_text(CARD.read_text(encoding="utf-8").replace("{PACKAGE_VERSION}", __version__),
                                   encoding="utf-8")
    print(f"wrote {out}: {len(mapping)} codes, {len(measures)} measures")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
