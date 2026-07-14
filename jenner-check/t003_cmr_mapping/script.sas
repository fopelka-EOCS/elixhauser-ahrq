/******************************************************************/
/* Title:       ELIXHAUSER COMORBIDITY SOFTWARE REFINED           */
/*              FOR ICD-10-CM MAPPING PROGRAM                     */
/*                                                                */
/* Program:     CMR_Mapping_Program_v2026-1.SAS                   */
/*                                                                */
/* Description: This SAS mapping program assigns the Elixhauser   */
/*              comorbidity measures from ICD-10-CM secondary     */
/*              diagnoses. Some comorbidities require additional  */
/*              information on whether the diagnosis was present  */
/*              on admission (POA).                               */
/*                                                                */
/* Output:      This program appends the comorbidity measures     */
/*              to the input SAS file. The data elements start    */
/*              with the 4-character prefix CMR_                  */
/******************************************************************/

/**********************************************/
/*          SPECIFY FILE LOCATIONS            */
/**********************************************/
LIBNAME  IN1    (WORK);                               * Location of input discharge data;
LIBNAME  OUT1   (WORK);                               * Location of output data;


/*********************************************/
/*   SPECIFY INPUT FILE CHARACTERISTICS      */
/*********************************************/
* Diagnosis data element array prefix;                    %LET DXPREFIX=I10_DX;
* POA data element array prefix;                          %LET POAPREFIX=DXPOA;
* Maximum number of diagnosis codes on any record;        %LET NUMDX = 6;
* Variable that counts ICD-10-CM codes on a record;       %LET NDXVAR=I10_NDX;
* Indicators that diagnosis is present on admission;      %LET POA   = 1;
* Number of observations to use;                          %LET OBS    = MAX;

/**********************************************/
/*          SPECIFY FILE NAMES                */
/**********************************************/
* Input SAS file member name;                              %Let CORE = mock_core;
* Output SAS file member name;                             %Let OUT  = mock_mapped;


/*********************************************/
/*   SET CMR VERSION                         */
/*********************************************/
%LET CMR_VERSION = "2026.1" ;               *<=== DO NOT MODIFY;


TITLE1 'Elixhauser Comorbidity Software Refined for ICD-10-CM Diagnoses';
TITLE2 'Comorbidity Mapping Program';


