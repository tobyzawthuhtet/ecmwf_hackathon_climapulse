# Climate × Health  — Analysis Pipeline ( Berlin case study )

Investigation of how air quality conditions affect emergency medical service (EMS) demand in Berlin, using Berlin Fire Brigade open data and Copernicus CAMS atmospheric forecasts.

---

## Project Structure

```
./
├── BF-Open-Data/          Berlin Fire Brigade open data (source)
├── data/
│   ├── raw/
│   │   ├── cams_analysis/ Daily CAMS forecast ZIPs (one per day)
│   │   ├── cams/          CAMS reanalysis NetCDF files (multi-year)
│   │   ├── era5/          ERA5 climate NetCDF files
│   │   └── berlin_districts.geojson
│   └── processed/         Analysis-ready CSVs and output figures
├── models/                Trained district inference models (.joblib)
├── notebooks/             Jupyter notebooks (run in order 01 → 07)
└── src/                   Standalone Python scripts
```

**Python environment:** `conda activate test` — use `conda run -n test python <script>` for all execution.

---

## Quick Start

```bash
# 1. Download 2025 CAMS data
conda run -n my_env python src/download_cams_2025.py

# 2. Preprocess into daily CSVs
conda run -n my_env python src/preprocess_cams_2025.py

# 3. Build health preprocessed data (run notebook 02)
# 4. Run analysis notebooks in order
```

---

## Source Scripts (`src/`)

### `download_cams_2025.py`
Downloads CAMS European Air Quality Forecast ZIPs for all of 2025 from the Atmosphere Data Store (ADS).

- **Dataset:** `cams-europe-air-quality-forecasts` — analysis type, leadtime hour = 0
- **Coverage:** 2025-01-01 to 2025-12-31, Berlin bounding box (52.3–52.7°N, 13.0–13.8°E)
- **Concurrency:** 5 parallel threads; skips dates already downloaded
- **Output:** `data/raw/cams_analysis/ads_cams_forecast_YYYY-MM-DD.zip` (365 files)
- **Requires:** ADS API key configured in script (`ADS_KEY`)

```bash
conda run -n my_env python src/download_cams_2025.py
```

---

### `preprocess_cams_2025.py`
Converts the downloaded daily CAMS ZIPs into two analysis-ready CSVs with time-lag features.

- **Input:** `data/raw/cams_analysis/ads_cams_forecast_2025-*.zip`
- **Extracts:** `ENS_ANALYSIS.nc` from each ZIP; squeezes level dimension; computes 24-hour daily mean
- **Variables (22):** PM2.5, PM10, NO₂, O₃, SO₂, NO, CO, NH₃, HCHO, CHOCHO, NMVOC, PANs, dust, sea-salt PM10, wildfire PM, EC residential/total, PM2.5 components (NH4, NO3, SO4, OM), SIA
- **Time-lag features:** lag₁–lag₇ for 9 core variables (PM2.5, PM10, NO₂, O₃, SO₂, NO, CO, NH₃, dust) — computed per-district to prevent cross-district bleed
- **Outputs:**
  - `data/processed/cams_daily_2025.csv` — 365 rows × 86 columns (city-wide mean)
  - `data/processed/cams_daily_district_2025.csv` — 4,380 rows × 87 columns (per district, nearest grid point)

```bash
conda run -n my_env python src/preprocess_cams_2025.py
```

---

### `download_berlin_geodata.py`
Downloads Berlin district boundary polygons and attaches official 2023 population and area statistics.

- **Source:** Berlin Open Data / TSB S3 (Bezirksgrenzen GeoJSON)
- **Population:** Statistik Berlin Brandenburg 2023 data (hardcoded from official release)
- **Output:** `data/raw/berlin_districts.geojson` — 12 district polygons with `pop_2023`, `area_km2`, `pop_density_km2` properties

```bash
conda run -n my_env python src/download_berlin_geodata.py
```

---

### `compute_risk_level.py`
Recomputes district-level Potential Risk scores and classifications from existing processed data.

- **Inputs:** `cams_daily_district_2025.csv`, `berlin_districts.geojson`, `district_inference_metrics.csv`
- **Risk formula:** `0.40 × AQ_score + 0.35 × density_factor + 0.25 × ems_factor`
  - AQ score: weighted sum of pollutants normalised against WHO 24h guidelines (PM2.5=15, PM10=45, NO₂=25, O₃=100, SO₂=40 µg/m³)
  - Density factor: population density normalised to Berlin maximum
  - EMS factor: predicted EMS demand normalised to district maximum
- **Classification thresholds:** High ≥ 0.55 | Medium 0.30–0.55 | Low < 0.30
- **Output:** `data/processed/risk_scores_2025.csv`

```bash
conda run -n my_env python src/compute_risk_level.py
```

---

