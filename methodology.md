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
| 2026-05-28 | Phase 1 closed. EDA notebook (notebooks/01_eda.ipynb) added documenting data coverage, distributional structure, and the first rental stress estimates. Three definitional decisions emerged from EDA for Phase 2: (1) use p25 (lower-quartile) household income as the primary stress denominator - median income produces a signal too weak to be informative; (2) model only LGA x property-type series with at least 80 quarters of data, decision on sparse-series treatment deferred to Phase 2; (3) forecast both the DFFH official affordable-lettings percentage and our computed rent/p25-income stress ratio as complementary targets. First end-to-end choropleth map of rental stress rendered, validating that the rents + income + boundary pipeline joins cleanly. Section 3 (rental stress definition) marked as superseded - the formal definition will be locked in Phase 2. |
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

### 4.2 ABS Census 2021 G33 — Household Income by Composition
- **Source:** ABS Census 2021 G33, accessed via the Digital Atlas of Australia
- **Coverage:** Single snapshot, August 2021
- **Frequency:** Census (5-yearly; next release 2026)
- **Granularity used:** LGA-level, household income distribution across 17 weekly income bands
- **Derived metrics:** Weighted median weekly household income, weighted 25th percentile (computed via histogram-quantile interpolation)
- **Known caveats:**
  - **Single point in time.** This dataset does not provide an annual time series at LGA level. Income enters our rental stress calculation as a fixed denominator anchored to 2021, while rent varies through time (quarterly). Implication: rental stress trajectories reflect rent-side movement, with income held constant. This is a reasonable simplification given (a) the modest variation in real household income at LGA level over short horizons, (b) the lack of consistent LGA-level annual income data from any public source that includes government allowances, and (c) the primary signal of interest in this project is the rent-side dynamic.
  - **Why this over the alternatives:** ABS's "Personal Income in Australia" series provides annual data (2018-2022 at LGA level via Region Summary) but excludes government pensions and allowances. For rental affordability analysis, this exclusion systematically understates available income in retirement-heavy and welfare-recipient LGAs, distorting the stress signal. Including government payments matters. The ArcGIS Data-by-Region feature service for income exists but exposes only the latest reference year per data item, not historical years.
  - **Income band methodology:** The top band ($4000 or more) is open-ended. We cap it at $5000 as a conservative midpoint estimate for the histogram-quantile interpolation. This affects the median estimate only in LGAs where >50% of households are in the top band - this does not occur at the Victorian LGA level.
  - **Confidentiality perturbation:** ABS applies small random adjustments to all cell counts to protect privacy. Effect on LGA-level aggregates is negligible (<1%).
- **Decision documented in Section 3** to compute the rental stress ratio against this dataset's median (and optionally p25) weekly household income.

### 4.3 Personal Income in Australia (REFERENCE ONLY)
The ABS "Personal Income in Australia" release is widely cited and provides annual time-series data at LGA level for 2018-2022. We have not used it because it excludes government pensions and allowances and this systematically biases an affordability analysis. It is referenced here for transparency.

### 4.4 ABS LGA Boundaries
- **Source:** ABS Australian Statistical Geography Standard (ASGS) — LGA 2021 edition
- **Use:** Map visualisation in the dashboard

### 4.5 ABS ASGS Edition 3 LGA Boundaries
- **Source:** ABS Australian Statistical Geography Standard (ASGS) Edition 3 (2021) LGA boundaries, accessed via the Digital Atlas of Australia (`digitalatlas::abs-asgs-edition-3-2021-local-government-areas`)
- **Coverage:** All Australian LGAs (566 features); filtered to 79 Victorian LGAs
- **Format:** GeoJSON, GDA2020 / WGS84 (CRS84) geographic coordinates
- **Use:** Choropleth map base layer in the dashboard
- **Transformations applied:**
  - Filter to Victoria
  - Drop 3 administrative placeholders (matching income data exclusion)
  - Normalise LGA names to DFFH canonical form (matching income data mapping)
  - Simplify polygons with Douglas-Peucker tolerance 0.0005 degrees
