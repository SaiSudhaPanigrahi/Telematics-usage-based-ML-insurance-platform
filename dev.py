#!/usr/bin/env python3
# dev.py — one-click launcher with auto-free-ports + multi-service orchestration

import os
import sys
import time
import sqlite3
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
ENV = os.environ.copy()

# Defaults (can be overridden via environment variables or .env)
ENV.setdefault("UBI_DB_PATH", str(ROOT / "data" / "ubi.db"))
ENV.setdefault("UBI_API_KEY", "dev_api_key_change_me")
ENV.setdefault("UBI_SECRET_KEY", "dev_secret")

# ---------- Utilities ----------

def pip_install():
    """Install/verify project dependencies."""
    req = ROOT / "requirements.txt"
    print("➡ Installing/Verifying dependencies from", req)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(req)])

def init_db():
    """Create the SQLite schema if it doesn't exist."""
    db_path = ENV["UBI_DB_PATH"]
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    print("➡ Initializing DB at", db_path)
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.executescript(
        # raw minute-level events
        "CREATE TABLE IF NOT EXISTS raw_events ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  ts TEXT NOT NULL,"
        "  user_id INTEGER NOT NULL,"
        "  trip_id TEXT NOT NULL,"
        "  vehicle_id TEXT NOT NULL,"
        "  speed REAL, accel REAL, brake REAL,"
        "  lat REAL, lon REAL, geohash TEXT"
        ");"
        # one row per trip
        "CREATE TABLE IF NOT EXISTS trips ("
        "  trip_id TEXT PRIMARY KEY,"
        "  user_id INTEGER,"
        "  vehicle_id TEXT,"
        "  start_ts TEXT, end_ts TEXT,"
        "  miles REAL"
        ");"
        # engineered features per trip
        "CREATE TABLE IF NOT EXISTS features ("
        "  trip_id TEXT PRIMARY KEY,"
        "  user_id INTEGER,"
        "  vehicle_id TEXT,"
        "  miles REAL, avg_speed REAL, max_speed REAL,"
        "  harsh_brake_ct INTEGER, accel_var REAL,"
        "  night_pct REAL, speeding_pct REAL,"
        "  weather_risk REAL"
        ");"
        # weak labels for training
        "CREATE TABLE IF NOT EXISTS labels ("
        "  trip_id TEXT PRIMARY KEY,"
        "  incident INTEGER"
        ");"
        # quote history
        "CREATE TABLE IF NOT EXISTS quotes ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  ts TEXT, user_id INTEGER, vehicle_id TEXT,"
        "  risk_score REAL, base_premium REAL,"
        "  dyn_component REAL, final_premium REAL"
        ");"
        # vehicles & policies (multi-vehicle)
        "CREATE TABLE IF NOT EXISTS vehicles ("
        "  vehicle_id TEXT PRIMARY KEY,"
        "  user_id INTEGER, vin TEXT,"
        "  make TEXT, model TEXT, year INTEGER, type TEXT,"
        "  safety_rating REAL, base_rate REAL"
        ");"
        "CREATE TABLE IF NOT EXISTS policies ("
        "  policy_id TEXT PRIMARY KEY,"
        "  user_id INTEGER, vehicle_id TEXT, status TEXT,"
        "  start_ts TEXT, end_ts TEXT"
        ");"
        # optional driver profile
        "CREATE TABLE IF NOT EXISTS driver_profiles ("
        "  user_id INTEGER PRIMARY KEY, name TEXT, email TEXT"
        ");"
        # gamification
        "CREATE TABLE IF NOT EXISTS rewards ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  user_id INTEGER, points INTEGER, badge TEXT, ts TEXT"
        ");"
    )
    con.commit()
    con.close()

def free_port(preferred: int) -> int:
    """Return preferred if free; otherwise ask OS for an available port."""
    import socket
    s = socket.socket()
    try:
        s.bind(("", preferred))
        port = preferred
    except OSError:
        s.bind(("", 0))
        port = s.getsockname()[1]
    finally:
        s.close()
    return port

# ---------- Orchestrator ----------

def run_all():
    """Start API, processor, simulator, and dashboard. Keep stack up."""
    procs = []

    def spawn(cmd, name):
        print(f"▶ {name}: {' '.join(cmd)}")
        p = subprocess.Popen(cmd, cwd=str(ROOT), env=ENV)
        procs.append((name, p))

    # Auto-pick ports (fall back to a free port if 8000/8501 are busy)
    api_port = free_port(int(os.environ.get("UBI_API_PORT", "8000")))
    dash_port = free_port(int(os.environ.get("UBI_DASH_PORT", "8501")))

    # Services
    spawn([sys.executable, "-m", "uvicorn", "src.api.app:app",
           "--reload", "--port", str(api_port)], "API")
    spawn([sys.executable, "src/processing/stream_processor.py"], "Processor")
    # Long-running simulator; will be respawned if it dies
    spawn([sys.executable, "src/ingest/simulator.py",
           "--users", "5", "--vehicles-per-user", "2",
           "--trips", "2000000", "--realtime"], "Simulator")
    spawn([sys.executable, "-m", "streamlit", "run", "src/dashboard/app.py",
           "--server.port", str(dash_port)], "Dashboard")

    critical = {"API", "Processor", "Dashboard"}
    print(f"🔥 Running | API: http://localhost:{api_port}/docs  |  Dashboard: http://localhost:{dash_port}")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            # Check for exited processes
            dead = [(n, p) for (n, p) in procs if p.poll() is not None]
            if dead:
                # If a critical service died, stop all
                if any(n in critical for (n, _) in dead):
                    break
                # If simulator died, respawn it
                for n, p in dead:
                    if n == "Simulator":
                        procs.remove((n, p))
                        spawn([sys.executable, "src/ingest/simulator.py",
                               "--users", "5", "--vehicles-per-user", "2",
                               "--trips", "2000000", "--realtime"], "Simulator")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n⏹ Stopping...")
    finally:
        # Graceful shutdown then hard kill if needed
        for _, p in procs:
            if p.poll() is None:
                p.terminate()
        time.sleep(0.5)
        for _, p in procs:
            if p.poll() is None:
                p.kill()

# ---------- Main ----------

if __name__ == "__main__":
    pip_install()
    init_db()
    run_all()
