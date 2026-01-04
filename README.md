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

payload = [a.to_public_dict() for a in activities]

print(json.dumps(payload, indent=2, ensure_ascii=False))
```

#### Restrict to an activity's type
```
import json
from garmin_client import get_activities_in_range

activities = get_activities_in_range("2025-06-01", "2025-06-30", activity_type="road_biking")

# eventually limit to certain activity types
payload = [a.to_public_dict() for a in activities]

print(json.dumps(payload, indent=2, ensure_ascii=False))
```

**Activities' types:**
- running
- road_biking
- indoor_cycling
- virtual_ride
- lap_swimming
- yoga

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

## Machine Learning: TRIMP Prediction (Running)

This repository also includes an **experimental but rigorous ML workflow** to train regression models that **predict TRIMP (Training Impulse)** for running activities using aggregated Garmin metrics.

The goal is **not** to replace physiological models, but to:
- study how well TRIMP can be approximated from *summary-level* data
- compare different gradient boosting algorithms
- build a **robust, reproducible baseline** for future experimentation

The workflow is intentionally conservative:
- **time-aware splits** (no random shuffling)
- explicit **data cleaning and anomaly removal**
- focus on **generalization**, not best-case MAE

---

## Dataset Preparation (Gold Version)

Model training uses a curated dataset:
```
running_activities_completed_gold_v1.csv
```

### Key characteristics
- Years included: **2024–2025**
- Only **running** activities
- Activities with:
  - implausible duration (seconds-long)
  - corrupted or extreme TRIMP values  
  were **removed**

### Feature selection
The following columns are **excluded** from training:
- `activity_id`
- `end_time_gmt`
- `elapsed_duration` (redundant / pause-heavy)
- `max_speed`
- `avg_power` (too device-dependent)

The remaining numeric fields are used as model features, with:
- `trimp` as the regression target

This frozen dataset is referred to as the **“gold” dataset** and is versioned to ensure reproducibility.

---

## Model 1: LightGBM Regressor

A first model is trained using **LightGBM**, with the following design choices:

- Gradient Boosting Decision Trees
- Time-based train/test split (last 10% as test)
- Early stopping on **validation MAE (L1)**
- Conservative regularization to limit overfitting

### Observed performance
- MAE ≈ **11**
- R² ≈ **0.74**

LightGBM performs well, but tends to:
- concentrate importance on a smaller subset of features
- be more sensitive to collinearity and noise in small datasets

This model serves as a **strong baseline**.

---

## Model 2: CatBoost Regressor (Gold Model)

A second model is trained using **CatBoost**, keeping the pipeline and split strategy identical to LightGBM.

### Why CatBoost
CatBoost was evaluated because it:
- handles correlated features more gracefully
- is more stable on small / medium datasets
- natively optimizes **MAE (L1 loss)**

### Observed performance
- MAE ≈ **10.4**
- R² ≈ **0.77**

Compared to LightGBM, CatBoost:
- improves MAE by ~**1 TRIMP**
- shows **more balanced feature importance**
- better reflects physiological intuition (HR, cadence, stride matter)

For these reasons, **CatBoost is considered the current “gold” model**.

---

## Model Comparison Summary

| Model      | MAE ↓ | R² ↑ | Notes |
|------------|------:|-----:|-------|
| LightGBM   | ~11.4 | 0.74 | Strong baseline |
| CatBoost   | **~10.4** | **0.77** | Best overall |

The improvement is modest but **consistent and meaningful** given:
- noisy real-world physiological data
- limited sample size
- aggregated (non–time-series) features

---

## Scope and Limitations

Important constraints to keep in mind:

- Models use **activity summaries only** (no HR time series)
- TRIMP itself is a **derived metric**, not ground truth
- Performance is athlete-specific and **not universal**

These models are best seen as:
- analytical tools
- data quality validators
- baselines for future extensions (e.g. time-series, zones, decoupling)
