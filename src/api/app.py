
from fastapi import FastAPI, Depends
import sqlite3
from src.api.auth import require_api_key
from src.models.risk_scoring import quote_for_user, risk_score_for_user, vehicle_list_for_user, driver_summary
from src.utils.config import DB_PATH

app = FastAPI(title="Telematics UBI Pro API")

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/risk/score")
def risk_score(user_id: int, vehicle_id: str = "", _=Depends(require_api_key)):
    score, meta = risk_score_for_user(user_id, vehicle_id or None)
    return {"user_id": user_id, "vehicle_id": vehicle_id or None, "risk_score": score, **meta}

@app.get("/pricing/quote")
def pricing_quote(user_id: int, vehicle_id: str = "", _=Depends(require_api_key)):
    q = quote_for_user(user_id, vehicle_id or None)
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT INTO quotes (ts,user_id,vehicle_id,risk_score,base_premium,dyn_component,final_premium) VALUES (datetime('now'),?,?,?,?,?,?)",
        (q['user_id'], q.get('vehicle_id'), q['risk_score'], q['base_premium'], q['dynamic_component'], q['final_monthly_premium'])
    )
    con.commit(); con.close()
    return q

@app.get("/vehicles")
def vehicles(user_id: int, _=Depends(require_api_key)):
    return vehicle_list_for_user(user_id)

@app.get("/driver/summary")
def summary(user_id: int, _=Depends(require_api_key)):
    return driver_summary(user_id)