### `download_cams.py` *(legacy multi-year)*
Downloads CAMS reanalysis data (2018–2026) one variable per month to stay within ADS cost limits.
Outputs per-month NetCDF files to `data/raw/cams/`.

### `download_cams_forecast.py` *(legacy)*
Downloads CAMS forecasts week-by-week. Superseded by `download_cams_2025.py` for 2025 analysis.

### `download_era5.py` *(legacy)*
Downloads ERA5 climate reanalysis (temperature, precipitation, wind, radiation) month-by-month from CDS.
Outputs per-month NetCDF files to `data/raw/era5/`.

---

## Notebooks (`notebooks/`)

Run notebooks in sequence. All use the `test` conda environment — select it as the kernel in JupyterLab.

---

### `01_data_acquisition.ipynb`
Interactive guide for downloading ERA5 and CAMS data via the Copernicus APIs.
- Checks `~/.cdsapirc` configuration
- Documents download parameters for Berlin bounding box
- Verification cells: prints shape and date range of downloaded files

---

### `02_preprocessing_health.ipynb`
Builds clean analysis-ready health CSVs from BF-Open-Data raw files.

- Loads all Mission_Data years (2018–2026), filters to EMS (`Rettungsdienst`) missions
- Aggregates by dispatch code → daily city-wide and daily district-level pivot tables
- Merges aggregate EMS statistics from `BFw_mission_data_daily.csv`
- Adds confounder columns: `day_of_week`, `is_weekend`, `month`, `day_of_year`, `doy_sin`, `doy_cos`, `is_public_holiday`, `covid_flag`, `year`
- **Outputs:**
  - `data/processed/daily_city_health.csv` — city-wide daily counts per dispatch code
  - `data/processed/daily_district_health.csv` — district × day counts per dispatch code
  - `data/processed/daily_district_health_smoothed.csv` — same with 7-day centred rolling mean applied to count columns

**Dispatch code mapping:**

| Column | Code | Condition |
|---|---|---|
| `code_02_allergy_insect` | 02 | Allergy / insect sting |
| `code_06_breathing` | 06 | Breathing difficulties |
| `code_09_cardiac_arrest` | 09 | Cardiac arrest |
| `code_10_chest_pain` | 10 | Chest pain |
| `code_12_seizure` | 12 | Seizure / convulsion |
| `code_13_blood_sugar` | 13 | Blood sugar emergency |
| `code_17_falls` | 17 | Falls / trauma |
| `code_18_headache` | 18 | Severe headache |
| `code_19_heart_problems` | 19 | Heart problems |
| `code_20_heat_cold_exposure` | 20 | Heat / cold exposure |
| `code_28_stroke_tia` | 28 | Stroke / TIA |
| `code_31_loss_of_consciousness` | 31 | Loss of consciousness |

---

### `03_preprocessing_climate.ipynb`
Extracts daily Berlin climate values from ERA5 NetCDF files and merges with health data.

- Loads ERA5 hourly data, resamples to daily (mean/min/max/sum by variable)
- Extracts Berlin centre point (52.52°N, 13.405°E) and district centroids
- Derives apparent temperature, wind speed from u/v components
- Loads CAMS reanalysis (multi-year) → daily means
- Adds rolling features: 3-day and 7-day means (shifted by 1 day to avoid leakage)
- **Output:** `data/processed/daily_climate.csv`

---

### `04_linear_analysis.ipynb`
Multivariate linear analysis of CAMS air quality × EMS health outcomes for 2025.

**Section 1 — Correlation screening**
- Spearman CCF at lags 0–7 days for each (AQ variable, health outcome) pair
- Heatmap of peak correlations; includes negative controls (assault, traffic) as model validation
- Output: `data/processed/ccf_peak_heatmap.png`

**Section 2 — Negative Binomial GLM (count outcomes)**
- Fits NegBin GLM for each of 75 (outcome × AQ variable) combinations
- Uses optimal lag from CCF (capped at 3 days for AQ)
- Confounders: `day_of_week`, `is_weekend`, `is_public_holiday`, `doy_sin`, `doy_cos`, `month`
- FDR correction (Benjamini-Hochberg) across all tests
- Output: `data/processed/results_negbin.csv`, `data/processed/negbin_forest_plots.png`

**Section 3 — OLS + HAC (response time)**
- OLS with Newey-West HAC standard errors (14-lag bandwidth) for continuous response time outcome
- Output: `data/processed/results_ols_hac.csv`, `data/processed/residual_acf.png`

**Section 4 — Distributed lag analysis**
- Fits separate models at lags 0–3 days; plots cumulative effect with 95% CI
- Key pairs: PM2.5 → critical EMS, O₃ → breathing, NO₂ → cardiac arrest
- Output: `data/processed/distributed_lag.png`

**Section 5 — District fixed-effects panel**
- OLS with district dummies + HAC SEs on merged district health × CAMS panel
- Output: `data/processed/results_panel_fe.csv`

