from datetime import datetime, timezone
from pathlib import Path
import os
import sqlite3
import pandas as pd
import streamlit as st

# Robust import for Ops charts (works whether run as script or package)
try:
    from .ops import (
        load_ops,
        chart_throughput,
        chart_feat_lat,
        chart_api_lat,
        chart_queue,
    )
except Exception:
    import sys
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from src.dashboard.ops import (
        load_ops,
        chart_throughput,
        chart_feat_lat,
        chart_api_lat,
        chart_queue,
    )

st.set_page_config(page_title="Telematics UBI Pro", layout="wide")
st.title("Telematics UBI Pro — Dashboard")

DB_PATH = Path(os.environ.get("UBI_DB_PATH", "data/ubi.db"))

# --------------------------- DB helpers --------------------------- #
def read_sql(sql: str, params: tuple = ()):
    """Simple SQLite reader that returns a pandas DataFrame or empty DF."""
    if not DB_PATH.exists():
        return pd.DataFrame()
    con = sqlite3.connect(str(DB_PATH))
    try:
        return pd.read_sql(sql, con, params=params)
    finally:
        con.close()

def load_vehicles(user_id: int) -> pd.DataFrame:
    return read_sql(
        """
        SELECT id, make, model, year, safety_rating, base_rate
        FROM vehicles
        WHERE user_id = ?
        ORDER BY id
        """,
        (user_id,),
    )

def load_latest_quote(user_id: int, vehicle_id: int | None) -> pd.DataFrame:
    if vehicle_id:
        return read_sql(
            """
            SELECT created_at, base_component, usage_component, behavior_component,
                   context_component, final_premium, risk_score
            FROM quotes
            WHERE user_id = ? AND vehicle_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id, vehicle_id),
        )
    # fall back to latest for any vehicle
    return read_sql(
        """
        SELECT created_at, base_component, usage_component, behavior_component,
               context_component, final_premium, risk_score
        FROM quotes
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user_id,),
    )

def load_recent_trips(user_id: int, vehicle_id: int | None, limit: int = 20) -> pd.DataFrame:
    """Last N trips (newest first). If vehicle_id is None, show trips for all vehicles of the user."""
    base_select = """
        SELECT
          id AS trip_id,
          ts_utc,
          vehicle_id,
          miles,
          avg_speed,
          max_speed,
          harsh_brakes,
          speeding_pct,
          night_pct,
          weather_risk
        FROM trips
    """
    if vehicle_id:
        return read_sql(
            base_select
            + f"""
            WHERE user_id = ? AND vehicle_id = ?
            ORDER BY ts_utc DESC
            LIMIT {int(limit)}
            """,
            (user_id, vehicle_id),
        )
    return read_sql(
        base_select
        + f"""
        WHERE user_id = ?
        ORDER BY ts_utc DESC
        LIMIT {int(limit)}
        """,
        (user_id,),
    )

# --------------------------- UI --------------------------- #
tab_overview, tab_vehicles, tab_rewards, tab_leaderboard, tab_ops = st.tabs(
    ["Overview", "Vehicles", "Achievements", "Leaderboard", "Ops (Labeled Metrics)"]
)

# Sidebar filters
with st.sidebar:
    st.header("Filters")
    user_id = st.number_input("User ID", min_value=1, value=1, step=1)
    vehicles_df = load_vehicles(user_id)
    vehicle_choices = {"All vehicles": None}
    for _, r in vehicles_df.iterrows():
        label = f"{int(r['id'])} — {r['make']} {r['model']} {int(r['year'])}"
        vehicle_choices[label] = int(r["id"])
    chosen_label = st.selectbox("Vehicle", list(vehicle_choices.keys()))
    vehicle_id = vehicle_choices[chosen_label]
    trip_limit = st.slider("Recent trips to show", 5, 50, 20, step=5)

