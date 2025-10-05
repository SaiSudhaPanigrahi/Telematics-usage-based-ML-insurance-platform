
import argparse, sqlite3, pandas as pd, matplotlib.pyplot as plt, os
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score, accuracy_score
from sklearn.calibration import calibration_curve
from src.utils.config import DB_PATH
from src.models.model_registry import save_model

FEATS = ["miles","avg_speed","max_speed","harsh_brake_ct","accel_var","night_pct","speeding_pct","weather_risk"]

def load_training(min_trips=50):
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT f.trip_id, f.user_id, f.vehicle_id, f.miles, f.avg_speed, f.max_speed, f.harsh_brake_ct, f.accel_var, f.night_pct, f.speeding_pct, f.weather_risk, l.incident "
        "FROM features f JOIN labels l ON f.trip_id = l.trip_id",
        con)
    con.close()
    if len(df) < min_trips:
        print(f"Not enough trips ({len(df)}) — collect more.")
    return df

def train(min_trips=50):
    df = load_training(min_trips)
    if df is None or df.empty or len(df) < min_trips:
        return
    X, y = df[FEATS], df["incident"]
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)
    clf = RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42, class_weight="balanced")
    clf.fit(Xtr, ytr)
    p = clf.predict_proba(Xte)[:,1]
    auc = roc_auc_score(yte, p)
    acc = accuracy_score(yte, (p>0.5).astype(int))
    print(f"ROC-AUC={auc:.3f} ACC={acc:.3f} on {len(Xte)} eval samples")
    prob_true, prob_pred = calibration_curve(yte, p, n_bins=10)
    os.makedirs("models/artifacts", exist_ok=True)
    plt.figure(); plt.plot(prob_pred, prob_true, marker="o"); plt.plot([0,1],[0,1], linestyle="--")
    plt.title("Calibration curve"); plt.xlabel("Mean predicted prob"); plt.ylabel("Fraction of positives")
    plt.savefig("models/artifacts/calibration.png", bbox_inches="tight")
    save_model(clf); print("Saved model → models/artifacts/rf_model.joblib")

def evaluate_only():
    df = load_training(min_trips=1)
    if df is None or df.empty:
        print("No data to evaluate."); return
    from src.models.model_registry import load_model
    clf = load_model()
    if clf is None:
        print("No model found."); return
    X, y = df[FEATS], df["incident"]
    p = clf.predict_proba(X)[:,1]
    auc = roc_auc_score(y, p)
    acc = accuracy_score(y, (p>0.5).astype(int))
    print(f"[Full] ROC-AUC={auc:.3f} ACC={acc:.3f} on {len(X)} samples")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-trips", type=int, default=50)
    ap.add_argument("--evaluate-only", action="store_true")
    args = ap.parse_args()
    evaluate_only() if args.evaluate_only else train(args.min_trips)
