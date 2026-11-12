"""Compare AHRQ SAS output (from validation/t7_kit/RUN_T7.sas) with package_expected.csv.

Usage: python validation/t7_compare.py <sas_output.csv> [package_expected.csv]
Exit 0 only if every field of every record matches.
"""
import csv
import sys
from pathlib import Path


def norm(v):
    v = (v or "").strip()
    if v in ("", "."):
        return ""
    try:
        return str(int(float(v)))
    except ValueError:
        return v


def load(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    return {(norm(r["POA_RUN"]), norm(r["KEY"])): {k.upper(): norm(v) for k, v in r.items()} for r in rows}


def main(argv):
    sas = load(argv[1])
    pkg = load(argv[2] if len(argv) > 2 else Path(__file__).with_name("t7_kit") / "package_expected.csv")
    fields = [f for f in next(iter(pkg.values())) if f not in ("POA_RUN", "KEY")]
    missing = sorted(set(pkg) - set(sas))
    mismatches = []
    for key, expected in pkg.items():
        got = sas.get(key)
        if got is None:
            continue
        for f in fields:
            if got.get(f) != expected[f]:
                mismatches.append((key, f, got.get(f), expected[f]))
    print(f"records compared: {len(set(pkg) & set(sas))} of {len(pkg)}; missing from SAS output: {len(missing)}")
    print(f"field mismatches: {len(mismatches)}")
    for m in mismatches[:25]:
        print("  POA_RUN={0[0]} KEY={0[1]} {1}: SAS={2!r} package={3!r}".format(*m))
    return 0 if not mismatches and not missing else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
