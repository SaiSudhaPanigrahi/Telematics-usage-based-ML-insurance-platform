
import os, sqlite3, random, time, argparse, string
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(os.environ.get("UBI_DB_PATH", "data/ubi.db"))

def rid(prefix="T"):
    return prefix + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))

def simulate_trip(user_id, vehicle_id):
    miles = round(random.uniform(2.0, 30.0), 1)
    avg_speed = round(random.uniform(20, 55), 1)
    max_speed = round(avg_speed + random.uniform(5, 30), 1)
    harsh_brakes = random.randint(0, 6)
    accel_var = round(random.uniform(0.5, 3.5), 2)
    night_pct = round(random.uniform(0, 70), 1)
    speeding_pct = round(max(0, (max_speed-65) * random.uniform(0.2, 1.0)), 1)
    weather_risk = round(random.uniform(0, 1), 2)
    return (rid("T"), user_id, vehicle_id, datetime.now(timezone.utc).isoformat(), miles, avg_speed, max_speed, harsh_brakes, accel_var, night_pct, speeding_pct, weather_risk)

def main(trips, realtime):
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    cur.execute("SELECT id, user_id FROM vehicles")
    vehs = cur.fetchall()
    if not vehs:
        print("No vehicles; initialize DB first.")
        return
    for i in range(trips):
        vehicle_id, user_id = random.choice(vehs)
        row = simulate_trip(user_id, vehicle_id)
        cur.execute("""
        INSERT INTO trips(id,user_id,vehicle_id,ts_utc,miles,avg_speed,max_speed,harsh_brakes,accel_var,night_pct,speeding_pct,weather_risk,processed)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)""", row)
        if i % 20 == 0:
            con.commit()
        if realtime:
            time.sleep(0.05)
    con.commit()
    con.close()
    print(f"Generated {trips} trips.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--trips", type=int, default=200)
    ap.add_argument("--realtime", action="store_true")
    args = ap.parse_args()
    main(args.trips, args.realtime)
