import pytest


def post(client, appliance):
    return client.post("/api/appliances", json=appliance)


# ---------------------------------------------------------------- CRUD
def test_crud_roundtrip(client, valid_appliance):
    r = post(client, valid_appliance)
    assert r.status_code == 201
    aid = r.get_json()["data"]["id"]
    listed = client.get("/api/appliances").get_json()["data"]
    assert len(listed) == 1
    assert listed[0]["daily_kwh"] == pytest.approx(2.0)        # 1000 W x 1 x 2 h / 1000
    assert listed[0]["monthly_kwh"] == pytest.approx(60.0)

    upd = dict(valid_appliance, hours_per_day=3)
    r = client.put(f"/api/appliances/{aid}", json=upd)
    assert r.status_code == 200
    assert r.get_json()["data"]["hours_per_day"] == 3
    assert client.get("/api/appliances").get_json()["data"][0]["daily_kwh"] == pytest.approx(3.0)

    assert client.delete(f"/api/appliances/{aid}").status_code == 200
    assert client.get("/api/appliances").get_json()["data"] == []
    assert client.delete(f"/api/appliances/{aid}").status_code == 404
    assert client.put(f"/api/appliances/{aid}", json=upd).status_code == 404


def test_data_persists_in_database_file(tmp_path, valid_appliance):
    from app import create_app
    from config import Config

    class Cfg(Config):
        TESTING = True
        DATABASE = str(tmp_path / "persist.db")

    post(create_app(Cfg).test_client(), valid_appliance)
    again = create_app(Cfg).test_client()                      # "restart"
    assert len(again.get("/api/appliances").get_json()["data"]) == 1


# ---------------------------------------------------------------- validation
@pytest.mark.parametrize("field,value", [
    ("name", ""), ("name", "x" * 61), ("power_w", 0), ("power_w", -5), ("power_w", "abc"),
    ("power_w", 20001), ("quantity", 0), ("quantity", 1.5), ("hours_per_day", 0),
    ("hours_per_day", 24.5), ("days_per_month", 0), ("days_per_month", 32),
    ("priority", 4), ("standby_w", -1), ("preferred_start", 24), ("category", "Spaceship"),
])
def test_invalid_fields_rejected(client, valid_appliance, field, value):
    valid_appliance[field] = value
    r = post(client, valid_appliance)
    assert r.status_code == 400
    body = r.get_json()
    assert body["success"] is False and body["error"]
    assert client.get("/api/appliances").get_json()["data"] == []


def test_boundary_values_accepted(client, valid_appliance):
    valid_appliance.update(hours_per_day=24, min_hours=0, max_hours=24, days_per_month=31,
                           quantity=100, window_start=0, window_end=24, power_w=20000)
    assert post(client, valid_appliance).status_code == 201


def test_cross_field_rules(client, valid_appliance):
    assert post(client, dict(valid_appliance, min_hours=5)).status_code == 400      # min > hours
    assert post(client, dict(valid_appliance, max_hours=1)).status_code == 400      # max < hours
    assert post(client, dict(valid_appliance, window_start=10, window_end=11)).status_code == 400  # window too short


def test_missing_required_fields(client):
    assert client.post("/api/appliances", json={}).status_code == 400


def test_malformed_json_and_wrong_type(client):
    r = client.post("/api/appliances", data="{not json", content_type="application/json")
    assert r.status_code == 400 and r.get_json()["success"] is False
    r = client.post("/api/appliances", json=[1, 2, 3])
    assert r.status_code == 400


# ---------------------------------------------------------------- error handling
def test_unknown_api_route_returns_json_404(client):
    r = client.get("/api/nope")
    assert r.status_code == 404 and r.get_json()["success"] is False


def test_wrong_method_returns_json_405(client):
    r = client.put("/api/dashboard")
    assert r.status_code == 405 and r.get_json()["success"] is False


def test_algorithms_need_appliances(client):
    for name in ("best-first", "a-star", "hill-climbing", "csp", "forward-chaining", "bayesian-network"):
        r = client.post(f"/api/algorithms/{name}", json={})
        assert r.status_code == 400, name
        assert "appliance" in r.get_json()["error"].lower()
    assert client.post("/api/optimize-schedule", json={}).status_code == 400


