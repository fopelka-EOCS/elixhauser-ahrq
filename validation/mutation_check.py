"""Re-plant each 2026 defect in a temporary copy and confirm the test suite fails.

Usage (from the repository root):  python validation/mutation_check.py
Exit code 0 only if the unmutated copy passes and every mutation is caught.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPPER = Path("elixhauser_ahrq") / "mapper.py"

MUTATIONS = [
    ("control (no mutation)", None, None),
    ("R2 metastatic cancer suppresses leukemia/lymphoma",
     '        flags["CANCER_NSITU"] = False\n    if flags["CANCER_SOLID"]:',
     '        flags["CANCER_NSITU"] = False\n        flags["CANCER_LEUK"] = False\n'
     '        flags["CANCER_LYMPH"] = False\n    if flags["CANCER_SOLID"]:'),
    ("R3 POA-exempt lists ignored", "exempt = code in exempt_list", "exempt = False"),
    ("R4 POA '1' accepted as present", 'POA_PRESENT = ("Y", "W")', 'POA_PRESENT = ("Y", "W", "1")'),
    ("R5 CBVD not-on-admission override unreachable", "cbvd_npoa = True", "cbvd_npoa = False"),
    ("R6 missing POA scored as absent", "flags[m] = None", "flags[m] = False"),
    ("R7 principal diagnosis mapped",
     "for pos, (raw_code, raw_poa) in enumerate(zip(secondary_dx, secondary_poa), start=2):",
     "for pos, (raw_code, raw_poa) in enumerate(zip(([principal_dx] if principal_dx else []) + secondary_dx, "
     "([\"\"] if principal_dx else []) + secondary_poa), start=2):"),
]


def main() -> int:
    ok = True
    for name, old, new in MUTATIONS:
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "c"
            shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns(".git", "*.egg-info", "dist", "build"))
            if old is not None:
                src = (copy / MAPPER).read_text(encoding="utf-8")
                assert src.count(old) == 1, f"mutation anchor not unique: {name}"
                (copy / MAPPER).write_text(src.replace(old, new), encoding="utf-8")
            env = dict(os.environ, PYTHONPATH=str(copy), ELIX_DIFF_N="3000")
            res = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"],
                                 cwd=copy, env=env, capture_output=True, text=True)
            summary = res.stdout.strip().splitlines()[-1] if res.stdout.strip() else res.stderr[-200:]
            caught = res.returncode != 0
            expected = old is not None
            status = "OK" if caught == expected else "PROBLEM"
            ok &= caught == expected
            print(f"{status:8} {name}: {summary}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
