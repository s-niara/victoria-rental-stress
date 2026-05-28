# Victoria Rental Stress Forecasting

Forecasting rental stress across Victorian Local Government Areas using historical rental and income data.

**Status:** 🚧 Phase 1 complete (data pipeline + EDA) · Phase 2 in progress (feature engineering)

## What this project does

This project builds an end-to-end data pipeline and machine learning system to answer one question:

> Where in Victoria is rental stress likely to worsen most over the next 12 months, and which Local Government Areas show the most concerning trends?

It combines 26 years of quarterly rental data from the Victorian Department of Families, Fairness and Housing (DFFH) with Australian Bureau of Statistics (ABS) income and demographic data, builds a multi-horizon forecasting model, and exposes the results through an interactive dashboard.

## Tech stack

- **Language:** Python 3.11+
- **Data:** pandas, geopandas, pyarrow
- **Modelling:** scikit-learn, statsmodels, Prophet, XGBoost
- **Experiment tracking:** MLflow
- **API:** FastAPI
- **Dashboard:** Streamlit with interactive choropleth maps
- **CI/CD:** GitHub Actions
- **Deployment:** Google Cloud Run (containerised)

## Data sources

All data is from public Australian government sources:

- **DFFH Victorian Rental Report** — quarterly median rents by LGA, June 1999 to present (79 LGAs × 6 property types)
- **DFFH Affordable Lettings** — quarterly share of new rentals affordable to income-support recipients, by LGA
- **ABS Census 2021 (G33)** — household income distribution by LGA, used to derive median and lower-quartile (p25) household income
- **ABS ASGS Edition 3 (2021)** — LGA boundary polygons for mapping

See `methodology.md` for detailed documentation of sources, definitions, and analytical decisions — including why Census household income was chosen over the ABS Personal Income series.

## Key findings so far

From the exploratory analysis (`notebooks/01_eda.ipynb`):

- The median Victorian LGA went from **75% of new rentals affordable** to income-support recipients in 2000 to just **27% by 2025**.
- Using lower-quartile household income, **every Victorian LGA now exceeds the 30% rental stress threshold** for a 2-bed flat, and two-thirds exceed 50% (severe stress).
- Post-COVID rent growth has shifted strongly toward regional LGAs — the fastest-rising over the last five years include Wodonga, Campaspe, and Greater Shepparton.

## Project status

| Phase | Status |
|-------|--------|
| 0 — Project scoping | ✅ Complete |
| 1 — Data acquisition and EDA | ✅ Complete |
| 2 — Feature engineering and rental stress definition | 🚧 In progress |
| 3 — Modelling | ⬜ Pending |
| 4 — API and dashboard | ⬜ Pending |
| 5 — Production deployment | ⬜ Pending |
| 6 — Documentation and polish | ⬜ Pending |

## Local setup

```bash
# Clone
git clone https://github.com/s-niara/victoria-rental-stress.git
cd victoria-rental-stress

# Create environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

Raw source files are not committed (they are large and publicly available). Download them from the
[DFFH Rental Report](https://www.dffh.vic.gov.au/publications/rental-report) and
[Digital Atlas of Australia](https://digital.atlas.gov.au/) and place them in `data/raw/`, then run the
ingestion scripts:

```bash
python scripts/ingest_dffh_history.py         # quarterly median rents by LGA
python scripts/ingest_dffh_affordability.py   # affordable lettings by LGA
python scripts/ingest_abs_income.py           # ABS Census G33 household income
python scripts/ingest_lga_boundaries.py       # ABS LGA boundary polygons
```

See `methodology.md` for the exact source files required.

## Repository structure

```
victoria-rental-stress/
├── data/                    # Raw and processed datasets (gitignored; data/reference committed)
├── notebooks/               # Exploratory analysis
├── src/                     # Production code
│   ├── ingestion/           # Parse DFFH and ABS data
│   ├── features/            # Feature engineering
│   ├── models/              # Training and forecasting
│   ├── api/                 # FastAPI backend
│   └── dashboard/           # Streamlit app
├── tests/                   # pytest suite
├── scripts/                 # Orchestration entry points
├── methodology.md           # Analytical decisions and limitations
└── README.md
```

## Author

Daniel Niaragh — Bachelor of Data Science, Victoria University. Built as a public-good analytics project demonstrating end-to-end data engineering, ML, and deployment.

## Licence

MIT