def test_invalid_algorithm_parameters(client):
    client.post("/api/sample-data/load")
    r = client.post("/api/algorithms/a-star", json={"capacity_kw": -2})
    assert r.status_code == 400
    r = client.post("/api/algorithms/bayesian-network", json={"UsageIntensity": "Bogus"})
    assert r.status_code == 400
    r = client.post("/api/algorithms/forward-chaining", json={"high_share_pct": "abc"})
    assert r.status_code == 400


def test_no_stack_trace_in_unexpected_error(client, monkeypatch):
    import routes.dashboard_routes as dr

    def boom(_conn):
        raise RuntimeError("secret internal detail")
    monkeypatch.setattr(dr, "build_dashboard", boom)
    r = client.get("/api/dashboard")
    assert r.status_code == 500
    assert "secret" not in r.get_data(as_text=True) and "Traceback" not in r.get_data(as_text=True)


# ---------------------------------------------------------------- demo data + reports
def test_dashboard_empty_then_populated(client):
    d = client.get("/api/dashboard").get_json()["data"]
    assert d["empty"] is True and "message" in d
    assert client.post("/api/sample-data/load").status_code == 201
    assert client.post("/api/sample-data/load").status_code == 409        # not duplicated
    d = client.get("/api/dashboard").get_json()["data"]
    assert d["empty"] is False
    assert d["totals"]["appliance_count"] == 8
    assert d["totals"]["monthly_kwh"] == pytest.approx(
        sum(c["monthly_kwh"] for c in d["charts"]["appliances"]), rel=0.01)


def test_reset_requires_confirmation_and_keeps_user_data(client, valid_appliance):
    post(client, valid_appliance)
    client.post("/api/sample-data/load")
    assert client.post("/api/sample-data/reset", json={}).status_code == 400
    assert len(client.get("/api/appliances").get_json()["data"]) == 9
    r = client.post("/api/sample-data/reset", json={"confirm": True})
    assert r.get_json()["data"]["removed"] == 8
    names = [a["name"] for a in client.get("/api/appliances").get_json()["data"]]
    assert names == ["Test Heater"]


def test_tariff_update_changes_costs(client, valid_appliance):
    post(client, valid_appliance)
    t = client.get("/api/tariff").get_json()["data"]
    t["base_rate"] = 10.0
    t["tou_enabled"] = False
    assert client.put("/api/tariff", json=t).status_code == 200
    d = client.get("/api/dashboard").get_json()["data"]
    assert d["totals"]["energy_charge"] == pytest.approx(600.0)            # 60 kWh x Rs10
    t["base_rate"] = -1
    assert client.put("/api/tariff", json=t).status_code == 400


def test_report_and_csv(client):
    assert client.get("/api/energy-report/csv").status_code == 400         # nothing to export
    client.post("/api/sample-data/load")
    rep = client.get("/api/energy-report").get_json()["data"]
    assert len(rep["rows"]) == 8
    r = client.get("/api/energy-report/csv")
    assert r.status_code == 200 and r.mimetype == "text/csv"
    assert "Air Conditioner" in r.get_data(as_text=True)


def test_csv_neutralises_formula_injection(client, valid_appliance):
    post(client, dict(valid_appliance, name="=HYPERLINK(\"x\")"))
    text = client.get("/api/energy-report/csv").get_data(as_text=True)
    assert "'=HYPERLINK" in text


def test_every_algorithm_endpoint_works_and_is_recorded(client):
    client.post("/api/sample-data/load")
    for name in ("best-first", "a-star", "hill-climbing", "csp", "forward-chaining", "bayesian-network"):
        r = client.post(f"/api/algorithms/{name}", json={})
        assert r.status_code == 200, name
        assert r.get_json()["data"]["found"] is True
    runs = client.get("/api/energy-report").get_json()["data"]["algorithm_runs"]
    assert len(runs) >= 6
    assert client.post("/api/recommendations", json={}).status_code == 200
    assert client.post("/api/optimize-schedule", json={}).status_code == 200


def test_pages_render(client):
    for p in ["/", "/appliances", "/calculator", "/recommendations", "/scheduler", "/algorithms", "/reports"]:
        assert client.get(p).status_code == 200, p
