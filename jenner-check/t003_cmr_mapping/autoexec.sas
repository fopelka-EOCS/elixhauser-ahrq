options obs=100;   /* cap input rows for the captured run */

/*
  Bundle setup for CMR_Mapping_Program_v2026-1.sas.

  The mapping program looks each secondary ICD-10-CM diagnosis up in the
  $COMFMT format and, for POA-dependent categories, in $POAXMPT_V43FMT. Those
  formats are built by the (very large) upstream CMR_Format_Program. To run the
  mapping logic in isolation this autoexec builds a WORK format library holding
  a small verbatim excerpt of $COMFMT (real code -> category ranges copied from
  the upstream format program) plus a small $POAXMPT_V43FMT, then a synthetic
  discharge file whose diagnoses use those exact codes. No patient data is used.
*/

libname library (work);

proc format lib=library;
   /* Verbatim code -> category ranges excerpted from CMR_Format_Program_v2026-1.sas */
   value $COMFMT
      "B20", "E8814", "Z21"                         = "AIDS"
      "O99312", "O99313", "O99314", "O99315"        = "ALCOHOL"
      "F323", "F328", "F329", "F341"                = "DEPRESS"
      "Z6842", "Z6854", "Z6856"                     = "OBESE"
      "J679", "J684", "J701", "J703"                = "LUNG_CHRONIC"
      "E13649", "E1365", "E1369", "E138"            = "DIAB_CX"
      "O10013", "O10019", "O1002", "O1003"          = "HTN_UNCX"
      "C7B09", "C7B1", "C7B8", "C800"               = "CANCER_METS"
      "G3185", "G3186", "G3189", "G319"             = "DEMENTIA"
      other                                         = " "
   ;

   /* Small POA-exempt lookup for ICDVER=43 (codes -> '1'); real codes from the
      $POAXMPT_V43FMT block of the upstream format program. */
   value $POAXMPT_V43FMT
      'B900', 'B901', 'B902', 'I252'                = '1'
      other                                         = ' '
   ;
run;

data work.mock_core;
   length I10_DX1-I10_DX6 $8 DXPOA1-DXPOA6 $1;
   input YEAR DQTR I10_NDX
         I10_DX1 $ I10_DX2 $ I10_DX3 $ I10_DX4 $ I10_DX5 $ I10_DX6 $
         DXPOA1 $ DXPOA2 $ DXPOA3 $ DXPOA4 $ DXPOA5 $ DXPOA6 $;
datalines;
2026 1 4 A419 Z21 O99315 E138 . . Y Y Y Y . .
2026 1 3 J189 J703 F329 Z6856 . . Y Y Y Y . .
2026 1 5 I509 C800 G319 O1003 H409 . Y Y Y Y N .
2026 1 2 R079 B20 . . . . Y Y . . . .
2026 1 4 K219 E1369 F341 J684 . . Y N Y Y . .
2026 1 3 N179 O10013 C7B1 . . . Y Y N . . .
;
run;
