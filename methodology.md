# Methodology

This document records every analytical decision made in this project, the reasoning behind it, and the known limitations of each choice. It is updated as the project develops.

---

## 1. Research question

**Primary:** Where in Victoria is rental stress likely to worsen most over the next 12 months, and which Local Government Areas (LGAs) show the most concerning trends?

**Secondary (descriptive):** Which LGAs have the highest current rental stress, and how has that changed over the last 10+ years?

The 12-month horizon was chosen because it is long enough to be decision-relevant for policy makers, planners, and individuals considering moves, while still being short enough to forecast with reasonable accuracy. Multi-horizon forecasting (1, 2, 3, 4 quarters ahead) is implemented rather than single-step-ahead forecasting.

---

## 2. Geographic unit

**Decision:** Analysis is conducted at the **Local Government Area (LGA)** level.

**Reasoning:**
- DFFH rental data is published at LGA and suburb level, not SA2.
- ABS income data (Personal Income in Australia, Data by Region) is published at LGA level with consistent annual time series.
- LGAs are the unit at which Victorian policy is actually made and resourced.
- Joining rental and income data at LGA level avoids the lossy concordance step that suburb-level analysis would require.

**Limitations:**
- LGAs vary enormously in size. The City of Melbourne is small and dense; the Shire of East Gippsland is vast and sparse. A single rental stress figure for a large rural LGA masks meaningful internal variation.
- Suburb-level descriptive views may be added in a later iteration to address this.

---

## 3. Definition of rental stress

**Working definition (subject to revision in Phase 2 once data is reviewed):**

A household is considered to be in **rental stress** when its weekly rent exceeds 30% of its gross weekly household income.

At the LGA level, the **rental stress indicator** is calculated as:

```
rental_stress_ratio_lga_q = median_weekly_rent_lga_q / median_weekly_household_income_lga_y
```

Where the income figure for year `y` is mapped to all four quarters of that year (income data is annual; rental data is quarterly).

**Why 30%:** This is the widely-used Australian housing affordability threshold, consistent with DFFH's own "affordable lettings" methodology and ABS rent affordability indicators.

**Alternative definitions to consider in Phase 2:**
- Lower-quartile income reference (more sensitive to housing vulnerability)
- Residual income approach (after rent, can the household meet other needs)
- DFFH's own "affordable lettings" framework (% of new lettings affordable to lower-income households)

The final choice will be made after EDA in Phase 1, and any change will be documented here.

---

## 4. Data sources

### 4.1 DFFH Victorian Rental Report
- **Source:** Department of Families, Fairness and Housing — `dffh.vic.gov.au/publications/rental-report`
- **Coverage:** June 2000 to current quarter
- **Frequency:** Quarterly
- **Granularity used:** LGA-level moving quarterly medians
- **Underlying data:** Residential Tenancies Bond Authority — covers all bonds lodged under the Residential Tenancies Act 1997
- **Known caveats:**
  - Excludes student housing, rooming houses, caravans, multiple bonds for share houses, and rooms within dwellings
  - "Moving quarterly median" smooths over three months, not a snapshot of a single month
  - Reflects new lettings only — does not capture in-place tenants who may pay below current market rates

### 4.2 ABS Personal Income in Australia
- **Source:** Australian Bureau of Statistics — `abs.gov.au/statistics/labour/earnings-and-working-conditions/personal-income-australia`
- **Coverage:** 2011-12 to most recent (currently 2022-23)
- **Frequency:** Annual
- **Granularity used:** LGA-level median total personal income, equivalised household income where available
- **Known caveats:**
  - Annual data only — must be interpolated or step-mapped to quarterly rental data
  - Small random adjustments applied for confidentiality
  - LGA boundaries change over time — concordance to current boundaries required for time series

### 4.3 ABS Census 2021
- **Source:** ABS Census Tables (G33: Total household income by household composition)
- **Granularity used:** LGA-level
- **Use:** Cross-check and demographic enrichment

### 4.4 ABS LGA Boundaries
- **Source:** ABS Australian Statistical Geography Standard (ASGS) — LGA 2021 edition
- **Use:** Map visualisation in the dashboard

---

## 5. Modelling approach (planned, Phase 3)

To be documented in Phase 3. Working plan:
1. Baseline: seasonal-naive forecast per LGA
2. Statistical: SARIMA, exponential smoothing per LGA
3. ML: gradient-boosted regression with engineered features (lags, trends, neighbour effects, cash rate, income trajectory)
4. Multi-horizon: predict 1, 2, 3, and 4 quarters ahead

Evaluation will be conducted via expanding-window backtesting on held-out quarters, with per-LGA error analysis.

---

## 6. Known limitations and open questions

This section is updated whenever a limitation is discovered.

- **LGA boundary changes:** Some Victorian LGAs have been amalgamated or redrawn over the 25-year window. A concordance layer is required.
- **Income data lag:** ABS income data is typically 2-3 years behind real time. Forecast features may need to use the most recent available year, accepting that information.
- **Pandemic-era anomalies:** Rental data 2020-2022 contains unusual patterns (rent reductions, then sharp recovery) that may distort training. Treatment to be decided in Phase 2.
- **Survivor bias in long time series:** LGAs with few bonds in any given quarter may be unreliable — a minimum-bond threshold will be applied.
- **Property type coverage varies by LGA:** Different LGAs have data for different property types (inner-city LGAs have lots of flats but few houses; rural LGAs are the opposite). The aggregation approach for the final stress metric must account for this.

---

## 7. Change log

| Date | Change |
|------|--------|
| 2026-05-16 | Initial methodology document created. LGA granularity locked. 12-month forecast horizon locked. Working rental stress definition: rent > 30% of median household income. |
| 2026-05-16 | DFFH time-series file located (`Quarterly median rents by Local Government Area`). Provides 26+ years of quarterly LGA-level rental data across 6 property types in a single file. Confirmed 40,340 clean rows after parsing, covering 78 LGAs and 106 quarters (1999-Q2 to 2025-Q3). |
