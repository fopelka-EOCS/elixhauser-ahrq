"""Independent reference implementation of AHRQ Elixhauser Comorbidity Software
Refined for ICD-10-CM, v2027.1, transliterated from the AHRQ SAS programs:

  CMR_Format_Program_v2027-1.sas   (PROC FORMAT: $COMFMT, $POAXMPT_V33FMT..V44FMT)
  CMR_Mapping_Program_v2027-1.sas  (DATA step, macro %comorbidity, lines 91-374)
  CMR_Index_Program_v2027-1.sas    (DATA step, lines 68-207)

Stdlib only.  Intended as a differential-test oracle.  See
SAS_REFERENCE_NOTES.md for every interpretation call.

SAS missing is represented as None.

CLI:
  python -I sas_reference.py <format.sas> <index.sas> <in.jsonl> <out.jsonl>
  python -I sas_reference.py <format.sas> <index.sas>          (self-check only)
"""

import json
import re
import sys

NUMDX = 40  # %LET NUMDX = 40;  (mapping line 61)

# ---------------------------------------------------------------------------
# Arrays from the mapping program, copied verbatim and in SAS order.
# ---------------------------------------------------------------------------

# LENGTH statement, mapping lines 142-146 (41 numeric vars, length 3)
LENGTH_VARS = """
CMR_AIDS CMR_ALCOHOL CMR_ANEMDEF CMR_AUTOIMMUNE CMR_BLDLOSS CMR_CANCER_LYMPH CMR_CANCER_LEUK CMR_CANCER_METS CMR_CANCER_NSITU
CMR_CANCER_SOLID CMR_CBVD_SQLA CMR_CBVD_POA CMR_CBVD_NPOA CMR_CBVD CMR_HF CMR_COAG CMR_DEMENTIA CMR_DEPRESS CMR_DIAB_UNCX
CMR_DIAB_CX CMR_DRUG CMR_HTN_CX CMR_HTN_UNCX CMR_LIVER_MLD CMR_LIVER_SEV CMR_LUNG_CHRONIC CMR_NEURO_MOVT
CMR_NEURO_OTH CMR_NEURO_SEIZ CMR_OBESE CMR_PARALYSIS CMR_PERIVASC CMR_PSYCHOSES CMR_PULMCIRC CMR_RENLFL_MOD CMR_RENLFL_SEV
CMR_THYROID_HYPO CMR_THYROID_OTH CMR_ULCER_PEPTIC CMR_VALVE CMR_WGHTLOSS
""".split()

# DROP statement, mapping line 98 (CMR_ intermediates only)
DROPPED = ("CMR_CBVD_SQLA", "CMR_CBVD_POA", "CMR_CBVD_NPOA")

FINAL_MEASURES = [v for v in LENGTH_VARS if v not in DROPPED]  # 38

# ARRAY COMANYPOA (20), mapping lines 155-157
COMANYPOA = """
CMR_AIDS CMR_ALCOHOL CMR_AUTOIMMUNE CMR_LUNG_CHRONIC CMR_DEMENTIA CMR_DEPRESS CMR_DIAB_UNCX CMR_DIAB_CX
CMR_DRUG CMR_HTN_UNCX CMR_HTN_CX CMR_THYROID_HYPO CMR_THYROID_OTH CMR_CANCER_LYMPH CMR_CANCER_LEUK CMR_CANCER_METS
CMR_OBESE CMR_PERIVASC CMR_CANCER_SOLID CMR_CANCER_NSITU
""".split()

# ARRAY COMPOA (19), mapping lines 159-161
COMPOA = """
CMR_ANEMDEF CMR_BLDLOSS CMR_HF CMR_COAG CMR_LIVER_MLD CMR_LIVER_SEV CMR_NEURO_MOVT
CMR_NEURO_SEIZ CMR_NEURO_OTH CMR_PARALYSIS CMR_PSYCHOSES CMR_PULMCIRC CMR_RENLFL_MOD CMR_RENLFL_SEV
CMR_ULCER_PEPTIC CMR_WGHTLOSS CMR_CBVD_POA CMR_CBVD_SQLA CMR_VALVE
""".split()

