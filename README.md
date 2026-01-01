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

#### Show activities for a month as JSON
```python
import json
from garmin_client import get_activities_in_range

activities = get_activities_in_range("2025-06-01", "2025-06-30")

payload = [a.to_dict() for a in activities[:3]]

print(json.dumps(payload, indent=2, ensure_ascii=False))
```

## Public API (garmin_client.py)

The `garmin_client.py` module exposes a small, explicit public API designed for
analytics, scripts, and MCP / agent-based integrations.

### `get_activities_in_range(start_date, end_date, activity_type=None, *, page_size=50, max_pages=None)`

Fetch **all Garmin activities** in the given date range (inclusive).

- Handles **pagination automatically** (no missing activities)
- Filters locally by date to remain compatible across library versions
- Returns **typed activity models** (running, cycling, swimming, or generic)

**Parameters**
- `start_date`, `end_date` (`YYYY-MM-DD`, `date`, or `datetime`)
- `activity_type` (optional): string or iterable of strings  
  Examples: `"running"`, `["road_biking", "virtual_ride"]`
- `page_size` (optional): number of activities per page (default: `50`)
- `max_pages` (optional): safety cap for paging (useful in MCP servers)

**Returns**
- `List[ActivitySummaryBase]` (typed dataclasses)

---

### `get_activity_details(activity_id)`

Fetch **best-effort detailed information** for a single activity.

⚠️ Garmin often returns **partial or empty payloads** for details depending on
activity type and device. Do **not** rely on this for core metrics like distance
or duration.

**Parameters**
- `activity_id` (`int` or `str`)

**Returns**
- `dict` with raw Garmin detail payload (numeric fields rounded where possible)

---

### `parse_activity_summary(summary_dict)`

Convert a **raw Garmin activity summary dict** into a typed activity model.

Used internally, but also useful when:
- loading cached Garmin JSON
- replaying stored payloads
- unit testing

**Returns**
- One of:
  - `RunningActivitySummary`
  - `CyclingActivitySummary`
  - `SwimmingActivitySummary`
  - `GenericActivitySummary`

---

### `init_api(auth=None)`

Initialize and authenticate a Garmin Connect API client.

- Reuses a cached session if available
- Falls back to username/password login

Mostly internal, but exposed for advanced use cases.

---

## Activity Models

All activities inherit from:

### `ActivitySummaryBase`

Common fields across all sports:
- `activity_id`
- `type_key`
- `activity_name`
- `begin_timestamp`
- `distance`
- `duration`
- `average_hr`
- `calories`
- `raw` (full original Garmin payload)

Specialized subclasses:
- `CyclingActivitySummary`
- `RunningActivitySummary`
- `SwimmingActivitySummary`
- `GenericActivitySummary` (fallback)

Each model provides:
- `.to_dict()` → stable, JSON-ready representation

