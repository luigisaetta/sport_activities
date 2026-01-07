"""
Train a LightGBM model to predict TRIMP from running activity data.
"""

import joblib
import lightgbm as lgb
from lightgbm.callback import log_evaluation
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
MODEL_PATH = "lgbm_trimp_model.joblib"

# Decide once: if you are dropping distance, do it for both scripts
DROP_COLS = COMMON_DROP_COLS + [
    # remove distance, improve results slightly
    "distance",
]


def train_lgbm(X_train, y_train, X_val, y_val):
    """
    Train and return a LightGBM regression model.
    Parameters:
        X_train: Training features.
        y_train: Training target.
        X_val: Validation features.
        y_val: Validation target.
    Returns:
        Trained LightGBM model.
    """
    model = lgb.LGBMRegressor(
        objective="regression",
        n_estimators=5000,
        learning_rate=0.02,
        num_leaves=31,
        max_depth=-1,
        min_child_samples=20,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.0,
        reg_lambda=0.0,
        random_state=RANDOM_SEED,
        verbosity=-1,
    )

    model.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        eval_metric="l1",
        callbacks=[
            lgb.early_stopping(stopping_rounds=500, verbose=True),
            log_evaluation(period=10),
        ],
    )
    return model


def show_feature_importance(model, feature_names):
    """
    Show feature importance from the trained LightGBM model.
    Parameters:
        model: Trained LightGBM model.
        feature_names: List of feature names.
    Returns:
        None
    """
    imp = pd.DataFrame(
        {"feature": feature_names, "importance": model.feature_importances_}
    )
    imp = imp.sort_values("importance", ascending=False)
    print("\n=== Feature importance ===")
    print(imp.to_string(index=False))


def main():
    """
    Main training routine.
    1. Load and prepare data.
    2. Time-based split into training and test sets.
    3. Train LightGBM model.
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

    print("Training LightGBM model...")
    model = train_lgbm(X_train, y_train, X_test, y_test)

    print("\nEvaluating model...")
    evaluate(model, X_test, y_test)

    show_feature_importance(model, X.columns)

    joblib.dump(model, MODEL_PATH)
    print(f"\nSaved model to: {MODEL_PATH}\n")


if __name__ == "__main__":
    main()
