"""
drift_detection.py

Run Kolmogorov–Smirnov tests to detect distribution drift
between 2024 and 2025 for numeric features.

Date column: end_time_gmt (ISO format)
"""

import pandas as pd
import numpy as np
from scipy.stats import ks_2samp

# -----------------------
# Config
# -----------------------

CSV_PATH = "running_activities_completed_gold_v1.csv"

DATE_COLUMN = "end_time_gmt"  # ISO timestamp
TRIMP_COLUMN = "trimp"

# Columns to exclude from drift analysis
EXCLUDE_COLUMNS = {"year", "activity_id"}

ALPHA = 0.05


# -----------------------
# Load data
# -----------------------

df = pd.read_csv(CSV_PATH)

# Parse ISO timestamp and extract year
df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN], utc=True)
df["year"] = df[DATE_COLUMN].dt.year

# Keep only 2024 and 2025
df = df[df["year"].isin([2024, 2025])]

df_2024 = df[df["year"] == 2024]
df_2025 = df[df["year"] == 2025]

print(f"Samples 2024: {len(df_2024)}")
print(f"Samples 2025: {len(df_2025)}\n")


# -----------------------
# Select numeric features
# -----------------------

numeric_cols = df.select_dtypes(include=[np.number]).columns.difference(EXCLUDE_COLUMNS)

# Defensive check: ensure TRIMP is included
if TRIMP_COLUMN not in numeric_cols:
    numeric_cols = numeric_cols.append(pd.Index([TRIMP_COLUMN]))


# -----------------------
# KS test
# -----------------------

results = []

for col in numeric_cols:
    x = df_2024[col].dropna()
    y = df_2025[col].dropna()

    # Skip if insufficient data
    if len(x) < 20 or len(y) < 20:
        continue

    ks_stat, p_value = ks_2samp(x, y)

    results.append(
        {
            "feature": col,
            "ks_statistic": ks_stat,
            "p_value": p_value,
            "drift_detected": p_value < ALPHA,
            "mean_2024": x.mean(),
            "mean_2025": y.mean(),
            "relative_mean_change_%": 100 * (y.mean() - x.mean()) / x.mean(),
        }
    )


# -----------------------
# Results
# -----------------------

results_df = pd.DataFrame(results).sort_values("p_value").reset_index(drop=True)

pd.set_option("display.float_format", "{:.4f}".format)

print("=== KS Drift Test Results (2024 vs 2025) ===\n")
print(results_df)

results_df.to_csv("ks_drift_results_2024_vs_2025.csv", index=False)
print("\nResults saved to ks_drift_results_2024_vs_2025.csv")
