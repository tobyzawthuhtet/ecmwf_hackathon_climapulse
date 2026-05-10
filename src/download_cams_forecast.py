"""
Download CAMS European Air Quality Forecasts (analysis, leadtime=0) for Berlin.
Dataset : cams-europe-air-quality-forecasts  |  type=analysis  |  leadtime_hour=0

Requests one week at a time (keeps cost within limits).
Variables: 5 key AQ vars relevant to health analysis.
Output  : data/raw/cams_forecast/cams_forecast_berlin_YYYY_MM.nc

Usage:
    python download_cams_forecast.py          # default year 2023
    python download_cams_forecast.py 2023     # single year
"""
import cdsapi
import zipfile
import xarray as xr
import pandas as pd
from pathlib import Path
import sys
import tempfile

OUT_DIR = Path('/fs2/toby/CmP/data/raw/cams_forecast')
OUT_DIR.mkdir(parents=True, exist_ok=True)

ADS_URL = 'https://ads.atmosphere.copernicus.eu/api'
ADS_KEY = '67325afa-ae1d-480f-ba8a-62fc21b664c4'

# Core AQ variables for health analysis
VARIABLES = [
    'particulate_matter_2.5um',
    'particulate_matter_10um',
    'nitrogen_dioxide',
    'ozone',
    'sulphur_dioxide',
]

BERLIN_BBOX = [52.68, 13.09, 52.34, 13.76]  # N, W, S, E

HOURS = [
    '00:00', '03:00', '06:00', '09:00',
    '12:00', '15:00', '18:00', '21:00',
]

client = cdsapi.Client(url=ADS_URL, key=ADS_KEY)

years = [2023]
if len(sys.argv) > 1:
    years = [int(sys.argv[1])]

for year in years:
    for month in range(1, 13):
        out_nc = OUT_DIR / f'cams_forecast_berlin_{year}_{month:02d}.nc'
        if out_nc.exists() and out_nc.stat().st_size > 10_000:
            print(f'{year}-{month:02d}: exists ({out_nc.stat().st_size/1e6:.2f} MB), skip')
            continue

        # Build list of all days in this month
        month_days = pd.date_range(
            start=f'{year}-{month:02d}-01',
            end=f'{year}-{month:02d}-01' ,
            freq='MS'
        )
        all_days = pd.date_range(
            start=f'{year}-{month:02d}-01',
            periods=pd.Period(f'{year}-{month:02d}').days_in_month,
            freq='D'
        )

        # Split into weekly chunks to stay within cost limit
        week_chunks = [all_days[i:i+7] for i in range(0, len(all_days), 7)]

        weekly_datasets = []
        month_ok = True

        with tempfile.TemporaryDirectory() as tmpdir:
            for chunk_idx, chunk in enumerate(week_chunks):
                date_start = chunk[0].strftime('%Y-%m-%d')
                date_end   = chunk[-1].strftime('%Y-%m-%d')
                date_range = f'{date_start}/{date_end}'
                zip_path   = Path(tmpdir) / f'chunk_{chunk_idx}.zip'

                print(f'  {year}-{month:02d} week {chunk_idx+1}/{len(week_chunks)}: {date_range}', flush=True)
                try:
                    client.retrieve(
                        'cams-europe-air-quality-forecasts',
                        {
                            'variable':      VARIABLES,
                            'model':         ['ensemble'],
                            'level':         ['0'],
                            'date':          [date_range],
                            'type':          ['analysis'],
                            'time':          HOURS,
                            'leadtime_hour': ['0'],
                            'data_format':   'netcdf_zip',
                            'area':          BERLIN_BBOX,
                        },
                    ).download(str(zip_path))
                except Exception as e:
                    print(f'    FAILED — {e}', flush=True)
                    month_ok = False
                    break

                # Extract from ZIP and load
                try:
                    with zipfile.ZipFile(zip_path) as zf:
                        nc_names = [n for n in zf.namelist() if n.endswith('.nc')]
                        zf.extractall(tmpdir)
                    datasets = [xr.open_dataset(f'{tmpdir}/{n}') for n in nc_names]
                    merged = xr.merge(datasets, compat='override') if len(datasets) > 1 else datasets[0]
                    weekly_datasets.append(merged)
                    print(f'    OK: vars={list(merged.data_vars)}  time={len(merged.time)}', flush=True)
                except Exception as e:
                    print(f'    extract FAILED — {e}', flush=True)
                    month_ok = False
                    break

            if not weekly_datasets:
                print(f'{year}-{month:02d}: no data downloaded', flush=True)
                continue

            # Concatenate all weekly chunks into one monthly file
            try:
                monthly = xr.concat(weekly_datasets, dim='time') if len(weekly_datasets) > 1 else weekly_datasets[0]
                for ds in weekly_datasets:
                    ds.close()
                monthly.to_netcdf(out_nc)
                size_mb = out_nc.stat().st_size / 1e6
                print(f'{year}-{month:02d}: saved → {out_nc.name}  ({size_mb:.2f} MB)  '
                      f'vars={len(list(monthly.data_vars))}  time={len(monthly.time)}', flush=True)
            except Exception as e:
                print(f'{year}-{month:02d}: concat/save FAILED — {e}', flush=True)

print('Download complete.')
