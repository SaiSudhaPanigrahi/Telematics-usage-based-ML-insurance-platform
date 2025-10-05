Telematics UBI Pro — Submission README

Public repo:
https://github.com/SaiSudhaPanigrahi/Telematics-usage-based-ML-insurance-platform

------------------------------------------------------------
1) Exact Setup & Run Steps (1–Click Dev)
------------------------------------------------------------
Prereqs
- Python 3.10+ (3.11 recommended)
- macOS/Windows/Linux
- Internet access for first dependency install

Steps
1. Clone or unzip the project into a folder, then open a terminal in that folder.
2. Run:
   python dev.py

What dev.py does automatically
- Installs/verifies Python dependencies from requirements.txt
- Creates and initializes SQLite DB at data/ubi.db
- Starts four processes:
  • API (FastAPI) — prints docs URL
  • Processor — computes risk, pricing, rewards; writes ops metrics
  • Simulator — streams multi-vehicle trips (GPS/accel simulated)
  • Dashboard (Streamlit) — prints dashboard URL
- Auto-picks free ports if 8000/8501 are in use and shows final URLs.

Open in browser (look at your console for exact ports)
- API docs: http://localhost:<API_PORT>/docs
- Dashboard: http://localhost:<DASH_PORT>

Default API key
- Header: X-API-Key: dev_api_key_change_me
(Override via environment variable UBI_API_KEY if desired.)

Optional: Dashboard-only quick preview
- python -m streamlit run src/dashboard/app.py

------------------------------------------------------------
2) Evaluation Steps
------------------------------------------------------------
A. Functional Walkthrough
1. Open the Dashboard URL → Overview tab.
   - Verify: Risk Score and Final Monthly Premium are visible.
   - Verify: “Premium Components” table shows Base/Usage/Behavior/Context.
   - Verify: “Recent Trips” table is filling in; use the slider to increase count.
   - Verify: Summary metrics (Miles, Avg Harsh Brakes, Avg Speeding %) update as trips stream.

2. Vehicles tab
   - Verify: Multi-vehicle records (make/model/year, safety rating, base rate).

3. Achievements tab
   - Verify: Rewards rows appear over time (safe-trip points).

4. Leaderboard tab
   - Verify: Users ordered by points/safety index.

5. Ops (Labeled Metrics) tab
   - Verify: Charts populate for Throughput (events/min), Feature Latency (ms),
     API Latency (p50/p95, ms), Queue Lag (events).

B. API Verification (FastAPI)
- Open http://localhost:<API_PORT>/docs
- Try endpoints with X-API-Key header:
  • GET /vehicles?user_id=1
  • GET /pricing/quote?user_id=1&vehicle_id=<id>
  • GET /driver/summary?user_id=1
- Confirm the quote breakdown matches the Dashboard Overview components.

C. Optional ML Training (if you want model artifacts)
- After a few minutes of simulation (>=200 labeled trips), run:
  python src/models/train_model.py --min-trips 200
- Included metrics (ROC-AUC/Accuracy)(e.g., models/artifacts/calibration.png).

D. Demo Screenshots
- Check Demo screenshots added to Repo

------------------------------------------------------------
3) Notes on Models, Data, and External Services
------------------------------------------------------------
Models
- Default risk scoring is a transparent rule-based approach for stability in demo.
- ML path provided: RandomForest/XGBoost training entrypoint with calibration/plots.
- Behavior features: miles, avg_speed, max_speed, harsh_brakes, accel_var,
  speeding_pct, night_pct; Context: weather_risk (stub).

Data
- All telematics data are simulated for POC (speed/acceleration/braking + geohash).
- SQLite database created at runtime (data/ubi.db). No external DB required for demo.

External Services
- None required for local demo. Weather/incident integration is stubbed and ready
  to be swapped with a live API (adapter pattern).

------------------------------------------------------------
5) Contact
------------------------------------------------------------
Author: Sai Sudha Panigrahi
Email: saisudha@usc.edu
Linkedin: https://www.linkedin.com/in/sai-sudha-panigrahi
Portfolio Website: https://saisudhapanigrahi.netlify.app/
Github: https://github.com/SaiSudhaPanigrahi