%macro comorbidity;
DATA OUT1.&OUT.;
   LABEL  CMR_VERSION = "VERSION OF COMORBIDITY SOFTWARE REFINED";
   RETAIN CMR_VERSION &CMR_VERSION;

   SET IN1.&CORE ;

   DROP I J  DXVALUE A1-A20 %if &POA.=1 %then %do;B1-B19 K %end;  CMR_CBVD_SQLA CMR_CBVD_POA CMR_CBVD_NPOA ;

   /*****************************************/
   /*    Establish the ICD-10-CM Version    */
   /*****************************************/
   ATTRIB ICDVER LENGTH=3 LABEL='ICD-10-CM VERSION';

   ICDVER = 0;

   IF      (YEAR IN (2015) AND DQTR IN (4))     THEN ICDVER = 33;
   ELSE IF (YEAR IN (2016) AND DQTR IN (1,2,3)) THEN ICDVER = 33;
   ELSE IF (YEAR IN (2016) AND DQTR IN (4))     THEN ICDVER = 34;
   ELSE IF (YEAR IN (2017) AND DQTR IN (1,2,3)) THEN ICDVER = 34;
   ELSE IF (YEAR IN (2017) AND DQTR IN (4))     THEN ICDVER = 35;
   ELSE IF (YEAR IN (2018) AND DQTR IN (1,2,3)) THEN ICDVER = 35;
   ELSE IF (YEAR IN (2018) AND DQTR IN (4))     THEN ICDVER = 36;
   ELSE IF (YEAR IN (2019) AND DQTR IN (1,2,3)) THEN ICDVER = 36;
   ELSE IF (YEAR IN (2019) AND DQTR IN (4))     THEN ICDVER = 37;
   ELSE IF (YEAR IN (2020) AND DQTR IN (1,2,3)) THEN ICDVER = 37;
   ELSE IF (YEAR IN (2020) AND DQTR IN (4))     THEN ICDVER = 38;
   ELSE IF (YEAR IN (2021) AND DQTR IN (1,2,3)) THEN ICDVER = 38;
   ELSE IF (YEAR IN (2021) AND DQTR IN (4))     THEN ICDVER = 39;
   ELSE IF (YEAR IN (2022) AND DQTR IN (1,2,3)) THEN ICDVER = 39;
   ELSE IF (YEAR IN (2022) AND DQTR IN (4))     THEN ICDVER = 40;
   ELSE IF (YEAR IN (2023) AND DQTR IN (1,2,3)) THEN ICDVER = 40;
   ELSE IF (YEAR IN (2023) AND DQTR IN (4))     THEN ICDVER = 41;
   ELSE IF (YEAR IN (2024) AND DQTR IN (1,2,3)) THEN ICDVER = 41;
   ELSE IF (YEAR IN (2024) AND DQTR IN (4))     THEN ICDVER = 42;
   ELSE IF (YEAR IN (2025) AND DQTR IN (1,2,3)) THEN ICDVER = 42;
   ELSE IF (YEAR IN (2025) AND DQTR IN (4))     THEN ICDVER = 43;
   ELSE IF (YEAR IN (2026) AND DQTR IN (1,2,3)) THEN ICDVER = 43;
   ELSE                                              ICDVER = 43;

   /********************************************/
   /* Establish lengths for all comorbidity    */
   /* flags.                                   */
   /********************************************/
   LENGTH   DXVALUE $20

            CMR_AIDS         CMR_ALCOHOL     CMR_ANEMDEF      CMR_AUTOIMMUNE CMR_BLDLOSS   CMR_CANCER_LYMPH CMR_CANCER_LEUK  CMR_CANCER_METS CMR_CANCER_NSITU
            CMR_CANCER_SOLID CMR_CBVD_SQLA   CMR_CBVD_POA     CMR_CBVD_NPOA  CMR_CBVD      CMR_HF CMR_COAG  CMR_DEMENTIA     CMR_DEPRESS     CMR_DIAB_UNCX
            CMR_DIAB_CX      CMR_DRUG_ABUSE  CMR_HTN_CX       CMR_HTN_UNCX   CMR_LIVER_MLD CMR_LIVER_SEV    CMR_LUNG_CHRONIC CMR_NEURO_MOVT
            CMR_NEURO_OTH    CMR_NEURO_SEIZ  CMR_OBESE        CMR_PARALYSIS  CMR_PERIVASC  CMR_PSYCHOSES    CMR_PULMCIRC     CMR_RENLFL_MOD  CMR_RENLFL_SEV
            CMR_THYROID_HYPO CMR_THYROID_OTH CMR_ULCER_PEPTIC CMR_VALVE      CMR_WGHTLOSS  3.
            ;

   /********************************************/
   /* Create diagnosis and comorbidity arrays  */
   /********************************************/
   ARRAY DX        (&NUMDX) $  &DXPREFIX.1 - &DXPREFIX.&NUMDX;

   ARRAY COMANYPOA  (20) CMR_AIDS       CMR_ALCOHOL    CMR_AUTOIMMUNE   CMR_LUNG_CHRONIC CMR_DEMENTIA    CMR_DEPRESS      CMR_DIAB_UNCX   CMR_DIAB_CX
                         CMR_DRUG_ABUSE CMR_HTN_UNCX   CMR_HTN_CX       CMR_THYROID_HYPO CMR_THYROID_OTH CMR_CANCER_LYMPH CMR_CANCER_LEUK CMR_CANCER_METS
                         CMR_OBESE      CMR_PERIVASC   CMR_CANCER_SOLID CMR_CANCER_NSITU ;

   ARRAY COMPOA     (19) CMR_ANEMDEF      CMR_BLDLOSS   CMR_HF        CMR_COAG      CMR_LIVER_MLD CMR_LIVER_SEV  CMR_NEURO_MOVT
                         CMR_NEURO_SEIZ   CMR_NEURO_OTH CMR_PARALYSIS CMR_PSYCHOSES CMR_PULMCIRC  CMR_RENLFL_MOD CMR_RENLFL_SEV
                         CMR_ULCER_PEPTIC CMR_WGHTLOSS  CMR_CBVD_POA  CMR_CBVD_SQLA CMR_VALVE ;

   ARRAY VALANYPOA  (20) $13 A1-A20
                       ("AIDS"        "ALCOHOL"   "AUTOIMMUNE"  "LUNG_CHRONIC"  "DEMENTIA"      "DEPRESS"       "DIAB_UNCX"     "DIAB_CX"
                        "DRUG_ABUSE"  "HTN_UNCX"  "HTN_CX"      "THYROID_HYPO"  "THYROID_OTH"   "CANCER_LYMPH"  "CANCER_LEUK"
                        "CANCER_METS" "OBESE"     "PERIVASC"    "CANCER_SOLID"  "CANCER_NSITU"  );

   /****************************************************/
   /* If POA flags are available, create POA, exempt,  */
   /* and value arrays.                                */
   /****************************************************/
   %if &POA. = 1 %then %do;
   ARRAY EXEMPTPOA (&NUMDX)  EXEMPTPOA1 - EXEMPTPOA&NUMDX;

   ARRAY DXPOA     (&NUMDX) $  &POAPREFIX.1 - &POAPREFIX.&NUMDX;

   ARRAY VALPOA    (19) $13 B1-B19
                       ("ANEMDEF"     "BLDLOSS"      "HF"         "COAG"       "LIVER_MLD"  "LIVER_SEV"
                        "NEURO_MOVT"  "NEURO_SEIZ"   "NEURO_OTH"  "PARALYSIS"  "PSYCHOSES"  "PULMCIRC"   "RENLFL_MOD"
                        "RENLFL_SEV"  "ULCER_PEPTIC" "WGHTLOSS"   "CBVD_POA"   "CBVD_SQLA"  "VALVE");
   %end;

   /****************************************************/
   /* Initialize POA independent comorbidity flags     */
   /****************************************************/
   DO I = 1 TO 20;
      COMANYPOA(I) = 0;
   END;

   %if &POA. = 1 %then %do;
   DO I = 1 TO 19;
      COMPOA(I) = 0;
   END;
   CMR_CBVD_NPOA   = 0;
   CMR_CBVD        = 0;
   EXEMPTPOA1      = 0;
   %end;
   %else %do;
   CMR_CBVD_NPOA   = .;
   CMR_CBVD        = .;
   %end;

   /****************************************************/
   /* Examine each secondary diagnosis on a record     */
   /****************************************************/
   %if &NDXVAR ne %then %let MAXNDX = &NDXVAR;
   %else                %let MAXNDX = &NUMDX;

   DO I = 2 TO MIN(&MAXNDX,&NUMDX);
      IF DX(I) NE " " THEN DO;

         DXVALUE = PUT(DX(I),COMFMT.);

         /****************************************************/
         /*   Assign Comorbidities that are neutral to POA   */
         /****************************************************/
         DO J = 1 TO 20;
            IF DXVALUE = VALANYPOA(J)  THEN COMANYPOA(J) = 1;
         END;
         IF DXVALUE = "DRUG_ABUSEPSYCHOSES"  THEN CMR_DRUG_ABUSE= 1;
         IF DXVALUE = "HFHTN_CX"             THEN CMR_HTN_CX    = 1;
         IF DXVALUE = "HTN_CXRENLFL_SEV"     THEN CMR_HTN_CX    = 1;
         IF DXVALUE = "HFHTN_CXRENLFL_SEV"   THEN CMR_HTN_CX    = 1;
         IF DXVALUE = "ALCOHOLLIVER_MLD"     THEN CMR_ALCOHOL   = 1;
         IF DXVALUE = "VALVE_AUTOIMMUNE"     THEN CMR_AUTOIMMUNE= 1;

         %if &POA. = 1 %then %do;
         /****************************************************/
         /* Assign comorbidities requiring POA that are also */
         /* not exempt from POA reporting.                   */
         /****************************************************/
         EXEMPTPOA(I) = 0;
         IF (ICDVER = 43 AND PUT(DX(I),$poaxmpt_v43fmt.)='1') THEN EXEMPTPOA(I) = 1;

         /**** Flag record if diagnosis is POA exempt or requires POA and POA indicates present on admission (Y or W) ****/
         IF (EXEMPTPOA(I) = 1)  or (EXEMPTPOA(I) = 0 AND DXPOA(I) IN ("Y","W")) THEN DO;
            DO K = 1 TO 19;
               IF DXVALUE = VALPOA(K)  THEN COMPOA(K) = 1;
            END;
            IF DXVALUE = "DRUG_ABUSEPSYCHOSES" THEN CMR_PSYCHOSES  = 1;
            IF DXVALUE = "HFHTN_CX"            THEN CMR_HF         = 1;
            IF DXVALUE = "HTN_CXRENLFL_SEV"    THEN CMR_RENLFL_SEV = 1;
            IF DXVALUE = "HFHTN_CXRENLFL_SEV"  THEN DO;
               CMR_HF         = 1;
               CMR_RENLFL_SEV = 1;
            END;
            IF DXVALUE = "CBVD_SQLAPARALYSIS"  THEN DO;
               CMR_PARALYSIS = 1;
               CMR_CBVD_SQLA = 1;
            END;
            IF DXVALUE = "ALCOHOLLIVER_MLD"    THEN CMR_LIVER_MLD = 1;
            IF DXVALUE = "VALVE_AUTOIMMUNE"    THEN CMR_VALVE     = 1;
            IF DXVALUE = "LIVER_MLD_NEURO" THEN DO;
               CMR_LIVER_MLD = 1;
               CMR_NEURO_OTH = 1;
            END;
            IF DXVALUE = "NEURO_OTH_SEIZ"  THEN DO;
               CMR_NEURO_OTH  = 1;
               CMR_NEURO_SEIZ = 1;
            END;

            IF DXVALUE = "LIVER_MLD_PULMCIRC" THEN DO;
               CMR_LIVER_MLD  = 1;
               CMR_PULMCIRC   = 1;
            END;
		 END;
         /****************************************************/
         /* Assign comorbidities requiring that the          */
         /* diagnosis is not POA                             */
         /****************************************************/
         IF (EXEMPTPOA(I) = 0 AND DXPOA(I) IN ("N","U")) THEN DO;
            IF DXVALUE = "CBVD_POA"  THEN CMR_CBVD_NPOA = 1;
         END;
         %end;
      END;
   END;

   /****************************************************/
   /* Implement exclusions for comorbidities that are  */
   /* neutral to POA.                                  */
   /****************************************************/
   IF CMR_DIAB_CX      = 1 THEN CMR_DIAB_UNCX   = 0;
   IF CMR_HTN_CX       = 1 THEN CMR_HTN_UNCX    = 0;
   IF CMR_CANCER_METS  = 1 THEN DO;
      CMR_CANCER_SOLID = 0;
      CMR_CANCER_NSITU = 0;
   END;
   IF CMR_CANCER_SOLID = 1 THEN CMR_CANCER_NSITU = 0;

   /****************************************************/
   /* Exclusions for comorbidities requiring POA.      */
   /****************************************************/
   %if &POA. = 1 %then %do;
   IF CMR_LIVER_SEV    = 1 THEN CMR_LIVER_MLD   = 0;
   IF CMR_RENLFL_SEV   = 1 THEN CMR_RENLFL_MOD  = 0;
   IF (CMR_CBVD_POA=1) OR (CMR_CBVD_POA=0 AND CMR_CBVD_NPOA=0 AND CMR_CBVD_SQLA=1) THEN CMR_CBVD = 1;
   %end;

   LABEL
        CMR_AIDS         = 'Acquired immune deficiency syndrome'
        CMR_ALCOHOL      = 'Alcohol abuse'
        CMR_ANEMDEF      = 'Anemias due to other nutritional deficiencies'
        CMR_AUTOIMMUNE   = 'Autoimmune conditions'
        CMR_BLDLOSS      = 'Chronic blood loss anemia (iron deficiency)'
        CMR_CANCER_LEUK  = 'Leukemia'
        CMR_CANCER_LYMPH = 'Lymphoma'
        CMR_CANCER_METS  = 'Metastatic cancer'
        CMR_CANCER_NSITU = 'Solid tumor without metastasis, in situ'
        CMR_CANCER_SOLID = 'Solid tumor without metastasis, malignant'
        CMR_CBVD         = 'Cerebrovascular disease'
        CMR_CBVD_NPOA    = 'Cerebrovascular disease, not on admission'
        CMR_CBVD_POA     = 'Cerebrovascular disease, on admission'
        CMR_CBVD_SQLA    = 'Cerebrovascular disease, sequela'
        CMR_HF           = 'Heart failure'
        CMR_COAG         = 'Coagulopathy'
        CMR_DEMENTIA     = 'Dementia'
        CMR_DEPRESS      = 'Depression'
        CMR_DIAB_CX      = 'Diabetes with chronic complications'
        CMR_DIAB_UNCX    = 'Diabetes without chronic complications'
        CMR_DRUG_ABUSE   = 'Drug abuse'
        CMR_HTN_CX       = 'Hypertension, complicated'
        CMR_HTN_UNCX     = 'Hypertension, uncomplicated'
        CMR_LIVER_MLD    = 'Liver disease, mild'
        CMR_LIVER_SEV    = 'Liver disease, moderate to severe'
        CMR_LUNG_CHRONIC = 'Chronic pulmonary disease'
        CMR_NEURO_MOVT   = 'Neurological disorders affecting movement'
        CMR_NEURO_OTH    = 'Other neurological disorders'
        CMR_NEURO_SEIZ   = 'Seizures and epilepsy'
        CMR_OBESE        = 'Obesity'
        CMR_PARALYSIS    = 'Paralysis'
        CMR_PERIVASC     = 'Peripheral vascular disease'
        CMR_PSYCHOSES    = 'Psychoses'
        CMR_PULMCIRC     = 'Pulmonary circulation disease'
        CMR_RENLFL_MOD   = 'Renal failure, moderate'
        CMR_RENLFL_SEV   = 'Renal failure, severe'
        CMR_THYROID_HYPO = 'Hypothyroidism'
        CMR_THYROID_OTH  = 'Other thyroid disorders'
        CMR_ULCER_PEPTIC = 'Peptic ulcer disease x bleeding'
        CMR_VALVE        = 'Valvular disease'
        CMR_WGHTLOSS     = 'Weight loss'
        ;