**Section 6 — Null model comparison**
- Compares AIC of seasonal-only vs. AQ-augmented model; validates that AQ adds explanatory power

---

### `05_arm_analysis.ipynb`
Association Rules Mining (ARM) — discovers non-linear co-occurrence patterns between AQ levels and health outcomes.

- Discretises AQ variables into 3 bins (Low/Moderate/High) using WHO-based thresholds
- Discretises health outcomes into Low/Normal/Elevated/Extreme (quantile-based)
- Runs FP-Growth algorithm (`mlxtend`) with `min_support=0.05`, `min_confidence=0.6`, `min_lift=1.5`
- Filters to rules where the consequent is a health outcome
- Stratifies by season (Winter/Spring/Summer/Autumn)
- **Outputs:**
  - `data/processed/arm_rules_cams.csv` — all significant rules
  - `data/processed/arm_rules_negative_controls.csv` — rules for negative control validation

```
Key parameters:
  min_support    = 0.05   (rule covers ≥5% of days)
  min_confidence = 0.60   (given antecedent, outcome occurs ≥60% of time)
  min_lift       = 1.50   (rule is 1.5× more likely than random)
```

---

### `06_bayesian_network.ipynb`
Structure learning and probabilistic inference using Bayesian Networks.

- Uses PC algorithm (constraint-based) + BIC score refinement (`pgmpy` / `bnlearn`)
- Enforces temporal directionality: prior-day AQ → same-day health outcome
- Learns conditional probability distributions (CPDs) for each node
- Queries: `P(high CPR | extreme heat, high O₃)` etc.
- Bootstrap stability analysis (100 resamples, keeps edges present in >70%)

---

### `07_district_inference.ipynb`
Per-district EMS demand prediction and Potential Risk classification.

**Model:**
- Gradient Boosting Regressor (scikit-learn) per district × dispatch-code target
- 6 health targets × 12 districts = 72 models total
- Features: CAMS AQ variables + lag₁–lag₇ + calendar confounders
- 80/20 chronological train/test split
- Models saved to `models/district_<name>.joblib`

**Risk scoring:**
- `infer_with_risk(date, cams_row)` → DataFrame with `risk_score` and `risk_level` (High/Medium/Low)
- Risk = 0.40 × AQ + 0.35 × population density + 0.25 × predicted EMS rate
- **Outputs:**
  - `data/processed/district_inference_metrics.csv` — R² and RMSE per district × target
  - `data/processed/risk_scores_2025.csv` — daily risk score + level per district
  - `data/processed/berlin_risk_map.png` — static 3-panel choropleth
  - `data/processed/berlin_risk_interactive.html` — interactive Folium map
  - `data/processed/risk_timeline.png` — heatmap of risk level over time × district

---

### `playground.ipynb`
3D lexcube visualisation of CAMS variables across time, latitude, and longitude.

- Loads all 365 daily ZIPs → stacks into a `time × lat × lon` DataArray
- Renders interactive `Cube3DWidget` for: PM2.5, NO₂, O₃, PM10, SO₂, Dust
- Requires `lexcube` package and a dask-chunked array (`.chunk({})`)

---

## Processed Data Files

| File | Description | Shape |
|---|---|---|
| `daily_city_health.csv` | City-wide daily EMS counts + aggregate stats + confounders | ~3000 × 50 |
| `daily_district_health.csv` | District × day EMS counts + confounders | ~36600 × 24 |
| `daily_district_health_smoothed.csv` | Same, with 7-day centred rolling mean on count columns | ~36600 × 24 |
| `cams_daily_2025.csv` | City-wide daily AQ means + lag features (2025) | 365 × 86 |
| `cams_daily_district_2025.csv` | Per-district daily AQ means + lag features (2025) | 4380 × 87 |
| `risk_scores_2025.csv` | Daily risk score + High/Medium/Low level per district | 4380 × 5 |
| `results_negbin.csv` | NegBin GLM coefficients + FDR-corrected p-values | 75 × 10 |
| `results_ols_hac.csv` | OLS+HAC results for response time outcome | 5 × 9 |
| `results_panel_fe.csv` | District fixed-effects panel regression results | varies |
| `arm_rules_cams.csv` | Association rules (AQ → health) with support/confidence/lift | varies |

---

## Key Methodological Notes

- **COVID period** (2020-03-15 to 2021-06-30): flagged via `covid_flag` column; exclude or control depending on analysis
- **Seasonal confounding**: always include `doy_sin` + `doy_cos` in regression models — they absorb the annual health cycle
- **Multiple testing**: use FDR (Benjamini-Hochberg) when testing many outcome × predictor combinations
- **Lag features**: pre-built lag₁–lag₇ columns in CAMS CSVs are computed per-district so values never bleed across district boundaries
- **Model dtype**: pass `X.astype(float)` to all statsmodels GLM/OLS calls — mixed bool/int columns cause a dtype=object error