# --------------------------- Overview --------------------------- #
with tab_overview:
    st.subheader("My Quote")
    qdf = load_latest_quote(user_id, vehicle_id)
    if qdf.empty:
        st.info("Waiting for first quote… keep the app running for ~10–20 seconds.")
    else:
        q = qdf.iloc[0]
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Risk Score", f"{q['risk_score']:.2f}")
        with c2:
            st.metric("Final Monthly Premium", f"$ {q['final_premium']:.2f}")

        st.caption("Premium Components")
        comp = (
            pd.DataFrame(
                [
                    {
                        "Base": q["base_component"],
                        "Usage": q["usage_component"],
                        "Behavior": q["behavior_component"],
                        "Context": q["context_component"],
                    }
                ]
            )
            .T.rename(columns={0: "$"})
            .reset_index()
            .rename(columns={"index": "Component"})
        )
        st.dataframe(comp, width="stretch", hide_index=True)

    st.markdown("---")
    st.subheader("Recent Trips")
    tdf = load_recent_trips(user_id, vehicle_id, limit=trip_limit)

    if tdf.empty:
        st.info("No trips yet. The simulator will begin streaming trips shortly.")
    else:
        # small summary row
        recent_miles = tdf["miles"].sum()
        avg_brakes = tdf["harsh_brakes"].mean()
        avg_speeding = tdf["speeding_pct"].mean()
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Miles (last N trips)", f"{recent_miles:.1f} mi")
        with c2:
            st.metric("Avg Harsh Brakes", f"{avg_brakes:.2f}")
        with c3:
            st.metric("Avg Speeding %", f"{avg_speeding:.1f}%")

        # show table
        nice_cols = {
            "trip_id": "Trip ID",
            "ts_utc": "Start (UTC)",
            "vehicle_id": "Vehicle",
            "miles": "Miles",
            "avg_speed": "Avg Speed (mph)",
            "max_speed": "Max Speed (mph)",
            "harsh_brakes": "Harsh Brakes",
            "speeding_pct": "Speeding (%)",
            "night_pct": "Night (%)",
            "weather_risk": "Weather Risk (0–1)",
        }
        show = tdf.rename(columns=nice_cols)
        st.dataframe(show, width="stretch", hide_index=True)

# --------------------------- Vehicles --------------------------- #
with tab_vehicles:
    st.subheader("Vehicles")
    st.dataframe(vehicles_df, width="stretch")

# --------------------------- Achievements --------------------------- #
with tab_rewards:
    st.subheader("Recent Rewards")
    rdf = read_sql(
        """
        SELECT created_at, points, reason, trip_id
        FROM rewards
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 50
        """,
        (user_id,),
    )
    if rdf.empty:
        st.info("No rewards yet.")
    else:
        st.dataframe(rdf, width="stretch", hide_index=True)

# --------------------------- Leaderboard --------------------------- #
with tab_leaderboard:
    st.subheader("Leaderboard")
    ldf = read_sql(
        """
        SELECT user_id, display_name, points, badges,
               (100 - risk_score) AS safety_index
        FROM driver_summary
        ORDER BY points DESC, safety_index DESC
        LIMIT 10
        """
    )
    st.dataframe(ldf, width="stretch", hide_index=True)

# --------------------------- Ops --------------------------- #
with tab_ops:
    st.subheader("Operational Metrics — Clearly Labeled")
    odf = load_ops()
    if odf.empty:
        st.info("Metrics will appear as the processor runs.")
    else:
        # Altair still uses use_container_width at the moment; OK to keep.
        c1, c2 = st.columns(2)
        with c1:
            st.altair_chart(chart_throughput(odf), use_container_width=True)
        with c2:
            st.altair_chart(chart_feat_lat(odf), use_container_width=True)
        c3, c4 = st.columns(2)
        with c3:
            st.altair_chart(chart_api_lat(odf), use_container_width=True)
        with c4:
            st.altair_chart(chart_queue(odf), use_container_width=True)

st.caption(f"Rendered at {datetime.now(timezone.utc).isoformat()}")
