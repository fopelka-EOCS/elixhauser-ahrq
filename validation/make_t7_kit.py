"""Build the T7 kit: a fixed synthetic input file, run-ready copies of AHRQ's
SAS programs, a SAS driver, and the package's expected output, so that anyone
with SAS can compare AHRQ's executed software with this package.

Usage (from the repository root):  python validation/make_t7_kit.py
Output: validation/t7_kit/

Only the lines AHRQ marks "USER MUST MODIFY" / "USER MAY MODIFY" are changed in
the SAS copies; validation/t7_kit/SAS_EDITS.diff lists every changed line.
"""
import csv
import difflib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elixhauser_ahrq import icd_version_for, score_discharge  # noqa: E402
from elixhauser_ahrq._data import ahrq_data  # noqa: E402

KIT = ROOT / "validation" / "t7_kit"
SAS = ROOT / "SAS-Programs"
N, SEED, NUMDX = 2000, 20277, 40


def records():
    d = ahrq_data()
    comfmt = d["comfmt"]
    mapped = sorted(comfmt)
    special = sorted(c for c, lab in comfmt.items() if lab not in d["valanypoa"] and lab not in d["valpoa"])
    cbvd = sorted(c for c, lab in comfmt.items() if lab.startswith("CBVD"))
    exempt = sorted({c for v in d["exempt"].values() for c in v} & set(comfmt))
    unmapped = sorted(set(d["exempt"][44]) - set(comfmt))
    rng = random.Random(SEED)
    poa_values = ["Y", "Y", "Y", "N", "U", "W", "1", ""]
    for i in range(1, N + 1):
        k = rng.randint(1, 25)
        dx = [rng.choice(mapped if r < 0.45 else special if r < 0.6 else cbvd if r < 0.72 else
                         exempt if r < 0.87 else unmapped) for r in (rng.random() for _ in range(k))]
        poa = [rng.choice(poa_values) for _ in dx]
        year = rng.choice([2016, 2018, 2020, 2022, 2024, 2025, 2026, 2026, 2027, 2027])
        dqtr = rng.randint(1, 4)
        if year == 2027:
            dqtr = rng.randint(1, 3)
        yield {"KEY": i, "YEAR": year, "DQTR": dqtr, "dx": dx, "poa": poa}


def patch(name, replacements, poa_flag=None):
    src = (SAS / name).read_text(encoding="utf-8-sig")
    out = src
    for old, new in replacements:
        assert out.count(old) == 1, (name, old)
        out = out.replace(old, new)
    return src, out


