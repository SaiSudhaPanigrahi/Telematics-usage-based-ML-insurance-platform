
import os, sqlite3
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

API_KEY = os.environ.get("UBI_API_KEY", "dev_api_key_change_me")
DB_PATH = Path(os.environ.get("UBI_DB_PATH", "data/ubi.db"))

app = FastAPI(title="Telematics UBI Pro", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def check_key(x_api_key: str | None):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

def read_sql(sql, params=()):
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description] if cur.description else []
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    con.close()
    return rows

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/vehicles")
def vehicles(user_id: int, x_api_key: str | None = Header(default=None, convert_underscores=False)):
    check_key(x_api_key)
    return read_sql("SELECT id, user_id, make, model, year, safety_rating, base_rate FROM vehicles WHERE user_id=? ORDER BY id", (user_id,))

@app.get("/pricing/quote")
def quote(user_id: int, vehicle_id: int | None = None, x_api_key: str | None = Header(default=None, convert_underscores=False)):
    check_key(x_api_key)
    if vehicle_id:
        q = "SELECT * FROM quotes WHERE user_id=? AND vehicle_id=? ORDER BY created_at DESC LIMIT 1"
        rows = read_sql(q, (user_id, vehicle_id))
    else:
        q = "SELECT * FROM quotes WHERE user_id=? ORDER BY created_at DESC LIMIT 1"
        rows = read_sql(q, (user_id,))
    return rows[0] if rows else {"message": "No quote yet"}

@app.get("/driver/summary")
def summary(user_id: int, x_api_key: str | None = Header(default=None, convert_underscores=False)):
    check_key(x_api_key)
    r = read_sql("SELECT user_id, display_name, points, badges, risk_score FROM driver_summary WHERE user_id=?", (user_id,))
    return r[0] if r else {}
