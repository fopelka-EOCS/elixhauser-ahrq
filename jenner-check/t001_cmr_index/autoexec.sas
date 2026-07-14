options obs=100;   /* cap input rows for the captured run */

/*
  Bundle setup for CMR_Index_Program_v2026-1.sas.

  The upstream index program reads a discharge file (IN1.&CORE) that already
  carries the 38 present-on-admission comorbidity flags (prefix CMR_) produced
  by the mapping program. To exercise the index arithmetic in isolation, this
  autoexec builds a small synthetic cohort of those 38 flags in WORK, and the
  script's LIBNAMEs are redirected to WORK. No patient data is used.
*/

data work.mock_core;
   input
      CMR_AIDS CMR_ALCOHOL CMR_ANEMDEF CMR_AUTOIMMUNE CMR_BLDLOSS
      CMR_CANCER_LEUK CMR_CANCER_LYMPH CMR_CANCER_METS CMR_CANCER_NSITU
      CMR_CANCER_SOLID CMR_CBVD CMR_HF CMR_COAG CMR_DEMENTIA CMR_DEPRESS
      CMR_DIAB_CX CMR_DIAB_UNCX CMR_DRUG_ABUSE CMR_HTN_CX CMR_HTN_UNCX
      CMR_LIVER_MLD CMR_LIVER_SEV CMR_LUNG_CHRONIC CMR_NEURO_MOVT
      CMR_NEURO_OTH CMR_NEURO_SEIZ CMR_OBESE CMR_PARALYSIS CMR_PERIVASC
      CMR_PSYCHOSES CMR_PULMCIRC CMR_RENLFL_MOD CMR_RENLFL_SEV
      CMR_THYROID_HYPO CMR_THYROID_OTH CMR_ULCER_PEPTIC CMR_VALVE CMR_WGHTLOSS
   ;
datalines;
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
0 1 0 0 0 0 0 0 0 0 0 1 0 0 0 0 1 0 0 1 0 0 1 0 0 0 1 0 0 0 0 0 0 0 0 0 0 0
0 0 1 0 0 0 0 1 0 0 0 1 1 0 0 1 0 0 1 0 0 1 0 0 0 0 0 0 0 0 1 0 1 0 0 0 0 1
1 0 0 1 0 0 1 0 0 0 0 0 0 0 1 0 1 0 0 0 0 0 0 0 1 0 0 0 0 0 0 0 0 1 0 0 0 0
0 0 0 0 1 1 0 0 0 1 1 1 0 1 0 0 0 0 0 0 1 0 1 0 0 1 0 1 1 0 0 1 0 0 0 1 0 0
0 1 0 0 0 0 0 0 1 0 0 0 0 0 1 0 0 1 0 1 0 0 0 0 0 0 1 0 0 1 0 0 0 0 0 0 0 1
0 0 1 0 0 0 0 1 0 0 1 1 0 0 0 1 0 0 1 0 0 0 1 0 1 0 0 0 1 0 0 0 1 0 0 0 0 0
0 0 0 0 0 0 0 0 0 1 0 1 1 1 0 0 1 0 0 0 0 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 1
;
run;
