import pandas as pd

# Load the original Excel
df = pd.read_excel(r'C:\Users\FGOpe\elixhauser-ahrq\elixhauser_ahrq\data\CMR-Reference-File-v2026-1.xlsx', 
                   sheet_name='DX_to_Comorb_Mapping', 
                   skiprows=1)

# Rename problematic columns
df = df.rename(columns={
    'ICD-10-CM Diagnosis': 'icd10_code',
    'ICD-10-CM Code Description': 'code_description',
    '# Comorbidities': 'num_comorbidities'
})

# Make all column names lowercase for consistency
df.columns = [c.lower() for c in df.columns]

# Save to dbt project
df.to_csv(r'C:\Users\FGOpe\eocs-analytics\data\ahrq_elixhauser_dx_mapping.csv', index=False)
print(f'Saved {len(df)} rows with columns:')
print(list(df.columns))
