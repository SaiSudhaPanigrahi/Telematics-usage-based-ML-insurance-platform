
from pathlib import Path
import joblib
ART_DIR = Path("models/artifacts"); ART_DIR.mkdir(parents=True, exist_ok=True)
def save_model(model, name="rf_model.joblib"):
    joblib.dump(model, ART_DIR / name)
def load_model(name="rf_model.joblib"):
    p = ART_DIR / name
    return joblib.load(p) if p.exists() else None
