"""
Preprocess 2025 CAMS forecast ZIPs into two daily-mean CSVs:
  - data/processed/cams_daily_2025.csv          (city-wide mean)
  - data/processed/cams_daily_district_2025.csv (per-district nearest-gridpoint mean)

Run after download_cams_2025.py has finished.
"""
import zipfile
import tempfile
import warnings
import numpy as np
import pandas as pd
import xarray as xr
from pathlib import Path

warnings.filterwarnings('ignore', category=FutureWarning)

CAMS_DIR  = Path('/fs2/toby/CmP/data/raw/cams_analysis')
PROC_DIR  = Path('/fs2/toby/CmP/data/processed')
PROC_DIR.mkdir(parents=True, exist_ok=True)

# Rename map: raw var name → friendly name
VAR_MAP = {
    'pm2p5_conc':   'pm25',
    'pm10_conc':    'pm10',
    'no2_conc':     'no2',
    'o3_conc':      'o3',
    'so2_conc':     'so2',
    'no_conc':      'no',
    'co_conc':      'co',
    'nh3_conc':     'nh3',
    'hcho_conc':    'hcho',
    'chocho_conc':  'chocho',
    'nmvoc_conc':   'nmvoc',
    'pans_conc':    'pans',
    'dust':         'dust',
    'pm10_ss_conc': 'pm10_sea_salt',
    'pmwf_conc':    'pm_wildfire',
    'ecres_conc':   'ec_residential',
    'ectot_conc':   'ec_total',
    'pm2p5_nh4_conc':      'pm25_nh4',
    'pm2p5_no3_conc':      'pm25_no3',
    'pm2p5_so4_conc':      'pm25_so4',
    'pm2p5_total_om_conc': 'pm25_om',
    'sia_conc':     'sia',
}

# Berlin district centroids (lat, lon)
DISTRICTS = {
    'Mitte':                    (52.517, 13.389),
    'Friedrichshain-Kreuzberg': (52.501, 13.449),
    'Pankow':                   (52.573, 13.413),
    'Charlottenburg-Wilmersdorf':(52.510, 13.303),
    'Spandau':                  (52.536, 13.200),
    'Steglitz-Zehlendorf':      (52.432, 13.256),
    'Tempelhof-Schöneberg':     (52.462, 13.383),
    'Neukölln':                 (52.478, 13.450),
    'Treptow-Köpenick':         (52.424, 13.580),
    'Marzahn-Hellersdorf':      (52.534, 13.601),
    'Lichtenberg':              (52.526, 13.504),
    'Reinickendorf':            (52.589, 13.325),
}


def load_daily_zip(zip_path):
    """Extract ENS_ANALYSIS.nc from a daily ZIP and return the Dataset."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmpdir)
        nc_files = list(Path(tmpdir).glob('*.nc'))
        if not nc_files:
            return None
        ds = xr.open_dataset(str(nc_files[0]), decode_timedelta=False)
        ds.load()
        return ds


def process_file(zip_path):
    date_str = zip_path.stem.replace('ads_cams_forecast_', '')
    date     = pd.Timestamp(date_str)

    ds = load_daily_zip(zip_path)
    if ds is None:
        return None, None

    # Squeeze level dimension (always 1 level)
    ds = ds.squeeze('level', drop=True)

    # --- City-wide daily mean ---
    city_row = {'date': date}
    for raw, friendly in VAR_MAP.items():
        if raw in ds:
            city_row[friendly] = float(ds[raw].mean())

    # --- District-level daily mean (nearest grid point) ---
    district_rows = []
    for district, (dlat, dlon) in DISTRICTS.items():
        row = {'date': date, 'district': district}
        pt  = ds.sel(latitude=dlat, longitude=dlon, method='nearest')
        for raw, friendly in VAR_MAP.items():
            if raw in ds:
                row[friendly] = float(pt[raw].mean())
        district_rows.append(row)

    ds.close()
    return city_row, district_rows


LAG_VARS = ['pm25', 'pm10', 'no2', 'o3', 'so2', 'no', 'co', 'nh3', 'dust']
LAG_DAYS = list(range(1, 8))  # lag_1 … lag_7


def add_lags(df, group_col=None):
    """
    Add lag_1 … lag_7 columns for each variable in LAG_VARS.
    If group_col is given (e.g. 'district'), lags are computed within each group
    so values never bleed across districts.
    Rows where a lag window extends before the first available date get NaN.
    """
    df = df.sort_values(['date'] if group_col is None else [group_col, 'date']).copy()
    aq_cols = [v for v in LAG_VARS if v in df.columns]

    if group_col:
        for var in aq_cols:
            for lag in LAG_DAYS:
                df[f'{var}_lag{lag}'] = (
                    df.groupby(group_col)[var].shift(lag)
                )
    else:
        for var in aq_cols:
            for lag in LAG_DAYS:
                df[f'{var}_lag{lag}'] = df[var].shift(lag)

    return df.reset_index(drop=True)


zip_files = sorted(CAMS_DIR.glob('ads_cams_forecast_2025-*.zip'))
zip_files = [z for z in zip_files if not z.name.endswith('.tmp')]
print(f'Found {len(zip_files)} ZIP files to process')

city_rows     = []
district_rows = []

for i, zf in enumerate(zip_files, 1):
    city_row, d_rows = process_file(zf)
    if city_row:
        city_rows.append(city_row)
    if d_rows:
        district_rows.extend(d_rows)
    if i % 30 == 0 or i == len(zip_files):
        print(f'  {i}/{len(zip_files)} files processed', flush=True)

# --- City-wide: sort → add lags → save ---
city_df = (
    pd.DataFrame(city_rows)
    .sort_values('date')
    .reset_index(drop=True)
)
city_df = add_lags(city_df)
city_out = PROC_DIR / 'cams_daily_2025.csv'
city_df.to_csv(city_out, index=False)
print(f'\nCity-wide: {city_df.shape}  →  {city_out}')

# --- District-level: sort → add lags per district → save ---
dist_df = (
    pd.DataFrame(district_rows)
    .sort_values(['district', 'date'])
    .reset_index(drop=True)
)
dist_df = add_lags(dist_df, group_col='district')
dist_df = dist_df.sort_values(['date', 'district']).reset_index(drop=True)
dist_out = PROC_DIR / 'cams_daily_district_2025.csv'
dist_df.to_csv(dist_out, index=False)
print(f'District:  {dist_df.shape}  →  {dist_out}')

# --- Summary ---
lag_cols = [c for c in city_df.columns if '_lag' in c]
print(f'\nLag features added: {len(lag_cols)} columns ({LAG_VARS[0]}_lag1 … {LAG_VARS[-1]}_lag7)')
print(f'First 7 rows have NaN lags (insufficient history) — expected behaviour')
print('\nPreprocessing complete.')
print(city_df[['date'] + list(city_df.columns[1:6])].head(10).to_string(index=False))