def main():
    KIT.mkdir(parents=True, exist_ok=True)
    recs = list(records())

    cols = ["KEY", "YEAR", "DQTR", "I10_NDX"] + [f"I10_DX{i}" for i in range(1, NUMDX + 1)] + \
           [f"DXPOA{i}" for i in range(1, NUMDX + 1)]
    with open(KIT / "t7_input.csv", "w", newline="", encoding="ascii") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(cols)
        for r in recs:
            dx = r["dx"] + [""] * (NUMDX - len(r["dx"]))
            poa = r["poa"] + [""] * (NUMDX - len(r["poa"]))
            w.writerow([r["KEY"], r["YEAR"], r["DQTR"], len(r["dx"])] + dx + poa)

    expected = []
    for poa_flag in (1, 0):
        for r in recs:
            res = score_discharge(r["dx"][0], r["dx"][1:], r["poa"][1:] if poa_flag else None,
                                  poa_available=bool(poa_flag), icd_version=icd_version_for(r["YEAR"], r["DQTR"]))
            expected.append({"POA_RUN": poa_flag, "KEY": r["KEY"], "ICDVER": res["icd_version"],
                             **{f"CMR_{m}": ("" if v is None else int(v)) for m, v in res["flags"].items()},
                             "CMR_Index_Mortality": res["mortality_index"],
                             "CMR_Index_Readmission": res["readmission_index"]})
    with open(KIT / "package_expected.csv", "w", newline="", encoding="ascii") as fh:
        w = csv.DictWriter(fh, fieldnames=list(expected[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(expected)

    diffs = []
    lib = "LIBNAME LIBRARY 'C:\\COMORB\\FMTLIB\\';"
    files = {
        "CMR_Format_Program_v2027-1.sas": [(lib, "LIBNAME LIBRARY \"&T7DIR\";")],
        "CMR_Index_Program_v2027-1.sas": [
            ("LIBNAME  IN1     'C:\\SASDATA\\';", "LIBNAME  IN1     \"&T7DIR\";"),
            ("LIBNAME  OUT1    'C:\\SASDATA\\';", "LIBNAME  OUT1    \"&T7DIR\";"),
            ("%Let CORE = YOUR_SAS_INPUT_FILE_HERE;", "%Let CORE = T7_MAPPED;"),
            ("%Let OUT  = YOUR_SAS_OUTPUT_FILE_HERE;", "%Let OUT  = T7_SCORED;"),
        ],
    }
    for name, reps in files.items():
        src, out = patch(name, reps)
        (KIT / name).write_text(out, encoding="utf-8")
        diffs += difflib.unified_diff(src.splitlines(), out.splitlines(), name, "t7_kit/" + name, lineterm="", n=0)
    for poa_flag in (1, 0):
        name = "CMR_Mapping_Program_v2027-1.sas"
        src, out = patch(name, [
            (lib, "LIBNAME LIBRARY \"&T7DIR\";"),
            ("LIBNAME  IN1    'C:\\SASDATA\\';", "LIBNAME  IN1    \"&T7DIR\";"),
            ("LIBNAME  OUT1   'C:\\SASDATA\\';", "LIBNAME  OUT1   \"&T7DIR\";"),
            ("%LET POA   = 1;", f"%LET POA   = {poa_flag};"),
            ("%Let CORE = YOUR_SAS_INPUT_FILE_HERE;", "%Let CORE = T7_INPUT;"),
            ("%Let OUT  = YOUR_SAS_OUTPUT_FILE_HERE;", "%Let OUT  = T7_MAPPED;"),
        ])
        target = f"CMR_Mapping_Program_v2027-1_POA{poa_flag}.sas"
        (KIT / target).write_text(out, encoding="utf-8")
        diffs += difflib.unified_diff(src.splitlines(), out.splitlines(), name, "t7_kit/" + target, lineterm="", n=0)
    (KIT / "SAS_EDITS.diff").write_text("\n".join(diffs) + "\n", encoding="utf-8")

    dx_len = " ".join(f"I10_DX{i}" for i in range(1, NUMDX + 1))
    poa_len = " ".join(f"DXPOA{i}" for i in range(1, NUMDX + 1))
    driver = f"""/* T7: run AHRQ's v2027.1 SAS programs on t7_input.csv, for both POA settings.
   Set T7DIR to the folder holding this kit (with a trailing slash), then submit this file.
   Output: sas_output.csv in the same folder. Return that file unchanged. */
%LET T7DIR = C:\\T7\\;   /* <=== set this */

%include "&T7DIR.CMR_Format_Program_v2027-1.sas";

%macro run_one(poa);
  DATA T7.T7_INPUT;
    INFILE "&T7DIR.t7_input.csv" DSD FIRSTOBS=2 LRECL=32767 TRUNCOVER;
    LENGTH KEY YEAR DQTR I10_NDX 8 {dx_len} $7 {poa_len} $1;
    INPUT KEY YEAR DQTR I10_NDX {dx_len} {poa_len};
  RUN;
  %include "&T7DIR.CMR_Mapping_Program_v2027-1_POA&poa..sas";
  %include "&T7DIR.CMR_Index_Program_v2027-1.sas";
  DATA T7.RESULT_&poa;
    SET T7.T7_SCORED;
    POA_RUN = &poa;
    KEEP POA_RUN KEY ICDVER CMR_: ;
    DROP CMR_VERSION;
  RUN;
%mend;

LIBNAME T7 "&T7DIR";
%run_one(1);
%run_one(0);
DATA T7.ALL_RESULTS; SET T7.RESULT_1 T7.RESULT_0; RUN;
PROC EXPORT DATA=T7.ALL_RESULTS OUTFILE="&T7DIR.sas_output.csv" DBMS=CSV REPLACE; RUN;
"""
    (KIT / "RUN_T7.sas").write_text(driver, encoding="utf-8")

    (KIT / "README.md").write_text(f"""# T7 kit: compare AHRQ's executed SAS software with elixhauser-ahrq

**Purpose.** This is the one validation tier this package cannot run itself. It compares AHRQ's own executed SAS software (Elixhauser Comorbidity Software Refined for ICD-10-CM, v2027.1) with this package, field by field.

**Inputs.** `t7_input.csv` holds {N:,} synthetic discharges (seed {SEED}). It contains no patient data. The discharges are enriched with combined-label, cerebrovascular and POA-exempt codes and with every POA value, and they span ICD-10-CM versions 33–44.

**Runs.** The kit runs twice: with POA indicators (`%LET POA = 1`) and without them (`%LET POA = 0`).

## Running it (about 15–30 minutes, any SAS 9.4 or SAS Viya environment, including SAS OnDemand for Academics)

1. Copy this folder to the SAS machine.
2. In `RUN_T7.sas`, set `T7DIR` to that folder.
3. Submit `RUN_T7.sas`.
4. Return `sas_output.csv`.

The SAS programs here are AHRQ's v2027.1 programs. Only the lines AHRQ marks for user modification have changed: library paths, file names and the POA switch. `SAS_EDITS.diff` lists every changed line.

## Comparing

```bash
python validation/t7_compare.py validation/t7_kit/sas_output.csv
```

The script compares all 38 flags, ICDVER and both indices with `package_expected.csv`. The tier passes only with 0 mismatches.
""", encoding="utf-8")
    print(f"T7 kit written to {KIT} ({N} records x 2 POA settings)")


if __name__ == "__main__":
    main()
