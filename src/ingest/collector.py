
from fastapi import FastAPI, Header, HTTPException
import sqlite3
from src.utils.config import DB_PATH, API_KEY
from src.ingest.schemas import Event

app = FastAPI(title="Telematics Collector")

def insert_event(ev: Event):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO raw_events (ts,user_id,trip_id,vehicle_id,speed,accel,brake,lat,lon,geohash) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (ev.ts, ev.user_id, ev.trip_id, ev.vehicle_id, ev.speed, ev.accel, ev.brake, ev.lat, ev.lon, ev.geohash),
    )
    con.commit(); con.close()

@app.post("/events")
def post_event(ev: Event, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")
    insert_event(ev)
    return {"ok": True}
