# Victoria Rental Stress Forecasting

Forecasting rental stress across Victorian Local Government Areas using historical rental and income data.

**Status:** 🚧 In active development

## What this project does

This project builds an end-to-end data pipeline and machine learning system to answer one question:

> Where in Victoria is rental stress likely to worsen most over the next 12 months, and which Local Government Areas show the most concerning trends?

It combines 25+ years of quarterly rental data from the Victorian Department of Families, Fairness and Housing (DFFH) with Australian Bureau of Statistics (ABS) income and demographic data, builds a multi-horizon forecasting model, and exposes the results through an interactive dashboard.

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

- **DFFH Victorian Rental Report** — quarterly median rents by LGA, June 2000 to present
- **ABS Personal Income in Australia** — annual LGA-level income time series
- **ABS Census 2021** — household income and composition by LGA
- **ABS Statistical Geography** — LGA 2021 boundary files

See `methodology.md` for detailed documentation of sources, definitions, and analytical decisions.

## Project status

| Phase | Status |
|-------|--------|
| 0 — Project scoping | ✅ Complete |
| 1 — Data acquisition and EDA | 🚧 In progress |
| 2 — Feature engineering and rental stress definition | ⬜ Pending |
| 3 — Modelling | ⬜ Pending |
| 4 — API and dashboard | ⬜ Pending |
| 5 — Production deployment | ⬜ Pending |
| 6 — Documentation and polish | ⬜ Pending |

## Local setup

```bash
# Clone
git clone https://github.com/YOUR-USERNAME/victoria-rental-stress.git
cd victoria-rental-stress

# Create environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the ingestion pipeline (Phase 1+ — placeholder for now)
python scripts/run_pipeline.py
```

## Repository structure

```
victoria-rental-stress/
├── data/                    # Raw and processed datasets (gitignored)
├── notebooks/               # Exploratory analysis
├── src/                     # Production code
│   ├── ingestion/           # Pull DFFH and ABS data
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

