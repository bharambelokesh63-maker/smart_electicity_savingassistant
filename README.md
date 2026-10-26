# Smart Electricity Saving Assistant

A Flask + SQLite web app that analyses household electricity use and applies **classical AI**
(Best-First, A*, Hill Climbing, CSP backtracking, Forward Chaining, Bayesian Network) to
schedule appliances and recommend savings. Runs fully offline: no API keys and no CDN
(Bootstrap, Bootstrap Icons and Chart.js are bundled in `static/vendor/`).

> All figures are **estimates** from the data and tariff you enter. "Energy charge" is
> `monthly kWh x tariff`; it is not a full bill (slabs, surcharges and taxes vary by utility).

## 1. Prerequisites
Python 3.9+ and a modern browser.

## 2. Setup
```bash
cd smart-electricity-assistant
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Database
`database/schema.sql` is applied automatically at startup and creates
`database/electricity.db` on first run, so there is nothing to do manually.
Data survives restarts. Set `SEA_DATABASE=/path/to/file.db` to use another file.

## 4. Run
```bash
python app.py
```
Open **http://127.0.0.1:5000**

## 5. Using the app
| Page | What to do |
|---|---|
| **Demo data** (top-right menu) | *Load sample data* adds 8 appliances flagged as demo. *Reset demonstration data* (asks for confirmation) removes only those; your own appliances stay. |
| **Dashboard** | Daily/monthly kWh, estimated bill, savings, top consumer, charts, current-vs-optimized load. Shows an onboarding card when empty. |
| **Appliances** | Add / edit / delete. Pick a preset template (LED, fan, fridge, TV, AC, washing machine, computer, water heater). Validated in the browser and on the server. |
| **Calculator** | Edit the tariff (flat rate, optional peak/off-peak multipliers, fixed charge, tax %) and see per-appliance daily/monthly kWh and energy charge. |
| **AI Recommendations** | Forward-chaining rules produce ranked suggestions with kWh/₹ savings and stated assumptions. Thresholds are adjustable. |
| **AI Scheduler** | Choose an algorithm, unavailable hours, hourly capacity (kW) and preferred hours. See original vs optimized timelines, cost and kWh change. If infeasible, the blocking constraints are explained. |
| **Algorithm Lab** | One tab per algorithm: explanation, parameters, **Run Algorithm**, logs, runtime, visualisation, original-vs-result timelines. Tip: set capacity to about 2.5 kW to see backtracking in action. |
| **Reports** | Tables, charts, recommendation ranking, algorithm run history. **Download CSV** exports the report. |

Light/dark mode: moon button in the top bar.

## 6. Tests
```bash
python -m pytest -q
```
60 tests cover calculations, CRUD, validation and boundaries, CSP constraints, A* goal/path
(and equality with brute force on a small case), Hill Climbing never worsening the objective,
forward-chaining rules, Bayesian CPT sums and posterior normalisation, API error handling,
CSV formula-injection safety, and every endpoint.

## 7. Project layout
```
app.py  config.py  requirements.txt
database/   schema.sql, db.py
ai/         best_first, a_star, hill_climbing, csp_scheduler, forward_chaining,
            bayesian_network, scheduling_problem (shared model), state_space (search engine)
services/   energy_calculator, recommendation_engine, schedule_optimizer, report_service, validators
routes/     appliance, dashboard, schedule, algorithm, report and page routes
templates/  static/{css,js,vendor}   tests/
```
`ai/` has no Flask imports, so each algorithm can be tested on its own.

## 8. Algorithm notes (for viva)
* **Model:** 24 hourly slots. A flexible appliance is one block of `ceil(hours)` consecutive hours
  with a start-hour variable. Cost = time-of-use energy cost + soft penalties (moving away from the preferred time).
* **A\***: state = partial placements; g = cost so far; h = sum of each unplaced appliance's cheapest
  placement (ignores capacity, so it never overestimates: admissible and consistent). `optimal` is
  reported only if the search finished without hitting the expansion limit.
* **Best-First**: priority = h only. Fast, with **no optimality claim**.
* **Hill Climbing**: move one appliance at a time to the best improving slot; stops at a *local* optimum.
* **CSP**: MRV variable ordering, unary pruning (window/duration/availability) plus a capacity check, recursive backtracking.
* **Forward Chaining**: facts from your data, five IF-THEN rules, repeated until no new facts; full inference trace shown.
* **Bayesian Network**: `UsageIntensity, HighPowerCount, StandbyLevel -> ConsumptionCategory` with explicit CPTs
  (every row sums to 1) and exact inference by enumeration. It is an educational estimate, not a measurement or forecast.

## 9. Troubleshooting
* *Port 5000 busy:* change the port in the last line of `app.py`.
* *`ModuleNotFoundError: flask`:* activate the venv and re-run `pip install -r requirements.txt`.
* *Fresh start:* stop the app and delete `database/electricity.db`.
* *"No valid schedule":* constraints are too tight (capacity below the fixed load, or all hours unavailable). The message names the cause.
* *Blank charts:* add appliances or load demo data first.
