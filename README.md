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

## Examples

#### Show activities for the last 7 days
```python
from datetime import date, timedelta
from garmin_client import get_activities_in_range

end = date.today()
start = end - timedelta(days=7)

activities = get_activities_in_range(start, end)

print(f"Fetched {len(activities)} activities")
for a in activities:
    print(a.type_key, a.activity_id)
```
