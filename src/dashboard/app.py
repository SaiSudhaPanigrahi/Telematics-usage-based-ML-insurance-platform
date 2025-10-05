
import streamlit as st
import sqlite3, pandas as pd
from src.utils.config import DB_PATH
from src.models.risk_scoring import quote_for_user, vehicle_list_for_user

st.set_page_config(page_title="Telematics UBI Pro", layout="wide")

def load_features(user_id:int, vehicle_id:str|None):
    con = sqlite3.connect(DB_PATH)
    if vehicle_id:
        feats = pd.read_sql_query("SELECT * FROM features WHERE user_id=? AND vehicle_id=? ORDER BY rowid DESC LIMIT 100",
                                  con, params=(user_id, vehicle_id))
    else:
        feats = pd.read_sql_query("SELECT * FROM features WHERE user_id=? ORDER BY rowid DESC LIMIT 100",
                                  con, params=(user_id,))
    con.close()
    return feats

def leaderboard():
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT user_id, SUM(points) AS points FROM rewards GROUP BY user_id ORDER BY points DESC LIMIT 10", con)
    con.close()
    if df.empty: st.info("No rewards yet."); return
    st.subheader("Leaderboard (Safe Driving Points)"); st.table(df)

def achievements(user_id:int):
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT ts, points, badge FROM rewards WHERE user_id=? ORDER BY ts DESC LIMIT 50", con, params=(user_id,))
    con.close()
    if df.empty: st.info("No achievements yet."); return
    st.subheader("My Achievements"); st.table(df)

def vehicles_tab(user_id:int):
    st.subheader("My Vehicles & Policies")
    vehicles = vehicle_list_for_user(user_id)
    if not vehicles: st.info("No vehicles yet."); return
    st.dataframe(pd.DataFrame(vehicles))

def overview_tab(user_id:int):
    vehicles = vehicle_list_for_user(user_id)
    options = ["All vehicles"] + [v["vehicle_id"] for v in vehicles]
    vehicle_sel = st.selectbox("Select vehicle", options)
    vehicle_id = None if vehicle_sel == "All vehicles" else vehicle_sel
    feats = load_features(user_id, vehicle_id)
    if feats.empty:
        st.info("No trips yet."); return
    st.subheader("Recent Trips (features)")
    st.dataframe(feats[['trip_id','vehicle_id','miles','avg_speed','max_speed','harsh_brake_ct','night_pct','speeding_pct','weather_risk']])
    st.subheader("My Quote")
    q = quote_for_user(user_id, vehicle_id)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Risk Score", q['risk_score'])
    col2.metric("Base Premium", f"$ {q['base_premium']}")
    col3.metric("Usage Component", f"$ {q['dynamic_component']}")
    col4.metric("Context Component", f"$ {q['context_component']}")
    st.metric("Final Monthly Premium", f"$ {q['final_monthly_premium']}")
    st.write("Explanations:", ", ".join(q['explanations']))

def main():
    st.title("Telematics UBI Pro — Driver Portal")
    user_id = st.sidebar.number_input("User ID", min_value=1, value=1, step=1)
    tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Vehicles", "Achievements", "Leaderboard"])
    with tab1: overview_tab(user_id)
    with tab2: vehicles_tab(user_id)
    with tab3: achievements(user_id)
    with tab4: leaderboard()

if __name__ == "__main__":
    main()
