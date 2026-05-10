"""
Compute daily district-level Potential Risk scores and classify as High / Medium / Low.

Risk model (three components):
  1. AQ Exposure Score  — normalised against WHO 24h guidelines (0-1, capped at 1)
  2. Population Density Factor — normalised to Berlin max (0-1)
  3. EMS Demand Rate   — predicted counts per 1000 residents, normalised (0-1)

Composite: risk = 0.40 × AQ + 0.35 × density + 0.25 × ems_rate

Thresholds (stable across time, not quantile-based so they generalise to new data):
  High   ≥ 0.55
  Medium  0.30 – 0.55
  Low    < 0.30

Outputs:
  data/processed/risk_scores_2025.csv   — daily risk score + level per district
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path

PROC_DIR = Path('/fs2/toby/CmP/data/processed')
RAW_DIR  = Path('/fs2/toby/CmP/data/raw')

# ── Population stats ──────────────────────────────────────────────────────────
DISTRICT_STATS = {
    'Mitte':                     {'population': 386181, 'area_km2': 39.47},
    'Friedrichshain-Kreuzberg':  {'population': 294099, 'area_km2': 20.16},
    'Pankow':                    {'population': 415257, 'area_km2': 103.01},
    'Charlottenburg-Wilmersdorf':{'population': 344207, 'area_km2': 64.74},
    'Spandau':                   {'population': 243977, 'area_km2': 91.91},
    'Steglitz-Zehlendorf':       {'population': 308080, 'area_km2': 102.49},
    'Tempelhof-Schöneberg':      {'population': 359199, 'area_km2': 53.09},
    'Neukölln':                  {'population': 328826, 'area_km2': 44.93},
    'Treptow-Köpenick':          {'population': 275469, 'area_km2': 168.42},
    'Marzahn-Hellersdorf':       {'population': 265225, 'area_km2': 61.74},
    'Lichtenberg':               {'population': 298187, 'area_km2': 52.29},
    'Reinickendorf':             {'population': 268568, 'area_km2': 89.49},
}

pop_df = pd.DataFrame.from_dict(DISTRICT_STATS, orient='index').reset_index()
pop_df.columns = ['district', 'population', 'area_km2']
pop_df['pop_density'] = pop_df['population'] / pop_df['area_km2']

MAX_DENSITY = pop_df['pop_density'].max()  # Friedrichshain-Kreuzberg ≈ 14588

# ── WHO 24h guidelines (µg/m³) ───────────────────────────────────────────────
WHO = {'pm25': 15, 'pm10': 45, 'no2': 25, 'o3': 100, 'so2': 40}
# Weights for AQ sub-index
AQ_WEIGHTS = {'pm25': 0.35, 'pm10': 0.15, 'no2': 0.25, 'o3': 0.20, 'so2': 0.05}


def aq_score(row):
    """Weighted normalised AQ index (0–1, capped at 1)."""
    score = 0.0
    for var, w in AQ_WEIGHTS.items():
        if var in row and not pd.isna(row[var]):
            score += w * min(row[var] / WHO[var], 1.0)
    return round(score, 4)


def classify(score):
    if score >= 0.55:   return 'High'
    if score >= 0.30:   return 'Medium'
    return 'Low'


# ── Load CAMS district data ───────────────────────────────────────────────────
cams = pd.read_csv(PROC_DIR / 'cams_daily_district_2025.csv', parse_dates=['date'])
cams = pd.merge(cams, pop_df[['district', 'population', 'pop_density']], on='district', how='left')

# ── Load predicted EMS (from inference output if available) ──────────────────
pred_file = PROC_DIR / 'district_inference_predictions.csv'
if pred_file.exists():
    pred = pd.read_csv(pred_file, parse_dates=['date'])
else:
    # Fall back to actual health counts
    health = pd.read_csv(PROC_DIR / 'daily_district_health.csv', parse_dates=['date'])
    health = health[health.date.dt.year == 2025]
    TARGET_COLS = [c for c in health.columns if c.startswith('code_')]
    pred = health[['date', 'district'] + TARGET_COLS].copy()
    pred['total_predicted_ems'] = pred[TARGET_COLS].sum(axis=1)
    pred_file = None

# If we have per-target predictions sum them
if 'total_predicted_ems' not in pred.columns:
    tgt_cols = [c for c in pred.columns if '_pred' in c or c.startswith('code_')]
    pred['total_predicted_ems'] = pred[tgt_cols].sum(axis=1)

ems_agg = pred[['date', 'district', 'total_predicted_ems']].copy()

# ── Merge and score ──────────────────────────────────────────────────────────
df = pd.merge(cams, ems_agg, on=['date', 'district'], how='left')

# AQ score
df['aq_score'] = df.apply(aq_score, axis=1)

# Population density factor (0–1)
df['density_factor'] = (df['pop_density'] / MAX_DENSITY).clip(0, 1).round(4)

# EMS rate per 1000 residents, normalised to Berlin max observed
df['ems_rate'] = df['total_predicted_ems'] / (df['population'] / 1000)
max_ems_rate   = df['ems_rate'].quantile(0.95)  # avoid outlier domination
df['ems_factor'] = (df['ems_rate'] / max_ems_rate).clip(0, 1).round(4)

# Composite risk score
df['risk_score'] = (
    0.40 * df['aq_score'] +
    0.35 * df['density_factor'] +
    0.25 * df['ems_factor'].fillna(0)
).round(4)

df['risk_level'] = df['risk_score'].apply(classify)

# ── Output ───────────────────────────────────────────────────────────────────
KEEP = ['date', 'district', 'population', 'pop_density',
        'pm25', 'pm10', 'no2', 'o3', 'so2',
        'aq_score', 'density_factor', 'ems_factor', 'risk_score', 'risk_level']
out = df[[c for c in KEEP if c in df.columns]].sort_values(['date', 'district'])

out_path = PROC_DIR / 'risk_scores_2025.csv'
out.to_csv(out_path, index=False)
print(f'Saved → {out_path}  ({out.shape[0]} rows)')

print('\n=== Risk Level Distribution ===')
print(out['risk_level'].value_counts().to_string())

print('\n=== Mean Risk Score by District ===')
summary = (
    out.groupby('district')[['aq_score', 'density_factor', 'risk_score']]
    .mean().round(3)
    .assign(risk_level=out.groupby('district')['risk_level']
            .agg(lambda x: x.value_counts().index[0]))
    .sort_values('risk_score', ascending=False)
)
print(summary.to_string())

if __name__ == '__main__':
    print('\nDone.')
