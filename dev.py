
#!/usr/bin/env python3
import os, sys, subprocess, time, socket
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
ENV = os.environ.copy()
ENV.setdefault("UBI_API_KEY", "dev_api_key_change_me")
ENV.setdefault("UBI_DB_PATH", str(ROOT / "data" / "ubi.db"))
ENV.setdefault("UBI_METRICS_CSV", str(ROOT / "data" / "ops_metrics.csv"))

def free_port(preferred):
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

def install():
    print("➡ Installing/Verifying dependencies")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])

def init_db():
    subprocess.check_call([sys.executable, "-m", "src.common.db"], env=ENV, cwd=str(ROOT))

def run():
    api_port = free_port(8000)
    dash_port = free_port(8501)
    procs = []
    def spawn(cmd, name):
        print("▶", name, ":", " ".join(cmd))
        p = subprocess.Popen(cmd, cwd=str(ROOT), env=ENV)
        procs.append(p)
    spawn([sys.executable, "-m", "uvicorn", "src.api.app:app", "--reload", "--port", str(api_port)], "API")
    spawn([sys.executable, "src/processing/processor.py"], "Processor")
    spawn([sys.executable, "src/ingest/simulator.py", "--trips", "200", "--realtime"], "Simulator")
    spawn([sys.executable, "-m", "streamlit", "run", "src/dashboard/app.py", "--server.port", str(dash_port)], "Dashboard")
    print(f"🔥 Running | API: http://localhost:{api_port}/docs  |  Dashboard: http://localhost:{dash_port}")
    print("Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        for p in procs:
            if p.poll() is None:
                p.terminate()

if __name__ == "__main__":
    install()
    init_db()
    run()
