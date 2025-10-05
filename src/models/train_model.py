# src/models/train_model.py
# Train a baseline ML model from the local SQLite DB and write artifacts.
# Usage:
#   python -m src.models.train_model --min-trips 200
# or:
#   python src/models/train_model.py --min-trips 200

from __future__ import annotations
import argparse
import os
import sqlite3
from pathlib import Path
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import roc_auc_score, accuracy_score
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore", category=UserWarning)

# --------- configurable defaults ----------
DEFAULT_DB = os.environ.get("UBI_DB_PATH", "data/ubi.db")
ARTIFACTS_DIR = Path("models/artifacts")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

# Feature candidates that often exist in this POC
CANDIDATE_FEATURES = [
    "miles",
    "avg_speed",
    "max_speed",
    "speeding_pct",
    "night_pct",
    "harsh_brake_ct",
    "accel_var",
    "weather_risk",
]

# Potential label column names if your processor already wrote a label
CANDIDATE_LABELS = ["label", "incident", "crash_flag", "target", "y"]


def get_columns(conn, table):
    q = f"PRAGMA table_info({table});"
    cols = pd.read_sql(q, conn)["name"].tolist()
    return cols


def find_source_table(conn):
    """Try common table names in this project."""
    tables = pd.read_sql(
        "SELECT name FROM sqlite_master WHERE type='table';", conn
    )["name"].tolist()

    # By priority
    for name in ["trip_features", "trips", "features"]:
        if name in tables:
            return name
    # fallback: any table that contains at least a few candidate features
    for t in tables:
        cols = set(get_columns(conn, t))
        if len(cols.intersection(CANDIDATE_FEATURES)) >= 3:
            return t
    raise RuntimeError(
        "Could not find a table with suitable columns. "
        "Check your DB or run the simulator/processor longer."
    )


def load_dataframe(db_path: str) -> pd.DataFrame:
    if not Path(db_path).exists():
        raise FileNotFoundError(
            f"DB not found at {db_path}. Set UBI_DB_PATH or run python dev.py first."
        )
    conn = sqlite3.connect(db_path)
    table = find_source_table(conn)
    cols = get_columns(conn, table)

    # select only needed columns if present
    select_cols = [c for c in CANDIDATE_FEATURES if c in cols]
    # bring along any obvious label if present
    label_col = next((c for c in CANDIDATE_LABELS if c in cols), None)

    base_cols = select_cols.copy()
    if label_col:
        base_cols.append(label_col)

    if not base_cols:
        # last resort: load all and we’ll prune later
        df = pd.read_sql(f"SELECT * FROM {table};", conn)
    else:
        df = pd.read_sql(
            f"SELECT {', '.join(base_cols)} FROM {table};", conn
        )

    conn.close()

    # Ensure numeric
    for c in select_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Drop extreme NaNs
    df = df.dropna(subset=select_cols, how="any")

    # If no label provided, create a weak label from behavior thresholds
    if label_col is None:
        lbl = (
            (df.get("speeding_pct", 0) > 40)
            | (df.get("harsh_brake_ct", 0) > 3)
            | (df.get("night_pct", 0) > 60)
        ).astype(int)
        df["label"] = lbl
        label_col = "label"

    # Filter to reasonable numeric ranges (optional hygiene)
    if "speeding_pct" in df:
        df = df[(df["speeding_pct"] >= 0) & (df["speeding_pct"] <= 100)]
    if "night_pct" in df:
        df = df[(df["night_pct"] >= 0) & (df["night_pct"] <= 100)]

    # Guard: at least some positives/negatives
    if df[label_col].nunique() < 2:
        raise RuntimeError(
            "Label has only one class. Let the simulator run longer or lower thresholds."
        )

    X_cols = [c for c in select_cols if c in df.columns]
    if len(X_cols) < 3:
        raise RuntimeError(
            f"Found too few usable feature columns ({X_cols}). "
            "Let the processor run longer or check DB schema."
        )

    X = df[X_cols].astype(float)
    y = df[label_col].astype(int)

    return X, y, X_cols


