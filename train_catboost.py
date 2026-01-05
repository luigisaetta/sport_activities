"""
Train a CatBoost model to predict TRIMP from running activity data.
"""

import joblib
from catboost import CatBoostRegressor
import pandas as pd

from train_common import (
    DataConfig,
    load_and_prepare,
    time_split,
    print_dataset_summary,
    evaluate,
    RANDOM_SEED,
    COMMON_DROP_COLS,
    TEST_FRAC,
)


CSV_PATH = "running_activities_completed_gold_v1.csv"
MODEL_PATH = "catboost_trimp_model.joblib"

DROP_COLS = COMMON_DROP_COLS


def train_catboost(X_train, y_train, X_val, y_val, log_every: int = 10):
    """
    Train and return a CatBoost regression model.
    Parameters:
        X_train: Training features.
        y_train: Training target.
        X_val: Validation features.
        y_val: Validation target.
        log_every: Frequency of logging during training.
    Returns:
        Trained CatBoostRegressor model.
    """
    model = CatBoostRegressor(
        loss_function="MAE",
        eval_metric="MAE",
        iterations=5000,
        learning_rate=0.02,
        depth=6,
        random_seed=RANDOM_SEED,
        od_type="Iter",
        od_wait=500,
        verbose=log_every,
        allow_writing_files=False,
    )
    model.fit(X_train, y_train, eval_set=(X_val, y_val), use_best_model=True)
    return model


def show_feature_importance(model, feature_names):
    """
    Show feature importance from the trained Catboost model.
    Parameters:
        model: Trained LightGBM model.
        feature_names: List of feature names.
    Returns:
        None
    """
    importances = model.get_feature_importance(type="PredictionValuesChange")
    imp = pd.DataFrame({"feature": feature_names, "importance": importances})
    imp = imp.sort_values("importance", ascending=False)
    print("\n=== Feature importance ===")
    print(imp.to_string(index=False))


def main():
    """
    Main training routine.
    1. Load and prepare data.
    2. Time-based split into training and test sets.
    3. Train Catboost model.
    4. Evaluate model.
    5. Show feature importance.
    6. Save trained model to disk.
    Returns:
        None
    """
    test_frac = TEST_FRAC

    cfg = DataConfig(csv_path=CSV_PATH, drop_cols=DROP_COLS)
    X, y = load_and_prepare(cfg)
    X_train, X_test, y_train, y_test = time_split(X, y, test_frac=test_frac)

    print_dataset_summary(X, test_frac, len(X_train), len(X_test))

    print("Training CatBoost model...")
    model = train_catboost(X_train, y_train, X_test, y_test, log_every=10)

    print("\nEvaluating model...")
    evaluate(model, X_test, y_test)

    show_feature_importance(model, list(X.columns))

    joblib.dump(model, MODEL_PATH)
    print(f"\nSaved model to: {MODEL_PATH}\n")


if __name__ == "__main__":
    main()