RUN;
%mend comorbidity;
%comorbidity;


/***********************************/
/*  Means on comorbidity variables */
/***********************************/
PROC MEANS DATA=OUT1.&OUT.  N NMISS MEAN STD MIN MAX;
   VAR
      CMR_AIDS         CMR_ALCOHOL      CMR_ANEMDEF      CMR_AUTOIMMUNE  CMR_BLDLOSS      CMR_CANCER_LYMPH CMR_CANCER_LEUK
      CMR_CANCER_METS  CMR_CANCER_NSITU CMR_CANCER_SOLID CMR_CBVD        CMR_HF           CMR_COAG         CMR_DEMENTIA     CMR_DEPRESS
      CMR_DIAB_UNCX    CMR_DIAB_CX      CMR_DRUG_ABUSE   CMR_HTN_CX      CMR_HTN_UNCX     CMR_LIVER_MLD    CMR_LIVER_SEV    CMR_LUNG_CHRONIC
      CMR_NEURO_MOVT   CMR_NEURO_OTH    CMR_NEURO_SEIZ   CMR_OBESE       CMR_PARALYSIS    CMR_PERIVASC     CMR_PSYCHOSES    CMR_PULMCIRC
      CMR_RENLFL_MOD   CMR_RENLFL_SEV   CMR_THYROID_HYPO CMR_THYROID_OTH CMR_ULCER_PEPTIC CMR_VALVE        CMR_WGHTLOSS  ;
    TITLE3 'Means of Comorbidity Variables';
RUN;
