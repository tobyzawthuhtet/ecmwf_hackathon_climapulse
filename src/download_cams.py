"""
Download CAMS European Air Quality Reanalysis for Berlin (2018–2026).
Requests one variable per month to stay within ADS cost limits.
Output: data/raw/cams/cams_berlin_YYYY_MM.nc  (all 5 variables merged)
"""
import cdsapi
import zipfile
import xarray as xr
from pathlib import Path
import sys
import tempfile
import calendar

CAMS_DIR = Path('/fs2/toby/CmP/data/raw/cams')
CAMS_DIR.mkdir(parents=True, exist_ok=True)

ADS_URL = 'https://ads.atmosphere.copernicus.eu/api'
ADS_KEY = '67325afa-ae1d-480f-ba8a-62fc21b664c4'

VARIABLES = [
    'particulate_matter_2.5um',
    'particulate_matter_10um',
    'nitrogen_dioxide',
    'ozone',
    'sulphur_dioxide',
]

BERLIN_BBOX = [52.68, 13.09, 52.34, 13.76]  # N, W, S, E

client = cdsapi.Client(url=ADS_URL, key=ADS_KEY)

years = list(range(2018, 2027))
if len(sys.argv) > 1:
    years = [int(sys.argv[1])]

for year in years:
    for month in range(1, 13):
        out_nc = CAMS_DIR / f'cams_berlin_{year}_{month:02d}.nc'
        if out_nc.exists() and out_nc.stat().st_size > 10_000:
            print(f'{year}-{month:02d}: exists ({out_nc.stat().st_size/1e6:.2f} MB), skip')
            continue

        # Date range for the full month
        last_day = calendar.monthrange(year, month)[1]
        date_range = f'{year}-{month:02d}-01/{year}-{month:02d}-{last_day:02d}'

        var_datasets = []

        with tempfile.TemporaryDirectory() as tmpdir:
            for var in VARIABLES:
                zip_path = Path(tmpdir) / f'{var}.zip'
                print(f'{year}-{month:02d} [{var}]: requesting...', flush=True)
                try:
                    client.retrieve(
                        'cams-europe-air-quality-reanalyses',
                        {
                            'variable':     [var],
                            'model':        ['ensemble'],
                            'level':        ['0'],
                            'type':         ['validated_reanalysis'],
                            'date':         [date_range],
                            'time':         ['00:00', '03:00', '06:00', '09:00',
                                             '12:00', '15:00', '18:00', '21:00'],
                            'data_format':  'netcdf_zip',
                            'area':         BERLIN_BBOX,
                        },
                    ).download(str(zip_path))
                except Exception as e:
                    print(f'  FAILED — {e}', flush=True)
                    continue

                # Extract .nc from ZIP
                try:
                    with zipfile.ZipFile(zip_path) as zf:
                        for name in zf.namelist():
                            if name.endswith('.nc'):
                                extracted = Path(tmpdir) / f'{var}.nc'
                                with zf.open(name) as src, open(extracted, 'wb') as dst:
                                    dst.write(src.read())
                                ds = xr.open_dataset(extracted)
                                var_datasets.append(ds)
                                print(f'  OK: vars={list(ds.data_vars)}', flush=True)
                                break
                except Exception as e:
                    print(f'  ZIP extract FAILED — {e}', flush=True)
                    continue

            if not var_datasets:
                print(f'{year}-{month:02d}: no data, skipping', flush=True)
                continue

            merged = xr.merge(var_datasets) if len(var_datasets) > 1 else var_datasets[0]
            merged.to_netcdf(out_nc)
            print(f'{year}-{month:02d}: saved → {out_nc.name}  '
                  f'({out_nc.stat().st_size/1e6:.2f} MB)  '
                  f'vars={list(merged.data_vars)}', flush=True)

print('CAMS download complete.')
