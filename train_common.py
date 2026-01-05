"""
train_common.py

Shared utilities for training TRIMP regression models.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score

COMMON_DROP_COLS = [
    "activity_id",
    "end_time_gmt",
    "elapsed_duration",
    "max_speed",
    "avg_power",
]

# shared configs
RANDOM_SEED = 42
TEST_FRAC = 0.1


@dataclass(frozen=True)
class DataConfig:
    """
    Configuration for loading and preparing data.
    """

    csv_path: str
    target_col: str = "trimp"
    drop_cols: Tuple[str, ...] = tuple(COMMON_DROP_COLS)


def load_and_prepare(cfg: DataConfig) -> tuple[pd.DataFrame, pd.Series]:
    """
    Load CSV and prepare (X, y).
    - Ensures required columns exist
    - Parses end_time_gmt and sorts chronologically (for time split)
    - Drops cfg.drop_cols and target
    - Coerces features to numeric
    - Removes rows with missing target
    """
    df = pd.read_csv(cfg.csv_path)

    required = list(cfg.drop_cols) + [cfg.target_col]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in CSV: {missing}")

    df["end_time_gmt"] = pd.to_datetime(df["end_time_gmt"], errors="coerce")
    if df["end_time_gmt"].isna().any():
        bad = df[df["end_time_gmt"].isna()][["activity_id", "end_time_gmt"]].head(10)
        raise ValueError(f"Unparseable end_time_gmt values. Examples:\n{bad}")

    df = df.sort_values("end_time_gmt").reset_index(drop=True)

    y = df[cfg.target_col]
    X = df.drop(columns=list(cfg.drop_cols) + [cfg.target_col])

    for col in X.columns:
        X[col] = pd.to_numeric(X[col], errors="coerce")

    mask = y.notna()
    X = X.loc[mask].reset_index(drop=True)
    y = y.loc[mask].reset_index(drop=True)

    return X, y


def time_split(
    X: pd.DataFrame,
    y: pd.Series,
    test_frac: float = 0.2,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """
    Time-based split: last `test_frac` fraction becomes test.
    """
    n = len(X)
    if n < 20:
        raise ValueError(f"Too few rows ({n}) to train reliably. Need more data.")

    split = int(np.floor(n * (1 - test_frac)))
    return X.iloc[:split], X.iloc[split:], y.iloc[:split], y.iloc[split:]


def print_dataset_summary(
    X: pd.DataFrame, test_frac: float, n_train: int, n_test: int
) -> None:
    """
    Print dataset summary.
    """

    print("")
    print("=== Datasets ===\n")
    print("Test set fraction:", test_frac)
    print(f"Rows: {len(X)} | Train: {n_train} | Test: {n_test}")
    print(f"Features ({X.shape[1]} columns):")
    for col in X.columns:
        print(f"- {col}")
    print("")
    print("===============\n")


def evaluate(model, X_test: pd.DataFrame, y_test: pd.Series) -> tuple[float, float]:
    """
    Evaluate model on test set. Returns (mae, r2).
    """
    pred = model.predict(X_test)

    mae = mean_absolute_error(y_test, pred)
    r2 = r2_score(y_test, pred)

    print("\n=== Evaluation (test) ===")
    print(f"MAE : {mae:.3f}")
    print(f"R2  : {r2:.3f}")
    print(f"\nTRIMP true range: [{y_test.min():.1f}, {y_test.max():.1f}]")
    print(f"TRIMP pred range: [{pred.min():.1f}, {pred.max():.1f}]")

    return mae, r2