# ARRAY VALANYPOA (20) $13 A1-A20, mapping lines 163-166
VALANYPOA = ["AIDS", "ALCOHOL", "AUTOIMMUNE", "LUNG_CHRONIC", "DEMENTIA", "DEPRESS", "DIAB_UNCX", "DIAB_CX",
             "DRUG", "HTN_UNCX", "HTN_CX", "THYROID_HYPO", "THYROID_OTH", "CANCER_LYMPH", "CANCER_LEUK",
             "CANCER_METS", "OBESE", "PERIVASC", "CANCER_SOLID", "CANCER_NSITU"]

# ARRAY VALPOA (19) $13 B1-B19, mapping lines 177-180
VALPOA = ["ANEMDEF", "BLDLOSS", "HF", "COAG", "LIVER_MLD", "LIVER_SEV",
          "NEURO_MOVT", "NEURO_SEIZ", "NEURO_OTH", "PARALYSIS", "PSYCHOSES", "PULMCIRC", "RENLFL_MOD",
          "RENLFL_SEV", "ULCER_PEPTIC", "WGHTLOSS", "CBVD_POA", "CBVD_SQLA", "VALVE"]

assert len(LENGTH_VARS) == 41 and len(FINAL_MEASURES) == 38
assert len(COMANYPOA) == len(VALANYPOA) == 20
assert len(COMPOA) == len(VALPOA) == 19

# Labels referenced by a special IF statement anywhere in the DATA step
SPECIAL_NEUTRAL = {  # mapping lines 237-242
    "DRUGPSYCHOSES": ["CMR_DRUG"],
    "HFHTN_CX": ["CMR_HTN_CX"],
    "HTN_CXRENLFL_SEV": ["CMR_HTN_CX"],
    "HFHTN_CXRENLFL_SEV": ["CMR_HTN_CX"],
    "ALCOHOLLIVER_MLD": ["CMR_ALCOHOL"],
    "VALVE_AUTOIMMUNE": ["CMR_AUTOIMMUNE"],
}
SPECIAL_POA = {  # mapping lines 269-294
    "DRUGPSYCHOSES": ["CMR_PSYCHOSES"],
    "HFHTN_CX": ["CMR_HF"],
    "HTN_CXRENLFL_SEV": ["CMR_RENLFL_SEV"],
    "HFHTN_CXRENLFL_SEV": ["CMR_HF", "CMR_RENLFL_SEV"],
    "CBVD_SQLAPARALYSIS": ["CMR_PARALYSIS", "CMR_CBVD_SQLA"],
    "ALCOHOLLIVER_MLD": ["CMR_LIVER_MLD"],
    "VALVE_AUTOIMMUNE": ["CMR_VALVE"],
    "LIVER_MLD_NEURO": ["CMR_LIVER_MLD", "CMR_NEURO_OTH"],
    "NEURO_OTH_SEIZ": ["CMR_NEURO_OTH", "CMR_NEURO_SEIZ"],
    "LIVER_MLD_PULMCIRC": ["CMR_LIVER_MLD", "CMR_PULMCIRC"],
}

EXEMPT_VERSIONS = list(range(33, 45))  # $POAXMPT_V33FMT .. $POAXMPT_V44FMT


# ---------------------------------------------------------------------------
# SAS character semantics
# ---------------------------------------------------------------------------

def _sas_str(v):
    """A SAS character value: missing (None) is all blanks.  SAS character
    comparison pads the shorter operand with blanks, so trailing blanks are
    insignificant; we canonicalise by stripping trailing ASCII spaces ONLY.
    Leading blanks, tabs, case, etc. are significant (no normalisation)."""
    if v is None:
        return ""
    return str(v).rstrip(" ")


def _sas_eq(a, b):
    return _sas_str(a) == _sas_str(b)


