# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the **BF-Open-Data** repository — the Open Data Platform of the Berlin Fire Brigade (Berliner Feuerwehr). It is a **pure data repository**: no application code, no build system, no tests. It publishes aggregated emergency services datasets as CSV and Excel files, updated automatically each day via git commits.

GitHub remote: `https://github.com/Berliner-Feuerwehr/BF-Open-Data.git`  
License: Creative Commons Attribution 4.0 (CC BY 4.0) — attribution required when citing data.

## Data Organization

```
Datasets/
├── Daily_Data/          # City-wide daily/monthly/yearly mission and call statistics
├── Regional_Data/       # Per-year CSVs broken down by geographic unit (2018–2026)
├── Mission_Data/        # Per-incident mission records by year (2017–2026)
├── Turnout_Times/       # Quarterly vehicle turnout times by fire station
├── KV_Data/             # Missions handed off to medical on-call service (KV Berlin)
└── Dispatchcodes/       # Reference tables mapping dispatch codes to resource requirements
```

Each dataset folder contains `*_descriptions.csv` or `field_descriptions.csv` files that document field names in English and German.

## Geographic Dimensions

Regional data is aggregated at three levels:
- **District** (`district_area`): 12 administrative districts of Berlin
- **Prediction Area** (`prediction_area`): 58 regional zones
- **Planning Room** (`planning_room`): 542 neighborhood-level zones (Berlin LOR concept)

## Mission Categories

| Category | German | Description |
|---|---|---|
| EMS | Rettungsdienst | General ambulance |
| Critical EMS | Kritischer Rettungsdienst | High-priority medical |
| Critical EMS CPR | Kritischer RD mit CPR | Suspected cardiac arrest |
| Fire | Brand | Fires, smoke alarms |
| Technical Rescue | Technische Hilfeleistung | Door openings, hazmat, storm |

## Key Metrics

- **Response Time**: Alarm to first unit on scene
- **Time to First Pump / Ladder / Full Crew**: Fire-specific arrival benchmarks
- **Call Answer Time**: Time for dispatch center to answer 112 calls
- **Time Goal Achievement**: % of critical missions meeting response targets
- **Turnout Time**: Time from alert to vehicle departure at station

## Update Pattern

Automated daily git commits (typically 05:00–06:30 UTC) update Daily_Data, Regional_Data, Mission_Data, KV_Data, and Turnout_Times with the previous day's data. Commit messages are always `"Automatic Daily Update"`.

## Working with the Data

No special tooling is required. Use standard data analysis tools:
- Python: `pandas.read_csv()` — most files use semicolon (`;`) as delimiter
- R: `read.csv(..., sep=";")`
- Excel: Data → From Text/CSV, select semicolon delimiter

Check `DISCLAIMER.txt` in `Datasets/Daily_Data/` for known data caveats (e.g., incomplete call data around New Year's Eve 2024–2025 due to phone system restrictions).
