"""
Train a CatBoost model to predict TRIMP from running activity data.
(Equivalent pipeline to the provided LightGBM script.)
"""
import pandas as pd
import numpy as np
from catboost import CatBoostRegressor
from sklearn.metrics import mean_absolute_error, r2_score
import joblib

# configs
RANDOM_SEED = 42

CSV_PATH = "running_activities_completed_gold_v1.csv"
MODEL_PATH = "catboost_trimp_model.joblib"

# columns to ignore
DROP_COLS = ["activity_id", "end_time_gmt", "elapsed_duration", "max_speed", "avg_power"]
TARGET_COL = "trimp"


def load_and_prepare(csv_path: str) -> tuple[pd.DataFrame, pd.Series]:
    """
    Load CSV and prepare features and target.
    """
    df = pd.read_csv(csv_path)

    missing = [c for c in DROP_COLS + [TARGET_COL] if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in CSV: {missing}")

    # parse and sort by time for time-based splitting
    df["end_time_gmt"] = pd.to_datetime(df["end_time_gmt"], errors="coerce")
    if df["end_time_gmt"].isna().any():
        bad = df[df["end_time_gmt"].isna()][["activity_id", "end_time_gmt"]].head(10)
        raise ValueError(f"Unparseable end_time_gmt values. Examples:\n{bad}")

    df = df.sort_values("end_time_gmt").reset_index(drop=True)

    # target
    y = df[TARGET_COL]

    # features: all columns except drop + target
    X = df.drop(columns=DROP_COLS + [TARGET_COL])

    # ensure numeric
    for col in X.columns:
        X[col] = pd.to_numeric(X[col], errors="coerce")

    # drop rows without target
    mask = y.notna()
    X = X.loc[mask].reset_index(drop=True)
    y = y.loc[mask].reset_index(drop=True)

    return X, y


def time_split(X: pd.DataFrame, y: pd.Series, test_frac: float = 0.2):
    """
    Time-based split into train and test sets.
    The last `test_frac` fraction of data is used as test set.
    """
    n = len(X)
    if n < 20:
        raise ValueError(f"Too few rows ({n}) to train reliably. Need more data.")

    split = int(np.floor(n * (1 - test_frac)))
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]
    return X_train, X_test, y_train, y_test


def train_catboost(X_train, y_train, X_val, y_val, log_every: int = 10):
    """
    Train CatBoost model with early stopping and periodic logging.
    """
    # CatBoost handles NaNs; keep them if present.
    model = CatBoostRegressor(
        loss_function="MAE",        # optimize MAE (L1)
        eval_metric="MAE",          # choose best iteration by MAE
        iterations=5000,
        learning_rate=0.02,
        depth=6,                    # roughly comparable complexity to num_leaves~31
        random_seed=RANDOM_SEED,
        od_type="Iter",             # overfitting detector
        od_wait=500,                # early stopping patience (like stopping_rounds)
        verbose=log_every,          # print every N iterations
        allow_writing_files=False,  # avoid catboost_info/ output
    )

    model.fit(
        X_train,
        y_train,
        eval_set=(X_val, y_val),
        use_best_model=True
    )
    return model


def evaluate(model, X_test, y_test):
    """
    Evaluate model on test set and print metrics.
    """
    pred = model.predict(X_test)

    mae = mean_absolute_error(y_test, pred)
    r2 = r2_score(y_test, pred)

    print("\n=== Evaluation (test) ===")
    print(f"MAE : {mae:.3f}")
    print(f"R2  : {r2:.3f}")

    print(f"\nTRIMP true range: [{y_test.min():.1f}, {y_test.max():.1f}]")
    print(f"TRIMP pred range: [{pred.min():.1f}, {pred.max():.1f}]")


def show_feature_importance(model, feature_names):
    """
    Show feature importance from trained model.
    """
    # PredictionValuesChange is a stable default for regression
    importances = model.get_feature_importance(type="PredictionValuesChange")
    imp = pd.DataFrame({"feature": feature_names, "importance": importances}).sort_values(
        "importance", ascending=False
    )

    print("\n=== Feature importance ===")
    print(imp.to_string(index=False))


def main():
    """
    Main training pipeline.
    """
    TEST_FRAC = 0.1

    X, y = load_and_prepare(CSV_PATH)
    X_train, X_test, y_train, y_test = time_split(X, y, test_frac=TEST_FRAC)

    print("")
    print("=== Datasets ===\n")
    print("Test set fraction:", TEST_FRAC)
    print(f"Rows: {len(X)} | Train: {len(X_train)} | Test: {len(X_test)}")
    print(f"Features ({X.shape[1]} columns):")
    for col in X.columns:
        print(f"- {col}")
    print("")
    print("===============\n")

    print("Training CatBoost model...")
    model = train_catboost(X_train, y_train, X_test, y_test, log_every=10)
    print("")

    print("Evaluating model...")
    evaluate(model, X_test, y_test)
    print("")

    show_feature_importance(model, list(X.columns))

    # Save model
    # CatBoost models can be saved with model.save_model(...), but joblib works too for python usage.
    joblib.dump(model, MODEL_PATH)
    print(f"\nSaved model to: {MODEL_PATH}\n")


if __name__ == "__main__":
    main()