# ---------------------------------------------------------------------------
# PROC FORMAT parser
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"""\s*(?:
        (?P<dq>"(?:[^"]|"")*")
      | (?P<sq>'(?:[^']|'')*')
      | (?P<punct>[,=;\-])
      | (?P<word>[A-Za-z_$&][A-Za-z0-9_$.&]*)
    )""", re.X)


def _strip_comments(text):
    # /* ... */ comments (SAS block comments do not nest)
    return re.sub(r"/\*.*?\*/", " ", text, flags=re.S)


def _tokenize(text):
    pos, n = 0, len(text)
    out = []
    while True:
        while pos < n and text[pos].isspace():
            pos += 1
        if pos >= n:
            break
        m = _TOKEN_RE.match(text, pos)
        if not m or m.end() == pos:
            raise ValueError("Unexpected text in format program near: %r" % text[pos:pos + 60])
        pos = m.end()
        if m.group("dq") is not None:
            out.append(("str", m.group("dq")[1:-1].replace('""', '"')))
        elif m.group("sq") is not None:
            out.append(("str", m.group("sq")[1:-1].replace("''", "'")))
        elif m.group("punct") is not None:
            out.append((m.group("punct"), m.group("punct")))
        else:
            out.append(("word", m.group("word")))
    return out


def parse_format_program(text):
    """Return {FORMATNAME_UPPER: {"map": {value: label}, "other": label,
    "duplicates": [...]}} for every VALUE statement."""
    text = text.lstrip("﻿")
    text = _strip_comments(text)
    # Skip everything up to and including the PROC FORMAT statement.
    m = re.search(r"\bproc\s+format\b[^;]*;", text, flags=re.I)
    if not m:
        raise ValueError("PROC FORMAT statement not found")
    toks = _tokenize(text[m.end():])
    formats = {}
    i = 0
    while i < len(toks):
        kind, val = toks[i]
        if kind == "word" and val.lower() == "run":
            break
        if not (kind == "word" and val.lower() == "value"):
            raise ValueError("Expected VALUE, got %r" % (val,))
        name = toks[i + 1][1].upper()
        i += 2
        fmap, other, dups = {}, None, []
        while toks[i][0] != ";":
            # One range-list: values separated by commas, then '=' label.
            if toks[i][0] == "word" and toks[i][1].lower() == "other":
                if toks[i + 1][0] != "=" or toks[i + 2][0] != "str":
                    raise ValueError("Bad OTHER clause in %s" % name)
                other = toks[i + 2][1]
                i += 3
                continue
            values = []
            while True:
                if toks[i][0] != "str":
                    raise ValueError("Expected quoted value in %s, got %r" % (name, toks[i]))
                if toks[i + 1][0] == "-":
                    raise ValueError("Range syntax encountered in %s (not supported)" % name)
                values.append(toks[i][1])
                i += 1
                if toks[i][0] == ",":
                    i += 1
                    continue
                if toks[i][0] == "=":
                    i += 1
                    break
                raise ValueError("Expected ',' or '=' in %s, got %r" % (name, toks[i]))
            if toks[i][0] != "str":
                raise ValueError("Expected label in %s" % name)
            label = toks[i][1]
            i += 1
            for v in values:
                key = _sas_str(v)
                if key in fmap:
                    dups.append((key, fmap[key], label))
                fmap[key] = label
        i += 1  # the ';'
        formats[name] = {"map": fmap, "other": other, "duplicates": dups}
    return formats


def parse_index_program(text):
    """Return dict with readmission / mortality weights {CMR_x: int} paired
    positionally through the SAS arrays, plus the raw arrays."""
    text = _strip_comments(text)
    assigns = {}
    for m in re.finditer(r"^\s*((?:rw|mw)\w+)\s*=\s*(-?\d+(?:\.\d+)?)\s*;", text, flags=re.M | re.I):
        assigns[m.group(1).lower()] = float(m.group(2)) if "." in m.group(2) else int(m.group(2))
    arrays = {}
    for m in re.finditer(r"\barray\s+(\w+)\s*\(\s*[^)]*\)\s*([^;]*);", text, flags=re.I):
        arrays[m.group(1).lower()] = m.group(2).split()
    cmvars = arrays["cmvars"]
    rw = [assigns.get(n.lower()) for n in arrays["rwcms"]]
    mw = [assigns.get(n.lower()) for n in arrays["mwcms"]]
    if not (len(cmvars) == len(rw) == len(mw) == len(arrays["ricms"]) == len(arrays["micms"])):
        raise ValueError("Index program array lengths differ")
    return {
        "cmvars": cmvars,
        "readmission": dict(zip(cmvars, rw)),
        "mortality": dict(zip(cmvars, mw)),
        "arrays": arrays,
        "assignments": assigns,
    }


