import os
import pandas as pd
import altair as alt
from pathlib import Path

def load_ops():
    p = Path(os.environ.get("UBI_METRICS_CSV", "data/ops_metrics.csv"))
    if p.exists():
        df = pd.read_csv(p, parse_dates=["ts_utc"])
        return df.sort_values("ts_utc")
    return pd.DataFrame(columns=["ts_utc","events_per_min","feature_latency_ms","api_p50_ms","api_p95_ms","queue_lag_events"])

def chart_throughput(df):
    return alt.Chart(df, title="Ingestion Throughput (events/min)").mark_line().encode(
        x=alt.X("ts_utc:T", title="Time (UTC)"),
        y=alt.Y("events_per_min:Q", title="Events per Minute")
    ).properties(height=260)

def chart_feat_lat(df):
    return alt.Chart(df, title="Processor Feature Latency (ms)").mark_line().encode(
        x=alt.X("ts_utc:T", title="Time (UTC)"),
        y=alt.Y("feature_latency_ms:Q", title="Latency (ms)")
    ).properties(height=260)

def chart_api_lat(df):
    base = alt.Chart(df, title="API Latency (ms) — p50 vs p95").encode(x=alt.X("ts_utc:T", title="Time (UTC)"))
    p50 = base.mark_line(color="#1f77b4").encode(y=alt.Y("api_p50_ms:Q", title="Latency (ms)"))
    p95 = base.mark_line(color="#ff7f0e").encode(y="api_p95_ms:Q")
    return (p50 + p95).properties(height=260)

def chart_queue(df):
    return alt.Chart(df, title="Queue Lag (events)").mark_area(opacity=0.35).encode(
        x=alt.X("ts_utc:T", title="Time (UTC)"),
        y=alt.Y("queue_lag_events:Q", title="Events in Queue")
    ).properties(height=260)
