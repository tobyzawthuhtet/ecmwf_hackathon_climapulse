"""
Download Berlin district boundaries (GeoJSON) and attach official population data.

Sources:
  - District boundaries: Berlin Open Data / TSB opendata S3 (Bezirksgrenzen)
  - Population (2023): Statistik Berlin Brandenburg — Einwohnerentwicklung

Outputs:
  data/raw/berlin_districts.geojson   — district polygons with pop/area/density
"""
import requests
import json
from pathlib import Path

RAW_DIR = Path('/fs2/toby/CmP/data/raw')
RAW_DIR.mkdir(parents=True, exist_ok=True)

OUT_PATH = RAW_DIR / 'berlin_districts.geojson'

# ── Population & area (official 2023, Statistik Berlin Brandenburg) ──────────
# Source: Amt für Statistik Berlin-Brandenburg, SB A I 5 - vj 3/23
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

CANDIDATE_URLS = [
    # TSB Berlin Open Data (primary)
    'https://tsb-opendata.s3.eu-central-1.amazonaws.com/bezirksgrenzen/bezirksgrenzen.geojson',
    # Berlin FIS-Broker WFS (alternative)
    'https://fbinter.stadt-berlin.de/fb/wfs/data/senstadt/s_bezirke_95?service=WFS&version=2.0.0&request=GetFeature&typeNames=s_bezirke_95&outputFormat=application/json',
]

def try_download(urls, timeout=30):
    for url in urls:
        try:
            print(f'Trying: {url[:70]}...')
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f'  Failed: {e}')
    return None

geojson = try_download(CANDIDATE_URLS)

if geojson is None:
    print('ERROR: Could not download district boundaries. Creating placeholder.')
    # Minimal placeholder so downstream scripts don't crash
    geojson = {'type': 'FeatureCollection', 'features': []}

# ── Attach population stats to each feature ──────────────────────────────────
# Normalise district name from GeoJSON (field may vary)
NAME_FIELDS = ['Gemeinde_name', 'BEZNAME', 'name', 'Bezirksname', 'GEN']

matched = 0
for feat in geojson.get('features', []):
    props = feat.get('properties', {})
    raw_name = None
    for field in NAME_FIELDS:
        if field in props and props[field]:
            raw_name = props[field].strip()
            break

    # Try exact match first, then partial
    stats = DISTRICT_STATS.get(raw_name)
    if stats is None and raw_name:
        for k in DISTRICT_STATS:
            if k.lower() in raw_name.lower() or raw_name.lower() in k.lower():
                stats = DISTRICT_STATS[k]
                raw_name = k
                break

    if stats:
        props['district']         = raw_name
        props['population']       = stats['population']
        props['area_km2']         = stats['area_km2']
        props['pop_density']      = round(stats['population'] / stats['area_km2'], 1)
        feat['properties']        = props
        matched += 1

print(f'Matched {matched}/{len(geojson.get("features", []))} district features')

# ── If GeoJSON has no geometry (e.g. WFS failed), build from stats only ──────
if not geojson['features']:
    print('Building attribute-only GeoJSON from population stats.')
    geojson['features'] = [
        {
            'type': 'Feature',
            'geometry': None,
            'properties': {
                'district':    name,
                'population':  s['population'],
                'area_km2':    s['area_km2'],
                'pop_density': round(s['population'] / s['area_km2'], 1),
            }
        }
        for name, s in DISTRICT_STATS.items()
    ]

OUT_PATH.write_text(json.dumps(geojson, ensure_ascii=False, indent=2))
print(f'Saved → {OUT_PATH}  ({OUT_PATH.stat().st_size / 1024:.1f} KB)')
print(f'Districts with pop data:')
for feat in geojson['features']:
    p = feat['properties']
    if 'pop_density' in p:
        print(f"  {p.get('district','?'):35s}  pop={p['population']:>7,}  density={p['pop_density']:>7,.1f} /km²")