class Formats:
    def __init__(self, formats):
        self.raw = formats
        c = formats["$COMFMT"]
        self.comfmt = c["map"]
        self.comfmt_other = c["other"]
        self.exempt = {}
        self.exempt_other = {}
        for v in EXEMPT_VERSIONS:
            f = formats["$POAXMPT_V%dFMT" % v]
            self.exempt[v] = f["map"]
            self.exempt_other[v] = f["other"]

    def put_comfmt(self, code):
        """PUT(DX(I),COMFMT.) assigned into DXVALUE $20."""
        lab = self.comfmt.get(_sas_str(code), self.comfmt_other)
        return lab[:20]

    def put_exempt(self, version, code):
        return self.exempt[version].get(_sas_str(code), self.exempt_other[version])

    def exempt_sets(self):
        return {v: {k for k, lab in m.items() if _sas_eq(lab, "1")} for v, m in self.exempt.items()}


def load(format_program_path, index_program_path):
    with open(format_program_path, "r", encoding="utf-8-sig", errors="strict") as fh:
        fmts = Formats(parse_format_program(fh.read()))
    with open(index_program_path, "r", encoding="utf-8-sig", errors="strict") as fh:
        weights = parse_index_program(fh.read())
    return fmts, weights


# ---------------------------------------------------------------------------
# Mapping program DATA step (one observation)
# ---------------------------------------------------------------------------

def _icdver(year, dqtr):
    # mapping lines 108-134.  Missing YEAR/DQTR fail every IN test -> ELSE.
    icdver = 0
    table = [
        (2015, (4,), 33), (2016, (1, 2, 3), 33), (2016, (4,), 34), (2017, (1, 2, 3), 34),
        (2017, (4,), 35), (2018, (1, 2, 3), 35), (2018, (4,), 36), (2019, (1, 2, 3), 36),
        (2019, (4,), 37), (2020, (1, 2, 3), 37), (2020, (4,), 38), (2021, (1, 2, 3), 38),
        (2021, (4,), 39), (2022, (1, 2, 3), 39), (2022, (4,), 40), (2023, (1, 2, 3), 40),
        (2023, (4,), 41), (2024, (1, 2, 3), 41), (2024, (4,), 42), (2025, (1, 2, 3), 42),
        (2025, (4,), 43), (2026, (1, 2, 3), 43), (2026, (4,), 44), (2027, (1, 2, 3), 44),
    ]
    for y, qs, v in table:
        if year is not None and dqtr is not None and year == y and dqtr in qs:
            icdver = v
            break
    else:
        icdver = 44
    return icdver


