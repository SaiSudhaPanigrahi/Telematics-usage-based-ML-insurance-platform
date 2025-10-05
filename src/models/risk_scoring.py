
import sqlite3, pandas as pd
from src.models.model_registry import load_model
from src.utils.config import DB_PATH

FEATS = ["miles","avg_speed","max_speed","harsh_brake_ct","accel_var","night_pct","speeding_pct","weather_risk"]

def vehicle_list_for_user(user_id:int):
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT vehicle_id, vin, make, model, year, type, safety_rating, base_rate FROM vehicles WHERE user_id=?", con, params=(user_id,))
    con.close()
    return df.to_dict(orient="records")

def latest_user_features(user_id:int, vehicle_id:str=None):
    con = sqlite3.connect(DB_PATH)
    if vehicle_id:
        df = pd.read_sql_query("SELECT * FROM features WHERE user_id=? AND vehicle_id=? ORDER BY rowid DESC LIMIT 50",
                               con, params=(user_id, vehicle_id))
    else:
        df = pd.read_sql_query("SELECT * FROM features WHERE user_id=? ORDER BY rowid DESC LIMIT 50",
                               con, params=(user_id,))
    con.close()
    return df

def _vehicle_factor(user_id:int, vehicle_id:str|None):
    con = sqlite3.connect(DB_PATH)
    if vehicle_id:
        q = "SELECT base_rate, safety_rating FROM vehicles WHERE user_id=? AND vehicle_id=?"
        df = pd.read_sql_query(q, con, params=(user_id, vehicle_id))
    else:
        q = "SELECT AVG(base_rate) AS base_rate, AVG(safety_rating) AS safety_rating FROM vehicles WHERE user_id=?"
        df = pd.read_sql_query(q, con, params=(user_id,))
    con.close()
    if df.empty: return 80.0, 0.9
    return float(df.iloc[0]['base_rate']), float(df.iloc[0]['safety_rating'])

def risk_score_for_user(user_id:int, vehicle_id:str|None=None):
    clf = load_model()
    df = latest_user_features(user_id, vehicle_id)
    if df.empty:
        return 50.0, {"explanations": ["insufficient data → neutral score"]}
    X = df[FEATS]
    if clf is not None:
        p = float(clf.predict_proba(X).mean(axis=0)[1])
        base = 100*p
    else:
        base = float(40 + 45*df['speeding_pct'].mean() + 25*df['night_pct'].mean() + 2*df['harsh_brake_ct'].mean() + 10*df['weather_risk'].mean())
    base = max(0.0, min(100.0, base))
    _, safety = _vehicle_factor(user_id, vehicle_id)
    adj = base * (1.0 - 0.1*(safety-0.8))
    score = round(adj, 1)
    expl = []
    if df['speeding_pct'].mean() > 0.2: expl.append("speeding_pct: high")
    if df['night_pct'].mean() > 0.3: expl.append("night_pct: high")
    if df['harsh_brake_ct'].mean() > 3: expl.append("harsh_braking: high")
    if df['weather_risk'].mean() > 0.3: expl.append("context: adverse weather")
    if not expl: expl.append("overall: average")
    return score, {"explanations": expl}

def quote_for_user(user_id:int, vehicle_id:str|None=None, base_premium:float|None=None)->dict:
    veh_base, safety = _vehicle_factor(user_id, vehicle_id)
    base_premium = base_premium or veh_base
    score, meta = risk_score_for_user(user_id, vehicle_id)
    con = sqlite3.connect(DB_PATH)
    if vehicle_id:
        miles = pd.read_sql_query("SELECT COALESCE(SUM(miles),0) AS m FROM features WHERE user_id=? AND vehicle_id=?",
                                  con, params=(user_id, vehicle_id)).iloc[0]['m']
    else:
        miles = pd.read_sql_query("SELECT COALESCE(SUM(miles),0) AS m FROM features WHERE user_id=?",
                                  con, params=(user_id,)).iloc[0]['m']
    con.close()
    dyn_usage = 0.015 * miles
    behavior = (-0.05 + 0.30 * (score/100.0)) * base_premium
    context = 0.03 * base_premium * min(1.0, score/100.0)
    final = round(base_premium + dyn_usage + behavior + context, 2)
    return dict(user_id=user_id, vehicle_id=vehicle_id, risk_score=score,
                base_premium=round(base_premium,2), dynamic_component=round(dyn_usage,2),
                context_component=round(context,2), final_monthly_premium=final,
                explanations=meta.get("explanations", []))

def driver_summary(user_id:int):
    con = sqlite3.connect(DB_PATH)
    agg = pd.read_sql_query(
        "SELECT vehicle_id, COUNT(*) AS trips, SUM(miles) AS miles, AVG(speeding_pct) AS avg_speeding, AVG(night_pct) AS avg_night, AVG(harsh_brake_ct) AS avg_brake "
        "FROM features WHERE user_id=? GROUP BY vehicle_id", con, params=(user_id,))
    rewards = pd.read_sql_query("SELECT * FROM rewards WHERE user_id=? ORDER BY ts DESC LIMIT 50", con, params=(user_id,))
    con.close()
    return dict(per_vehicle=agg.to_dict(orient="records"), rewards=rewards.to_dict(orient="records"))