def train_and_calibrate(X, y, random_state=42):
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=random_state, stratify=y
    )
    base = RandomForestClassifier(
        n_estimators=300, max_depth=None, n_jobs=-1, random_state=random_state
    )
    base.fit(X_train, y_train)

    # Calibrate probabilities for better reliability
    clf = CalibratedClassifierCV(base, cv=3, method="sigmoid")
    clf.fit(X_train, y_train)

    # Metrics
    y_pred = clf.predict(X_test)
    y_proba = clf.predict_proba(X_test)[:, 1]
    acc = accuracy_score(y_test, y_pred)
    try:
        auc = roc_auc_score(y_test, y_proba)
    except Exception:
        auc = float("nan")

    return clf, (acc, auc), (X_test, y_test, y_proba)


def plot_calibration(y_true, y_proba, out_path: Path):
    # reliability-like curve via binning
    bins = np.linspace(0.0, 1.0, 11)
    idx = np.digitize(y_proba, bins) - 1
    df = pd.DataFrame({"y": y_true, "p": y_proba, "bin": idx})
    g = df.groupby("bin").agg(rate=("y", "mean"), conf=("p", "mean")).dropna()

    plt.figure(figsize=(6, 6))
    plt.plot([0, 1], [0, 1], "--", label="Ideal")
    plt.plot(g["conf"], g["rate"], marker="o", label="Model")
    plt.xlabel("Predicted probability")
    plt.ylabel("Observed rate")
    plt.title("Calibration (Reliability) Curve")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def plot_importances(model, feature_names, out_path: Path):
    # Works for RF; for Calibrated wrapper, get underlying estimator
    est = getattr(model, "base_estimator", None) or getattr(
        model, "estimator", None
    )
    if hasattr(est, "feature_importances_"):
        imps = est.feature_importances_
        order = np.argsort(imps)[::-1]
        names = np.array(feature_names)[order]
        vals = imps[order]
        plt.figure(figsize=(8, 5))
        plt.bar(range(len(vals)), vals)
        plt.xticks(range(len(vals)), names, rotation=45, ha="right")
        plt.title("Feature Importances")
        plt.tight_layout()
        plt.savefig(out_path)
        plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=DEFAULT_DB, help="Path to SQLite DB")
    parser.add_argument("--min-trips", type=int, default=200)
    args = parser.parse_args()

    # Quick size check
    if not Path(args.db).exists():
        raise FileNotFoundError(
            f"{args.db} not found. Run `python dev.py` first to generate data."
        )
    with sqlite3.connect(args.db) as conn:
        n_trips = pd.read_sql(
            "SELECT count(*) as n FROM sqlite_master WHERE type='table';", conn
        )
    # We won’t depend on an exact table count—just proceed and rely on data load guardrails.

    X, y, feat_names = load_dataframe(args.db)
    if len(X) < args.min_trips:
        raise RuntimeError(
            f"Found only {len(X)} rows (< --min-trips {args.min_trips}). "
            "Let the simulator/processor run longer."
        )

    model, (acc, auc), (X_test, y_test, y_proba) = train_and_calibrate(X, y)

    # Save artifacts
    model_path = ARTIFACTS_DIR / "model.joblib"
    joblib.dump(model, model_path)

    calib_path = ARTIFACTS_DIR / "calibration.png"
    plot_calibration(y_test, y_proba, calib_path)

    imp_path = ARTIFACTS_DIR / "feature_importances.png"
    plot_importances(model, feat_names, imp_path)

    # Print metrics plainly
    print("\n=== Training Summary ===")
    print(f"Rows used: {len(X)}")
    print(f"Features: {feat_names}")
    print(f"Accuracy: {acc:.4f}")
    print(f"ROC-AUC : {auc:.4f}")
    print(f"Saved model to: {model_path}")
    print(f"Saved plots : {calib_path}, {imp_path}")
    print("\nTip: To use this model at runtime:")
    print("Mac/Linux: export UBI_USE_ML=1 && python dev.py")
    print("Windows  : set UBI_USE_ML=1 && python dev.py")


if __name__ == "__main__":
    main()