def assign(record, fmt):
    """Run the %comorbidity DATA step for one observation.

    record keys: year, dqtr, dx (list; dx[0] = I10_DX1), poa (list or None),
    poa_available (bool -> &POA), ndx (I10_NDX or None).
    Returns {CMR_<38 measures>: 0/1/None, "ICDVER": int}.
    """
    poa_flag = 1 if record.get("poa_available") else 0
    year = record.get("year")
    dqtr = record.get("dqtr")
    dxlist = list(record.get("dx") or [])[:NUMDX]
    poalist = list(record.get("poa") or [])[:NUMDX]
    ndx = record.get("ndx")

    # ARRAY DX(40): positions beyond the supplied list are blank.
    DX = [None] + [dxlist[k] if k < len(dxlist) else None for k in range(NUMDX)]
    DXPOA = [None] + [poalist[k] if k < len(poalist) else None for k in range(NUMDX)]

    v = {name: None for name in LENGTH_VARS}  # all numeric vars start missing

    ICDVER = _icdver(year, dqtr)

    for j in range(20):                       # lines 187-189
        v[COMANYPOA[j]] = 0
    EXEMPTPOA = [None] * (NUMDX + 1)
    if poa_flag == 1:                         # lines 197-204
        for k in range(19):
            v[COMPOA[k]] = 0
        v["CMR_CBVD_NPOA"] = 0
        v["CMR_CBVD"] = 0
        EXEMPTPOA[1] = 0
    else:                                     # lines 205-208
        v["CMR_CBVD_NPOA"] = None
        v["CMR_CBVD"] = None

    # DO I = 2 TO MIN(&MAXNDX,&NUMDX)   (lines 223-226)
    # &NDXVAR = I10_NDX; SAS MIN() ignores missing, so missing I10_NDX -> 40.
    if ndx is None:
        upper = NUMDX
    else:
        upper = min(ndx, NUMDX)
    i = 2
    while i <= upper:
        if not _sas_eq(DX[i], " "):           # line 227
            DXVALUE = fmt.put_comfmt(DX[i])   # line 229
            for j in range(20):               # lines 234-236
                if _sas_eq(DXVALUE, VALANYPOA[j]):
                    v[COMANYPOA[j]] = 1
            for lab, targets in SPECIAL_NEUTRAL.items():   # lines 237-242
                if _sas_eq(DXVALUE, lab):
                    for t in targets:
                        v[t] = 1

            if poa_flag == 1:
                EXEMPTPOA[i] = 0              # line 250
                # lines 251-262: only the clause whose ICDVER matches can be true;
                # ICDVER is always one of 33..44 after lines 108-134.
                if ICDVER in fmt.exempt and _sas_eq(fmt.put_exempt(ICDVER, DX[i]), "1"):
                    EXEMPTPOA[i] = 1
                p = _sas_str(DXPOA[i])
                if EXEMPTPOA[i] == 1 or (EXEMPTPOA[i] == 0 and p in ("Y", "W")):   # line 265
                    for k in range(19):       # lines 266-268
                        if _sas_eq(DXVALUE, VALPOA[k]):
                            v[COMPOA[k]] = 1
                    for lab, targets in SPECIAL_POA.items():   # lines 269-294
                        if _sas_eq(DXVALUE, lab):
                            for t in targets:
                                v[t] = 1
                if EXEMPTPOA[i] == 0 and p in ("N", "U"):      # line 300
                    if _sas_eq(DXVALUE, "CBVD_POA"):
                        v["CMR_CBVD_NPOA"] = 1
        i += 1

    # Exclusions, POA-neutral (lines 311-317)
    if v["CMR_DIAB_CX"] == 1:
        v["CMR_DIAB_UNCX"] = 0
    if v["CMR_HTN_CX"] == 1:
        v["CMR_HTN_UNCX"] = 0
    if v["CMR_CANCER_METS"] == 1:
        v["CMR_CANCER_SOLID"] = 0
        v["CMR_CANCER_NSITU"] = 0
    if v["CMR_CANCER_SOLID"] == 1:
        v["CMR_CANCER_NSITU"] = 0

    # Exclusions requiring POA (lines 323-327)
    if poa_flag == 1:
        if v["CMR_LIVER_SEV"] == 1:
            v["CMR_LIVER_MLD"] = 0
        if v["CMR_RENLFL_SEV"] == 1:
            v["CMR_RENLFL_MOD"] = 0
        if (v["CMR_CBVD_POA"] == 1) or (v["CMR_CBVD_POA"] == 0 and v["CMR_CBVD_NPOA"] == 0
                                         and v["CMR_CBVD_SQLA"] == 1):
            v["CMR_CBVD"] = 1

    out = {name: v[name] for name in FINAL_MEASURES}
    out["ICDVER"] = ICDVER
    return out


