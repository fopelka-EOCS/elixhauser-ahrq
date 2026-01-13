from setuptools import setup, find_packages

setup(
    name="elixhauser-ahrq",
    version="0.1.0",
    author="Frank Opelka, MD",
    author_email="fopelka@eocs.ltd",
    description="Python implementation of AHRQ Elixhauser Comorbidity Index for ICD-10-CM",
    packages=find_packages(),
    package_data={
        'elixhauser_ahrq': ['data/*.xlsx'],
    },
    include_package_data=True,
    install_requires=[
        'pandas>=1.3.0',
        'numpy>=1.20.0',
        'openpyxl>=3.0.0',
    ],
    python_requires='>=3.8',
)