- **Simplification trade-off:** At state-level zoom, the simplified polygons are visually indistinguishable from the originals. The simplification only becomes noticeable when zoomed into a single LGA boundary - which the dashboard does not do. Trade-off accepted in exchange for ~12x file size reduction, dramatically faster dashboard load times and lower bandwidth costs in production.
- **Known caveats:**
  - ABS LGA boundaries are statistical approximations of the legally gazetted local government boundaries, not the legal boundaries themselves. ABS notes they should not be used for legal purposes.
  - 2021 vintage. LGA boundary changes since 2021 are minor in Victoria (Moreland → Merri-bek was a rename, not a boundary change). Future ASGS Edition 4 will become available in 2026 and may be adopted in a later revision.
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
- **Income as fixed denominator:** The rental stress calculation uses 2021 household income as a constant denominator across all quarters of rent data. Real income drift between 2021 and the modelled horizon is not captured. Where rental stress trajectories are interpreted, this should be flagged.
- **Coverage varies dramatically across LGA x property-type combinations.** Hindmarsh has just 1 quarter of 2-bed-flat data over the entire 26-year series; the City of Melbourne has all 106. The modelling subset (Phase 2) will need an explicit minimum-coverage threshold; current working assumption is 80 quarters.
- **Pandemic-era anomaly (2020-2021) is real signal, not data error.** Melbourne LGA shows a ~30% rent drop in 2020-21 that fully reverses by 2023. This reflects the international-student exit during the international border closure and is verified in DFFH commentary. Phase 2 modelling will need to decide whether to mask, weight down, or include these quarters as-is.
- **Income denominator is fixed at 2021.** Real income drift between 2021 and the modelled horizon (2025+) is not captured. Stress ratio trajectories should therefore be interpreted as rent-side movement; structural income changes are outside the model.
---

## 7. Change log

| Date       | Change |
|------------|--------|
| 2026-05-16 | Initial methodology document created. LGA granularity locked. 12-month forecast horizon locked. Working rental stress definition: rent > 30% of median household income. |
| 2026-05-16 | DFFH time-series file located (`Quarterly median rents by Local Government Area`). Provides 26+ years of quarterly LGA-level rental data across 6 property types in a single file. Confirmed 40,340 clean rows after parsing, covering 78 LGAs and 106 quarters (1999-Q2 to 2025-Q3). |
| 2026-05-22 | DFFH affordability time-series parser added. Provides 25.5 years of LGA × bedroom-category affordability data (count of affordable lettings, percent affordable). 39,390 clean rows across 78 LGAs and 101 quarters (2000-Q1 to 2025-Q3). DFFH's official affordability methodology can now be used directly rather than computing our own. |
| 2026-05-22 | ABS Census 2021 G33 household income parser added. Used as the income source for the rental stress calculation - single point in time (2021) rather than annual time series. Decision documented in updated Section 4.2. 79 Victorian LGAs after filtering 3 administrative placeholders. LGA names normalised against DFFH (Bayside, Kingston, Latrobe, Colac-Otway, Merri-bek mappings). Median weekly household income range $906-$2487. p25 also computed for lower-quartile rental stress sensitivity work in Phase 2. |
| 2026-05-23 | LGA boundary GeoJSON ingestion added. Source: ABS ASGS Edition 3 (2021) Local Government Areas, downloaded from Digital Atlas of Australia. Filtered to 79 Victorian LGAs (3 administrative placeholders excluded). LGA names normalised against the same mapping used for income (Bayside, Kingston, Latrobe, Colac-Otway, Merri-bek). Polygons simplified with Douglas-Peucker tolerance 0.0005 degrees, reducing output from ~22 MB (Vic only, full detail) to ~1.8 MB (98.8% reduction from the 151 MB national source). Output committed to git at data/reference/vic_lga_boundaries.geojson so the dashboard can render immediately on clone. |
| 2026-05-23 | BUGFIX in parse_dffh.py: City of Hume LGA was being silently filtered out because its name matches the "Hume" DFFH region group label. The col 1 (LGA name) filter was incorrectly checking against KNOWN_REGIONS; regions only appear in col 0 as group headers, never as LGA names. Caught by the cross-dataset `test_g33_lgas_match_dffh_lgas` test introduced in Phase 1.4. Datasets regenerated. DFFH rents row count: 40,340 → 40,976 (now 79 LGAs, not 78). Affordability row count also updated. Reinforces value of cross-dataset compatibility tests in catching silent join failures across phases. |
| 2026-05-28 | Second Hume bugfix discovered: `parse_afford_sheet` had the same KNOWN_REGIONS filter bug that was fixed in `parse_timeseries_sheet` during Phase 1.4 deployment, but the affordability parser was missed. The bug was caught when the corrected notebook was re-run with the cross-dataset compatibility tests freshly applied. Affordability parquet regenerated. DFFH affordability row count: 39,390 -> 39,895 (now 79 LGAs, not 78). Lesson: when a bug pattern is identified, search the codebase for the same pattern in sibling functions before considering the fix complete. |
| 2026-05-28 | Phase 1 closed. EDA notebook (notebooks/01_eda.ipynb) added documenting data coverage, distributional structure, and the first rental stress estimates. Three definitional decisions emerged from EDA for Phase 2: (1) use p25 (lower-quartile) household income as the primary stress denominator - median income produces a signal too weak to be informative; (2) model only LGA x property-type series with at least 80 quarters of data, decision on sparse-series treatment deferred to Phase 2; (3) forecast both the DFFH official affordable-lettings percentage and our computed rent/p25-income stress ratio as complementary targets. First end-to-end choropleth map of rental stress rendered, validating that the rents + income + boundary pipeline joins cleanly. Section 3 (rental stress definition) marked as superseded - the formal definition will be locked in Phase 2. |