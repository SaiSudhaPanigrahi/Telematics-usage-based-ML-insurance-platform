
import os, sqlite3, string, random
from pathlib import Path

DB_PATH = Path(os.environ.get("UBI_DB_PATH", "data/ubi.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, display_name TEXT);
CREATE TABLE IF NOT EXISTS vehicles (id INTEGER PRIMARY KEY, user_id INTEGER, make TEXT, model TEXT, year INTEGER, safety_rating REAL, base_rate REAL);
CREATE TABLE IF NOT EXISTS trips (id TEXT PRIMARY KEY, user_id INTEGER, vehicle_id INTEGER, ts_utc TEXT, miles REAL, avg_speed REAL, max_speed REAL, harsh_brakes INTEGER, accel_var REAL, night_pct REAL, speeding_pct REAL, weather_risk REAL, processed INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS quotes (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, user_id INTEGER, vehicle_id INTEGER, base_component REAL, usage_component REAL, behavior_component REAL, context_component REAL, final_premium REAL, risk_score REAL, explanations TEXT);
CREATE TABLE IF NOT EXISTS rewards (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, user_id INTEGER, points INTEGER, reason TEXT, trip_id TEXT);
CREATE TABLE IF NOT EXISTS driver_summary (user_id INTEGER PRIMARY KEY, display_name TEXT, points INTEGER DEFAULT 0, badges INTEGER DEFAULT 0, risk_score REAL DEFAULT 50.0);
"""

def init():
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    cur.executescript(SCHEMA)
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        for u in range(1, 6):
            cur.execute("INSERT INTO users(id, display_name) VALUES (?, ?)", (u, f"Driver {u}"))
            cur.execute("INSERT OR REPLACE INTO driver_summary(user_id, display_name, points, badges, risk_score) VALUES (?,?,?,?,?)",
                        (u, f"Driver {u}", 0, 0, 50.0))
            for v in range(2):
                make = ["Toyota","Honda","Ford","Tesla","Subaru"][u % 5]
                model = ["Sedan","SUV","Hatch","EV","Crossover"][v % 5]
                year = 2018 + ((u+v) % 6)
                safety = 3.5 + (u+v)%2
                base = 70 + 10*((u+v)%3)
                cur.execute("INSERT INTO vehicles(user_id, make, model, year, safety_rating, base_rate) VALUES (?,?,?,?,?,?)",
                            (u, make, model, year, safety, base))
    con.commit()
    con.close()

if __name__ == "__main__":
    init()
    print(f"Initialized DB at {DB_PATH}")
