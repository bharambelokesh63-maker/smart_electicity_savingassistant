"""SQLite helpers: connection handling, initialization and all SQL queries.

Every query uses parameter placeholders (?) - never string formatting - to
avoid SQL injection.
"""
import json
import os
import sqlite3

from flask import current_app, g

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

APPLIANCE_FIELDS = [
    "name", "category", "power_w", "quantity", "hours_per_day", "days_per_month",
    "preferred_start", "flexible", "min_hours", "max_hours", "priority",
    "standby_w", "window_start", "window_end", "is_demo",
]
TARIFF_FIELDS = [
    "base_rate", "fixed_charge", "tax_percent", "tou_enabled", "peak_start",
    "peak_end", "peak_multiplier", "offpeak_start", "offpeak_end", "offpeak_multiplier",
]


# --------------------------------------------------------------------------- #
# Connection / initialization
# --------------------------------------------------------------------------- #
def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db(db_path):
    """Create all tables (if missing) and make sure the tariff row exists."""
    parent = os.path.dirname(os.path.abspath(db_path))
    os.makedirs(parent, exist_ok=True)
    conn = connect(db_path)
    try:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as fh:
            conn.executescript(fh.read())
        conn.execute("INSERT OR IGNORE INTO tariff_settings (id) VALUES (1)")
        conn.commit()
    finally:
        conn.close()


def init_app(app):
    app.teardown_appcontext(close_db)
    init_db(app.config["DATABASE"])


# --------------------------------------------------------------------------- #
# Appliances
# --------------------------------------------------------------------------- #
def _appliance_to_dict(row):
    d = dict(row)
    d["flexible"] = bool(d["flexible"])
    d["is_demo"] = bool(d["is_demo"])
    return d


def list_appliances(conn):
    rows = conn.execute("SELECT * FROM appliances ORDER BY id").fetchall()
    return [_appliance_to_dict(r) for r in rows]


def get_appliance(conn, appliance_id):
    row = conn.execute("SELECT * FROM appliances WHERE id = ?", (appliance_id,)).fetchone()
    return _appliance_to_dict(row) if row else None


def insert_appliance(conn, data):
    cols = ", ".join(APPLIANCE_FIELDS)
    marks = ", ".join("?" for _ in APPLIANCE_FIELDS)
    values = [int(data[f]) if f in ("flexible", "is_demo") else data.get(f) for f in APPLIANCE_FIELDS]
    cur = conn.execute(f"INSERT INTO appliances ({cols}) VALUES ({marks})", values)
    conn.commit()
    return cur.lastrowid


def update_appliance(conn, appliance_id, data):
    fields = [f for f in APPLIANCE_FIELDS if f != "is_demo"]
    sets = ", ".join(f"{f} = ?" for f in fields)
    values = [int(data[f]) if f == "flexible" else data.get(f) for f in fields]
    cur = conn.execute(
        f"UPDATE appliances SET {sets}, updated_at = datetime('now') WHERE id = ?",
        values + [appliance_id],
    )
    conn.commit()
    return cur.rowcount > 0


def delete_appliance(conn, appliance_id):
    cur = conn.execute("DELETE FROM appliances WHERE id = ?", (appliance_id,))
    conn.commit()
    return cur.rowcount > 0


def delete_demo_appliances(conn):
    cur = conn.execute("DELETE FROM appliances WHERE is_demo = 1")
    conn.commit()
    return cur.rowcount


def count_demo_appliances(conn):
    return conn.execute("SELECT COUNT(*) FROM appliances WHERE is_demo = 1").fetchone()[0]


# --------------------------------------------------------------------------- #
# Tariff
# --------------------------------------------------------------------------- #
def get_tariff(conn):
    row = conn.execute("SELECT * FROM tariff_settings WHERE id = 1").fetchone()
    d = dict(row)
    d["tou_enabled"] = bool(d["tou_enabled"])
    return d


def save_tariff(conn, data):
    sets = ", ".join(f"{f} = ?" for f in TARIFF_FIELDS)
    values = [int(data[f]) if f == "tou_enabled" else data[f] for f in TARIFF_FIELDS]
    conn.execute(f"UPDATE tariff_settings SET {sets}, updated_at = datetime('now') WHERE id = 1", values)
    conn.commit()


# --------------------------------------------------------------------------- #
# Schedules
# --------------------------------------------------------------------------- #
def replace_schedule(conn, kind, rows, algorithm):
    """rows: iterable of (appliance_id, start_hour, duration_hours)."""
    conn.execute("DELETE FROM schedules WHERE kind = ?", (kind,))
    conn.executemany(
        "INSERT INTO schedules (appliance_id, kind, start_hour, duration_hours, algorithm) VALUES (?, ?, ?, ?, ?)",
        [(a, kind, s, d, algorithm) for a, s, d in rows],
    )
    conn.commit()


def get_schedule(conn, kind):
    rows = conn.execute(
        "SELECT appliance_id, start_hour, duration_hours, algorithm, created_at FROM schedules WHERE kind = ?",
        (kind,),
    ).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------- #
# Usage records / recommendations / algorithm runs / settings
# --------------------------------------------------------------------------- #
def insert_usage_record(conn, rec):
    cur = conn.execute(
        """INSERT INTO usage_records
           (appliance_count, daily_kwh, monthly_kwh, tariff_rate, energy_charge, estimated_bill)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (rec["appliance_count"], rec["daily_kwh"], rec["monthly_kwh"],
         rec["tariff_rate"], rec["energy_charge"], rec["estimated_bill"]),
    )
    conn.commit()
    return cur.lastrowid


def list_usage_records(conn, limit=30):
    rows = conn.execute("SELECT * FROM usage_records ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def replace_recommendations(conn, recs):
    conn.execute("DELETE FROM recommendations")
    for r in recs:
        conn.execute(
            """INSERT INTO recommendations
               (appliance_id, appliance_name, kind, issue, action, reason, daily_kwh_saved,
                monthly_kwh_saved, monthly_rs_saved, feasibility, score, assumptions)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (r.get("appliance_id"), r["appliance"], r["kind"], r["issue"], r["action"], r["reason"],
             r["daily_kwh_saved"], r["monthly_kwh_saved"], r["monthly_rs_saved"],
             r["feasibility"], r["score"], r["assumptions"]),
        )
    conn.commit()


def list_recommendations(conn):
    rows = conn.execute("SELECT * FROM recommendations ORDER BY score DESC, id").fetchall()
    return [dict(r) for r in rows]


def insert_algorithm_run(conn, algorithm, found, objective, runtime_ms, summary):
    conn.execute(
        "INSERT INTO algorithm_runs (algorithm, found, objective, runtime_ms, summary) VALUES (?, ?, ?, ?, ?)",
        (algorithm, int(bool(found)), objective, runtime_ms, json.dumps(summary)),
    )
    conn.commit()


def latest_algorithm_runs(conn):
    """Latest run per algorithm plus total run count."""
    rows = conn.execute(
        """SELECT r.*, (SELECT COUNT(*) FROM algorithm_runs c WHERE c.algorithm = r.algorithm) AS run_count
           FROM algorithm_runs r
           WHERE r.id IN (SELECT MAX(id) FROM algorithm_runs GROUP BY algorithm)
           ORDER BY r.algorithm"""
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["found"] = bool(d["found"])
        d["summary"] = json.loads(d["summary"])
        out.append(d)
    return out


def get_setting(conn, key, default=None):
    row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def set_setting(conn, key, value):
    conn.execute(
        "INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, json.dumps(value)),
    )
    conn.commit()