# ---------------------------------------------------------------------------
# Index program DATA step
# ---------------------------------------------------------------------------

def _sas_mul(a, b):
    if a is None or b is None:
        return None
    return a * b


def _sas_sum_of(values):
    """SUM(OF ...): ignores missing; missing only if every argument missing."""
    vals = [x for x in values if x is not None]
    if not vals:
        return None
    return sum(vals)


def index(flags, weights):
    """Return (CMR_Index_Readmission, CMR_Index_Mortality).  Missing -> None.
    A flag absent from `flags` is treated as SAS missing."""
    cmvars = weights["cmvars"]
    ri = [_sas_mul(flags.get(c), weights["readmission"][c]) for c in cmvars]   # line 198
    mi = [_sas_mul(flags.get(c), weights["mortality"][c]) for c in cmvars]     # line 199
    return _sas_sum_of(ri), _sas_sum_of(mi)                                   # lines 202-203


# ---------------------------------------------------------------------------
# Self-check / CLI
# ---------------------------------------------------------------------------

def self_check(fmt, weights, stream=sys.stdout):
    w = stream.write
    w("COMFMT codes: %d (OTHER label %r)\n" % (len(fmt.comfmt), fmt.comfmt_other))
    labels = {}
    for lab in fmt.comfmt.values():
        labels[lab] = labels.get(lab, 0) + 1
    w("COMFMT distinct labels: %d\n" % len(labels))
    handled = set(VALANYPOA) | set(VALPOA) | set(SPECIAL_NEUTRAL) | set(SPECIAL_POA)
    for lab in sorted(labels):
        w("  %-22s %5d%s\n" % (lab, labels[lab], "" if lab in handled else "   <-- NOT REFERENCED BY MAPPING PROGRAM"))
    w("COMFMT duplicate keys: %d\n" % len(fmt.raw["$COMFMT"]["duplicates"]))
    w("Max COMFMT label length: %d\n" % max(len(l) for l in labels))
    sets = fmt.exempt_sets()
    for v in EXEMPT_VERSIONS:
        nonone = sum(1 for lab in fmt.exempt[v].values() if not _sas_eq(lab, "1"))
        w("POAXMPT_V%dFMT: %d exempt codes (non-'1' labels: %d, duplicates: %d, OTHER %r)\n"
          % (v, len(sets[v]), nonone, len(fmt.raw["$POAXMPT_V%dFMT" % v]["duplicates"]), fmt.exempt_other[v]))
    w("Weights (readmission, mortality) in index-array order:\n")
    for c in weights["cmvars"]:
        w("  %-18s rw=%4s  mw=%4s\n" % (c, weights["readmission"][c], weights["mortality"][c]))
    # positional alignment check of index arrays
    a = weights["arrays"]
    for arr, pre in (("rwcms", "rw"), ("mwcms", "mw"), ("ricms", "ri"), ("micms", "mi")):
        for c, n in zip(weights["cmvars"], a[arr]):
            if n.lower() != (pre + c[4:]).lower():
                w("  NOTE: array %s element %r is positionally paired with %s\n" % (arr, n, c))
    missing = set(weights["cmvars"]) ^ set(FINAL_MEASURES)
    w("Index cmvars vs mapping final measures symmetric difference: %s\n" % (sorted(missing) or "none"))


def main(argv):
    if len(argv) not in (3, 5):
        sys.stderr.write(__doc__)
        return 2
    fmt, weights = load(argv[1], argv[2])
    if len(argv) == 3:
        self_check(fmt, weights)
        return 0
    with open(argv[3], "r", encoding="utf-8") as fin, open(argv[4], "w", encoding="utf-8", newline="\n") as fout:
        for line in fin:
            if not line.strip():
                continue
            rec = json.loads(line)
            res = assign(rec, fmt)
            icdver = res.pop("ICDVER")
            r, m = index(res, weights)
            fout.write(json.dumps({"id": rec.get("id"), "ICDVER": icdver, "flags": res,
                                   "CMR_Index_Mortality": m, "CMR_Index_Readmission": r}) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
