import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.metrics import mean_absolute_error, r2_score
import joblib

CSV_PATH = "running_activities_completed.csv"
MODEL_PATH = "lgbm_trimp_model.joblib"

# colonne da ignorare
DROP_COLS = ["activity_id", "end_time_gmt", "elapsed_duration"]
TARGET_COL = "trimp"


def load_and_prepare(csv_path: str) -> tuple[pd.DataFrame, pd.Series]:
    df = pd.read_csv(csv_path)

    # check minimi
    missing = [c for c in DROP_COLS + [TARGET_COL] if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in CSV: {missing}")

    # ordina temporalmente (split time-aware)
    df["end_time_gmt"] = pd.to_datetime(df["end_time_gmt"], errors="coerce")
    if df["end_time_gmt"].isna().any():
        bad = df[df["end_time_gmt"].isna()][["activity_id", "end_time_gmt"]].head(10)
        raise ValueError(f"Unparseable end_time_gmt values. Examples:\n{bad}")

    df = df.sort_values("end_time_gmt").reset_index(drop=True)

    # target
    y = df[TARGET_COL]

    # features: tutte le colonne tranne drop + target
    X = df.drop(columns=DROP_COLS + [TARGET_COL])

    # converti a numerico (se per caso arrivano stringhe)
    for col in X.columns:
        X[col] = pd.to_numeric(X[col], errors="coerce")

    # rimuovi righe senza target
    mask = y.notna()
    X = X.loc[mask].reset_index(drop=True)
    y = y.loc[mask].reset_index(drop=True)

    return X, y


def time_split(X: pd.DataFrame, y: pd.Series, test_frac: float = 0.2):
    n = len(X)
    if n < 20:
        raise ValueError(f"Too few rows ({n}) to train reliably. Need more data.")

    split = int(np.floor(n * (1 - test_frac)))
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]
    return X_train, X_test, y_train, y_test


def train_lgbm(X_train, y_train, X_val, y_val):
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
        random_state=42,
    )

    model.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        eval_metric="l1",  # MAE
        callbacks=[lgb.early_stopping(stopping_rounds=150, verbose=True)],
    )
    return model


def evaluate(model, X_test, y_test):
    pred = model.predict(X_test)

    mae = mean_absolute_error(y_test, pred)
    r2 = r2_score(y_test, pred)

    print("\n=== Evaluation (test) ===")
    print(f"MAE : {mae:.3f}")
    print(f"R2  : {r2:.3f}")

    # sanity check: range
    print(f"\nTRIMP true range: [{y_test.min():.1f}, {y_test.max():.1f}]")
    print(f"TRIMP pred range: [{pred.min():.1f}, {pred.max():.1f}]")


def show_feature_importance(model, feature_names):
    imp = pd.DataFrame(
        {"feature": feature_names, "importance": model.feature_importances_}
    ).sort_values("importance", ascending=False)

    print("\n=== Feature importance ===")
    print(imp.to_string(index=False))


def main():
    TEST_FRAC = 0.1

    X, y = load_and_prepare(CSV_PATH)
    X_train, X_test, y_train, y_test = time_split(X, y, test_frac=TEST_FRAC)

    print("---- Datasets ----")
    print("Test set fraction:", TEST_FRAC)
    print(f"Rows: {len(X)} | Train: {len(X_train)} | Test: {len(X_test)}")
    print(f"Features ({X.shape[1]}): {list(X.columns)}")
    print("-----------------")
    print("")

    print("Training LightGBM model...")
    model = train_lgbm(X_train, y_train, X_test, y_test)
    print("")

    print
    evaluate(model, X_test, y_test)
    print("")

    show_feature_importance(model, X.columns)

    # save model
    joblib.dump(model, MODEL_PATH)
    print(f"\nSaved model to: {MODEL_PATH}")


if __name__ == "__main__":
    main()
