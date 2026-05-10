"""
Download ERA5 for Berlin month-by-month (avoids CDS cost-limit per request).
Files saved as: data/raw/era5/era5_berlin_YYYY_MM.nc
"""
import cdsapi
from pathlib import Path
import sys

ERA5_DIR = Path('/fs2/toby/CmP/data/raw/era5')
ERA5_DIR.mkdir(parents=True, exist_ok=True)

CDS_URL = 'https://cds.climate.copernicus.eu/api'
CDS_KEY = '44c8e973-6913-4ba0-bffc-a5228c09d7a4'

VARIABLES = [
    '2m_temperature',
    '2m_dewpoint_temperature',
    'total_precipitation',
    '10m_u_component_of_wind',
    '10m_v_component_of_wind',
    'surface_solar_radiation_downwards',
]

BERLIN_BBOX = [52.7, 13.0, 52.3, 13.8]  # N, W, S, E
DAYS  = [f'{d:02d}' for d in range(1, 32)]
HOURS = [f'{h:02d}:00' for h in range(24)]

c = cdsapi.Client(url=CDS_URL, key=CDS_KEY)

years = list(range(2018, 2027))
if len(sys.argv) > 1:
    years = [int(sys.argv[1])]

for year in years:
    for month in range(1, 13):
        out = ERA5_DIR / f'era5_berlin_{year}_{month:02d}.nc'
        if out.exists() and out.stat().st_size > 10_000:
            print(f'{year}-{month:02d}: exists ({out.stat().st_size/1e6:.1f} MB), skip')
            continue
        print(f'{year}-{month:02d}: requesting...', flush=True)
        try:
            c.retrieve(
                'reanalysis-era5-single-levels',
                {
                    'product_type': 'reanalysis',
                    'variable': VARIABLES,
                    'year': str(year),
                    'month': f'{month:02d}',
                    'day': DAYS,
                    'time': HOURS,
                    'area': BERLIN_BBOX,
                    'format': 'netcdf',
                },
                str(out)
            )
            print(f'{year}-{month:02d}: saved {out.stat().st_size/1e6:.1f} MB', flush=True)
        except Exception as e:
            print(f'{year}-{month:02d}: FAILED — {e}', flush=True)

print('Download complete.')
