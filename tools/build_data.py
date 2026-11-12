"""Compile AHRQ's Elixhauser Comorbidity Software Refined SAS programs into the
package's bundled data file.

Nothing in the bundled data is hand-copied: every code list, POA-exempt list,
weight, measure label and POA classification is parsed from AHRQ's own SAS
programs in ``SAS-Programs/``. The test suite re-runs this parse and asserts
that the bundled file is identical, so the package cannot drift from AHRQ's
published software.

Usage (from the repository root):
    python tools/build_data.py            # writes elixhauser_ahrq/data/cmr_v2027_1.json.gz
    python tools/build_data.py --check    # exits 1 if the bundled file is stale
"""

import argparse
import gzip
import hashlib
import io
import json
import re
import sys
from pathlib import Path

CMR_VERSION = "2027.1"
FILE_TAG = "v2027-1"

ROOT = Path(__file__).resolve().parents[1]
SAS_DIR = ROOT / "SAS-Programs"
OUT = ROOT / "elixhauser_ahrq" / "data" / "cmr_v2027_1.json.gz"

FORMAT_PROGRAM = f"CMR_Format_Program_{FILE_TAG}.sas"
MAPPING_PROGRAM = f"CMR_Mapping_Program_{FILE_TAG}.sas"
INDEX_PROGRAM = f"CMR_Index_Program_{FILE_TAG}.sas"
REFERENCE_FILE = f"CMR-Reference-File-{FILE_TAG}.xlsx"

_TOKEN = re.compile(r'"([^"]*)"|\'([^\']*)\'|(=)|(;)')


def _read(path: Path) -> str:
    return path.read_text(encoding="latin-1").replace("\r", "")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_value_blocks(text: str) -> dict:
    """Parse every ``VALUE $NAME ... ;`` block of a SAS PROC FORMAT.

    Returns {format_name_upper: {code: label}}. The ``other = " "`` clause is
    ignored (it maps unlisted values to blank, which is the default here).
    """
    starts = [(m.start(), m.end(), m.group(1).upper())
              for m in re.finditer(r"\bvalue\s+\$(\w+)", text, re.IGNORECASE)]
    blocks = {}
    for i, (_, body_start, name) in enumerate(starts):
        body_end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        mapping = {}
        pending = []
        expect_label = False
        for m in _TOKEN.finditer(text, body_start, body_end):
            quoted = m.group(1) if m.group(1) is not None else m.group(2)
            if m.group(3):
                expect_label = True
            elif m.group(4):
                break  # end of this VALUE statement
            elif quoted is not None:
                if expect_label:
                    for code in pending:
                        if code in mapping and mapping[code] != quoted:
                            raise ValueError(f"{name}: {code} mapped twice")
                        mapping[code] = quoted
                    pending = []
                    expect_label = False
                else:
                    pending.append(quoted.strip())
        if pending:
            raise ValueError(f"{name}: dangling codes without a label: {pending[:5]}")
        blocks[name] = mapping
    return blocks


def parse_array_literal(text: str, array_name: str) -> list:
    m = re.search(r"ARRAY\s+" + array_name + r"\s*\(\d+\)\s*\$\d+\s*[A-Z]\d+\s*-\s*[A-Z]\d+\s*\((.*?)\)\s*;",
                  text, re.IGNORECASE | re.DOTALL)
    if not m:
        raise ValueError(f"array {array_name} not found")
    return re.findall(r'"([^"]+)"', m.group(1))


def parse_labels(text: str) -> dict:
    # Measure labels are the single-quoted CMR_x = '...' pairs in the final LABEL statement.
    return dict(re.findall(r"CMR_(\w+)\s*=\s*'([^']*)'", text))


def parse_weights(text: str) -> tuple:
    weights = {"mortality": {}, "readmission": {}}
    for prefix, name in (("mw", "mortality"), ("rw", "readmission")):
        for m in re.finditer(r"^\s*" + prefix + r"([A-Z_]+)\s*=\s*(-?\d+)\s*;", text, re.MULTILINE):
            weights[name][m.group(1)] = int(m.group(2))
    order = re.search(r"array\s+cmvars\(&NUMcomorb_\)(.*?);", text, re.IGNORECASE | re.DOTALL)
    measures = [v[4:] for v in order.group(1).split()]
    return weights, measures


def build() -> dict:
    fmt_text = _read(SAS_DIR / FORMAT_PROGRAM)
    map_text = _read(SAS_DIR / MAPPING_PROGRAM)
    idx_text = _read(SAS_DIR / INDEX_PROGRAM)

    blocks = parse_value_blocks(fmt_text)
    comfmt = blocks.pop("COMFMT")
    exempt = {}
    for name, mapping in blocks.items():
        m = re.fullmatch(r"POAXMPT_V(\d+)FMT", name)
        if not m:
            raise ValueError(f"unexpected format {name}")
        if set(mapping.values()) != {"1"}:
            raise ValueError(f"{name}: unexpected labels {set(mapping.values())}")
        exempt[m.group(1)] = sorted(mapping)

    version = re.search(r'%LET\s+CMR_VERSION\s*=\s*"([^"]+)"', map_text).group(1)
    if version != CMR_VERSION:
        raise ValueError(f"mapping program is {version}, expected {CMR_VERSION}")

    valanypoa = parse_array_literal(map_text, "VALANYPOA")
    valpoa = parse_array_literal(map_text, "VALPOA")
    labels = parse_labels(map_text)
    weights, measures = parse_weights(idx_text)
    if len(measures) != 38 or set(weights["mortality"]) != set(measures) \
            or set(weights["readmission"]) != set(measures):
        raise ValueError("index program weights do not cover the 38 measures")

    poa_dependent = (set(valpoa) - {"CBVD_POA", "CBVD_SQLA"}) | {"CBVD"}
    return {
        "cmr_version": CMR_VERSION,
        "generated_by": "tools/build_data.py",
        "sources": {
            f: sha256(SAS_DIR / f) for f in (FORMAT_PROGRAM, MAPPING_PROGRAM, INDEX_PROGRAM)
        },
        "measures": [
            {"name": n, "label": labels[n], "poa_dependent": n in poa_dependent}
            for n in measures
        ],
        "valanypoa": valanypoa,
        "valpoa": valpoa,
        "weights": weights,
        "comfmt": dict(sorted(comfmt.items())),
        "exempt": dict(sorted(exempt.items(), key=lambda kv: int(kv[0]))),
    }


def serialize(data: dict) -> bytes:
    raw = json.dumps(data, sort_keys=False, separators=(",", ":")).encode("utf-8")
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0, compresslevel=9) as gz:
        gz.write(raw)
    return buf.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    fresh = build()
    if args.check:
        # Compare content, not gzip bytes: zlib builds may compress identical data differently.
        current = json.loads(gzip.decompress(OUT.read_bytes())) if OUT.exists() else {}
        if current != fresh:
            differing = sorted(k for k in set(current) | set(fresh) if current.get(k) != fresh.get(k))
            print(f"STALE: {OUT} does not match a fresh build from {SAS_DIR}; differing sections: {differing}")
            if "sources" in differing:
                print("  bundled source hashes:", current.get("sources"))
                print("  fresh source hashes:  ", fresh.get("sources"))
            return 1
        print("bundled data matches AHRQ SAS programs")
        return 0
    blob = serialize(fresh)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(blob)
    print(f"wrote {OUT} ({len(blob):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
