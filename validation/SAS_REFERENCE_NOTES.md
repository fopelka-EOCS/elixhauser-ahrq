# sas_reference.py — interpretation notes

Independent transliteration of AHRQ CMR v2027.1 SAS. Sources read: `CMR_Mapping_Program_v2027-1.sas` (all 395 lines), `CMR_Index_Program_v2027-1.sas` (all 221 lines), `CMR_Format_Program_v2027-1.sas` (the header, every VALUE boundary, then parsed in full by a strict tokenizer that raises an error on anything unexpected). Line numbers below are "M" for mapping, "I" for index and "F" for format. Python `None` stands for SAS missing.

## Format program parsing
- F27 `Proc format lib=library;`. There are 13 VALUE statements: `$COMFMT` (F28–F4656) and `$POAXMPT_V33FMT`…`$POAXMPT_V44FMT` (F4658–F452942), ending with `run;` at F452944. A UTF-8 BOM opens the file.
- Quoting is mixed. V33–V42 use `"…"`, V43 uses `'…'` throughout with `other = ' '` (F414539), and V44 uses `'…'` codes with `="1"` and `other=" "`. Doubled-quote escapes are handled (none occur).
- There are no ranges (`-`), no NOTSORTED/MULTILABEL options and no duplicate keys in any block. SAS would reject an overlapping VALUE, so the parser reports duplicates if any appear. Every key matches `[A-Z0-9]{3,7}`.
- Each block ends with `other = " "`, so an unlisted code yields a blank label. Every POAXMPT label is `"1"`.
- Counts: COMFMT has 4,573 codes and 49 distinct labels. Exempt codes by version: V33 35,239; V34 36,875; V35 36,877; V36 36,935; V37 37,075; V38 37,258; V39 37,297; V40 37,658; V41 38,110; V42 38,159; V43 38,349; V44 38,399.
- Format lookup is exact and case-sensitive. Trailing blanks are ignored and leading blanks are significant. There is no UPCASE or decimal stripping. Header M9–M10 requires codes without decimals.

## Labels
- All 49 COMFMT labels are consumed by the mapping program: 20 in VALANYPOA, 19 in VALPOA (M177–180), and 10 combination labels (M237–242, M269–294). No label is orphaned. Had one existed, SAS would silently set nothing.
- Combination labels behave asymmetrically:
  - `DRUGPSYCHOSES`, `HFHTN_CX`, `HTN_CXRENLFL_SEV`, `HFHTN_CXRENLFL_SEV`, `ALCOHOLLIVER_MLD` and `VALVE_AUTOIMMUNE` set their POA-neutral half regardless of POA. Their POA half sets only inside the M265 branch.
  - `CBVD_SQLAPARALYSIS`, `LIVER_MLD_NEURO`, `NEURO_OTH_SEIZ` and `LIVER_MLD_PULMCIRC` act only in the POA branch. With &POA=0 they contribute nothing.
- DXVALUE is `$20` (M140). The longest label has 18 characters, so nothing is truncated. VALANYPOA/VALPOA are `$13` (M163, M177), and every element fits.
- Array alignment was checked position by position: COMANYPOA↔VALANYPOA (M155–166) and COMPOA↔VALPOA (M159–161 vs M177–180).

## DATA step semantics
- **ICDVER (M108–134).** The ELSE branch sets 44 for any YEAR/DQTR outside 2015Q4–2027Q3. That includes missing YEAR or DQTR, pre-2015Q4 (ICD-9 era) dates, 2027Q4 and later, and invalid quarters. Every record therefore gets an exemption list, and a missing date silently uses the newest list. The `ICDVER = 0` on M108 is always overwritten. ICDVER is computed even when &POA=0, but it is used only at M251–262.
- **Loop bound (M223–226).** With `NDXVAR=I10_NDX` the loop is `DO I=2 TO MIN(I10_NDX,40)`. SAS `MIN` ignores missing values, so a missing I10_NDX gives 40, the same result as a blank NDXVAR. I10_NDX below 2 means no iterations. A non-integer bound behaves like its floor. Codes beyond I10_NDX are ignored, and DX positions past the supplied list are blank. DX1 is never examined.
- **Blank test (M227).** `DX(I) NE " "` is false for an empty or all-space value. Tabs and other characters count as non-blank.
- **POA comparisons (M265, M300).** `DXPOA(I) IN ("Y","W")` and `IN ("N","U")` compare exactly, case-sensitively, with trailing blanks ignored. `"y"` and `"n"` match neither test. A missing or blank POA matches neither: a non-exempt code then gets no POA-requiring flag and no NPOA. `poa_available=true` with `poa=null` is treated as all-blank DXPOA.
- **Exemption (M250–262).** Only the clause for the record's ICDVER can fire. An exempt code bypasses the POA check and can never set CMR_CBVD_NPOA (M300 requires `EXEMPTPOA(I)=0`).
- **&POA=0 (M205–208).** The COMPOA variables are declared by LENGTH and ARRAY but never assigned, so 17 final flags plus CMR_CBVD stay missing (18 `None`s). The POA-neutral flags and the M311–317 exclusions still apply. The M324–326 exclusions are skipped.
- **CBVD (M326).** `CBVD_POA=1`, or `CBVD_POA=0 AND NPOA=0 AND SQLA=1`. A POA-present CBVD code wins even when another CBVD_POA code on the same record is N/U, because NPOA only blocks the sequela path. CMR_CBVD_SQLA, CMR_CBVD_POA and CMR_CBVD_NPOA are dropped (M98).
- Exclusions run in order (M311–317), after the loop. Flags are never reset to 0 except by these exclusions.
- I did not model length truncation of input variables (for example a `$1` DXPOA turning "YES" into "Y", or `$7` DX). The values are used as given.
- EXEMPTPOA1–40 are not in the DROP list (M98), so they leak into SAS output. This does not affect the measures. `EXEMPTPOA1 = 0` (M203) has no effect because the loop starts at 2.

## Index program
- I compute `ri=cm*rw` (I198), with a missing flag giving a missing product. `SUM(OF ri[*])` ignores missing products and returns missing only if all 38 are missing. That never happens, because the POA-neutral flags are always 0/1.
- With &POA=0 the index is therefore the sum of the POA-neutral terms only, not missing. That contradicts the header assumption (I13–17, I52–54) that flags were assigned using POA.
- Weights are paired positionally through the arrays (I166–193), and names were checked against cmvars.
- **`miPEmiVASC` (I192).** This looks like a typo for `miPERIVASC`, but it is just a variable name in position 29 of `micms`, which pairs with CMR_PERIVASC × mwPERIVASC. `SUM(OF micms[*])` covers all elements and `drop mi:` (I206) removes it, so it has no effect on the result.
- `LENGTH … 3` (I72) stores integers exactly up to 8,192, which is far above the reachable index range.
