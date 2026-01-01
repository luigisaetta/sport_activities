# Sport Activities

A pragmatic Python toolkit to fetch and analyze your **Garmin Connect** workout data, with a clean data model and *correct pagination* (no missing activities).

This repository is designed as a solid foundation for:
- personal training analysis
- dashboards and reports
- future **MCP (Model Context Protocol) servers** and agent-based tools

---

## Why this project exists

Garmin Connect is tricky:

- Activity lists are **paginated** → if you don’t loop, you silently lose workouts
- “Activity details” endpoints often return **partial or empty data**
- Payloads vary a lot by **sport, device, and firmware**

This project takes a **reliable approach**:

- **Activity summaries are the source of truth**
- Pagination is **always handled**
- Data is normalized into **typed Python models**
- Raw Garmin payloads are preserved for future enrichment

---

## Features

- ✅ Garmin Connect authentication (username/password)
- ✅ Optional session reuse (`session.json`)
- ✅ Fetch **all activities in a date range** (robust pagination)
- ✅ Typed activity models:
  - Cycling (`road_biking`, `virtual_ride`, …)
  - Running
  - Swimming (`lap_swimming`, …)
  - Generic fallback
- ✅ Numeric normalization (rounded to 2 decimals)
- ✅ Clean API, MCP-friendly output

---

## Project structure
sport_activities/
├── garmin_client.py
├── config_private.py # credentials (NOT committed)
├── test_models_and_parsing.py # unit tests (no network)
├── test_integration_typed_summaries.py
└── README.md


## Data model
**Activities** are converted into typed dataclasses:
- ActivitySummaryBase
- CyclingActivitySummary
- RunningActivitySummary
- SwimmingActivitySummary
- GenericActivitySummary

Each object:
- exposes normalized fields (distance, duration, speed, HR, power, …)
- keeps the original Garmin payload in raw

