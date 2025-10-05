
import time, random, argparse, geohash2, sqlite3
from datetime import datetime, timedelta
from src.utils.config import DB_PATH
from src.utils.logging import get_logger

log = get_logger("simulator")

MAKES = [("Toyota","Camry","sedan",0.9, 78.0),("Honda","Civic","sedan",0.9, 76.0),
         ("Ford","F-150","truck",0.8, 85.0),("Tesla","Model 3","sedan",0.95, 90.0),
         ("Subaru","Outback","wagon",0.92, 75.0)]

def rand_id(prefix="T", n=9):
    import secrets, string
    return prefix + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(n))

def ensure_user_vehicles(con, user_id:int, vehicles_per_user:int):
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM vehicles WHERE user_id=?", (user_id,))
    cnt = cur.fetchone()[0] or 0
    to_make = max(0, vehicles_per_user - cnt)
    for _ in range(to_make):
        make, model, typ, safety, base = random.choice(MAKES)
        vid = rand_id("V")
        year = random.randint(2010, 2024)
        vin = rand_id("VIN", 12)
        cur.execute("INSERT OR REPLACE INTO vehicles (vehicle_id,user_id,vin,make,model,year,type,safety_rating,base_rate) VALUES (?,?,?,?,?,?,?,?,?)",
                    (vid, user_id, vin, make, model, year, typ, safety, base))
        cur.execute("INSERT OR REPLACE INTO policies (policy_id,user_id,vehicle_id,status,start_ts,end_ts) VALUES (?,?,?,?,datetime('now'),NULL)",
                    (rand_id("P"), user_id, vid, "active"))
    con.commit()

def list_user_vehicle_ids(con, user_id:int):
    cur = con.cursor()
    cur.execute("SELECT vehicle_id FROM vehicles WHERE user_id=?", (user_id,))
    return [r[0] for r in cur.fetchall()]

def simulate_trip(user_id:int, vehicle_id:str, start:datetime, minutes:int=None):
    minutes = minutes or random.randint(10, 45)
    trip_id = rand_id("T")
    miles = 0.0
    lat, lon = 34.05 + random.uniform(-0.05, 0.05), -118.24 + random.uniform(-0.05, 0.05)
    events = []
    ts = start
    prev_speed = random.uniform(0, 10)
    for _ in range(minutes):
        hour = ts.hour
        night = 1 if hour < 6 or hour >= 22 else 0
        target = random.uniform(20, 70) * (0.7 if night else 1.0)
        accel = random.uniform(-3, 3)
        speed = max(0, prev_speed + accel + (target - prev_speed) * 0.15)
        brake = 1.0 if (prev_speed - speed) > 8.0 else 0.0
        lat += random.uniform(-0.001, 0.001)
        lon += random.uniform(-0.001, 0.001)
        gh = geohash2.encode(lat, lon, precision=5)
        miles += speed * (1/60)
        events.append((ts.isoformat(), user_id, trip_id, vehicle_id, speed, accel, brake, lat, lon, gh))
        prev_speed = speed
        ts += timedelta(minutes=1)
    return trip_id, miles, events, ts

def write_trip(con, trip_id, user_id, vehicle_id, miles, start_ts, end_ts, events):
    cur = con.cursor()
    cur.execute("INSERT OR REPLACE INTO trips (trip_id,user_id,vehicle_id,start_ts,end_ts,miles) VALUES (?,?,?,?,?,?)",
                (trip_id, user_id, vehicle_id, start_ts.isoformat(), end_ts.isoformat(), miles))
    cur.executemany("INSERT INTO raw_events (ts,user_id,trip_id,vehicle_id,speed,accel,brake,lat,lon,geohash) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    events)
    con.commit()

def main(users:int, vehicles_per_user:int, trips:int, realtime:bool):
    con = sqlite3.connect(DB_PATH)
    for u in range(1, users+1):
        ensure_user_vehicles(con, u, vehicles_per_user)
    for u in range(1, users+1):
        vids = list_user_vehicle_ids(con, u)
        for _ in range(trips):
            vid = random.choice(vids)
            start = datetime.utcnow() - timedelta(hours=random.randint(0, 72))
            tid, miles, events, end = simulate_trip(u, vid, start)
            write_trip(con, tid, u, vid, miles, start, end, events)
            log.info(f"trip {tid} user {u} veh {vid} miles={miles:.1f} events={len(events)}")
            if realtime:
                time.sleep(0.2)
    con.close()

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", type=int, default=3)
    ap.add_argument("--vehicles-per-user", type=int, default=2)
    ap.add_argument("--trips", type=int, default=10)
    ap.add_argument("--realtime", action="store_true")
    args = ap.parse_args()
    main(args.users, args.vehicles_per_user, args.trips, args.realtime)
