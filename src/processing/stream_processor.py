
import time, sqlite3, pandas as pd, random
from src.utils.config import DB_PATH
from src.utils.logging import get_logger

log = get_logger("processor")

def list_unfeatured_trip_ids(con):
    q = "SELECT t.trip_id, t.user_id, t.vehicle_id FROM trips t LEFT JOIN features f ON f.trip_id = t.trip_id WHERE f.trip_id IS NULL"
    return pd.read_sql_query(q, con)

def load_trip_events(con, trip_id):
    df = pd.read_sql_query(
        "SELECT ts, user_id, trip_id, vehicle_id, speed, accel, brake FROM raw_events WHERE trip_id=? ORDER BY ts",
        con, params=(trip_id,)
    )
    df['ts'] = pd.to_datetime(df['ts'])
    return df

def features_from_events(df: pd.DataFrame) -> dict:
    if df.empty: return {}
    miles = (df['speed'].fillna(0) * (1/60)).sum()
    avg_speed = df['speed'].mean()
    max_speed = df['speed'].max()
    harsh_brake_ct = int((df['brake'] > 0.5).sum())
    accel_var = float(df['accel'].var() or 0.0)
    hours = df['ts'].dt.hour
    night_pct = float(((hours < 6) | (hours >= 22)).mean())
    speeding_pct = float((df['speed'] > 65).mean())
    weather_risk = float(random.choice([0.0, 0.1, 0.2, 0.4, 0.6])) * (0.5 + 0.5*night_pct)
    return dict(miles=float(miles), avg_speed=float(avg_speed), max_speed=float(max_speed),
                harsh_brake_ct=harsh_brake_ct, accel_var=accel_var,
                night_pct=night_pct, speeding_pct=speeding_pct,
                weather_risk=weather_risk)

def maybe_label(con, trip_id):
    q = "SELECT * FROM features WHERE trip_id=?"
    df = pd.read_sql_query(q, con, params=(trip_id,))
    if df.empty: return
    r = df.iloc[0]
    p = 0.04 + 0.25*r['night_pct'] + 0.4*r['speeding_pct'] + 0.05*min(r['harsh_brake_ct']/5, 1) + 0.08*r['weather_risk']
    incident = 1 if random.random() < p else 0
    con.execute("INSERT OR REPLACE INTO labels (trip_id, incident) VALUES (?, ?)", (trip_id, incident))

def maybe_reward(con, user_id, feats):
    safe = (feats['speeding_pct'] < 0.1) and (feats['harsh_brake_ct'] <= 1) and (feats['night_pct'] < 0.3)
    if safe:
        con.execute("INSERT INTO rewards (user_id, points, badge, ts) VALUES (?, ?, ?, datetime('now'))",
                    (user_id, 5, 'safe-trip',))
        con.commit()

def process_once():
    con = sqlite3.connect(DB_PATH)
    todo = list_unfeatured_trip_ids(con)
    for _, row in todo.iterrows():
        df = load_trip_events(con, row['trip_id'])
        feats = features_from_events(df)
        if feats:
            con.execute(
                "INSERT OR REPLACE INTO features (trip_id, user_id, vehicle_id, miles, avg_speed, max_speed, harsh_brake_ct, accel_var, night_pct, speeding_pct, weather_risk) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (row['trip_id'], row['user_id'], row['vehicle_id'], feats['miles'], feats['avg_speed'], feats['max_speed'],
                 feats['harsh_brake_ct'], feats['accel_var'], feats['night_pct'], feats['speeding_pct'], feats['weather_risk'])
            )
            maybe_label(con, row['trip_id'])
            maybe_reward(con, int(row['user_id']), feats)
            con.commit()
            log.info(f"featured trip {row['trip_id']} user {row['user_id']} veh {row['vehicle_id']}")
    con.close()

if __name__ == "__main__":
    while True:
        process_once()
        time.sleep(2)
