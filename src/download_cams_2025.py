"""
Download CAMS European Air Quality Forecasts (analysis, leadtime=0) for 2025.
Based on the pattern in notebooks/01_data_acquisition.ipynb.

Uses ThreadPoolExecutor (max 5 workers) for parallel downloads.
Skips dates where the output ZIP already exists and has size > 0.

Output: data/raw/cams_analysis/ads_cams_forecast_YYYY-MM-DD.zip
"""
import cdsapi
import pandas as pd
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

OUT_DIR = Path('/fs2/toby/CmP/data/raw/cams_analysis')
OUT_DIR.mkdir(parents=True, exist_ok=True)

ADS_URL = 'https://ads.atmosphere.copernicus.eu/api'
ADS_KEY = '67325afa-ae1d-480f-ba8a-62fc21b664c4'

VARIABLES = [
    'ammonia', 'carbon_monoxide', 'formaldehyde', 'glyoxal',
    'nitrogen_dioxide', 'nitrogen_monoxide', 'non_methane_vocs', 'ozone',
    'particulate_matter_2.5um', 'pm2.5_ammonium', 'pm2.5_nitrate',
    'residential_elementary_carbon', 'secondary_inorganic_aerosol',
    'pm2.5_sulphate', 'total_elementary_carbon', 'pm2.5_total_organic_matter',
    'particulate_matter_10um', 'dust', 'pm10_sea_salt_dry', 'pm10_wildfires',
    'peroxyacyl_nitrates', 'sulphur_dioxide',
]

HOURS = [f'{h:02d}:00' for h in range(24)]

BERLIN_BBOX = [52.68, 13.09, 52.34, 13.76]  # N, W, S, E

MAX_WORKERS = 5

calendar_2025 = pd.date_range('2025-01-01', '2025-12-31', freq='D')


def download_one_day(date, retries=3, sleep_seconds=15):
    date_str = date.strftime('%Y-%m-%d')
    out_file = OUT_DIR / f'ads_cams_forecast_{date_str}.zip'
    tmp_file = OUT_DIR / f'ads_cams_forecast_{date_str}.zip.tmp'

    if out_file.exists() and out_file.stat().st_size > 0:
        return date_str, 'skipped'

    request = {
        'variable': VARIABLES,
        'model': ['ensemble'],
        'level': ['50'],
        'date': [f'{date_str}/{date_str}'],
        'type': ['analysis'],
        'time': HOURS,
        'leadtime_hour': ['0'],
        'data_format': 'netcdf_zip',
        'area': BERLIN_BBOX,
    }

    for attempt in range(1, retries + 1):
        try:
            client = cdsapi.Client(url=ADS_URL, key=ADS_KEY)
            client.retrieve('cams-europe-air-quality-forecasts', request).download(str(tmp_file))
            tmp_file.rename(out_file)
            return date_str, 'downloaded'
        except Exception as e:
            if tmp_file.exists():
                tmp_file.unlink()
            if attempt < retries:
                time.sleep(sleep_seconds)
            else:
                return date_str, f'failed: {e}'


results = []
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {executor.submit(download_one_day, d): d for d in calendar_2025}
    total = len(futures)
    done = 0
    for future in as_completed(futures):
        date_str, status = future.result()
        done += 1
        results.append((date_str, status))
        print(f'[{done:3d}/{total}] {date_str}: {status}', flush=True)

downloaded = [r for r in results if r[1] == 'downloaded']
skipped    = [r for r in results if r[1] == 'skipped']
failed     = [r for r in results if r[1].startswith('failed')]

print(f'\nDone — downloaded: {len(downloaded)}, skipped: {len(skipped)}, failed: {len(failed)}')
if failed:
    print('Failed dates:')
    for d, e in sorted(failed):
        print(f'  {d}: {e}')
