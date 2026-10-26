import math

import pytest

from ai.a_star import a_star_search
from ai.bayesian_network import BayesianNetwork, run_bayesian_network
from ai.best_first import best_first_search
from ai.csp_scheduler import csp_backtracking
from ai.forward_chaining import run_forward_chaining
from ai.hill_climbing import hill_climbing
from ai.scheduling_problem import SchedulingProblem
from services.recommendation_engine import generate_recommendations
from services.schedule_optimizer import optimize_schedule
from services.validators import validate_schedule_config


def make_problem(appliances, tariff, **overrides):
    cfg, errors = validate_schedule_config(overrides)
    assert not errors
    return SchedulingProblem(appliances, tariff, cfg)


def assert_hard_constraints(problem, schedule):
    assert schedule["feasible"] and schedule["violations"] == []
    for e in schedule["entries"]:
        b = problem.block(e["appliance_id"])
        assert len(e["slots"]) == math.ceil(b.hours)                 # required duration
        if b.flexible:                                               # unavailable hours bind flexible appliances
            assert not set(e["slots"]) & set(problem.unavailable)    # availability
            assert b.window_start <= e["start"] and e["end"] <= b.window_end   # window
    if problem.capacity is not None:
        assert max(schedule["hourly_load_kwh"]) <= problem.capacity + 1e-6      # capacity


# ---------------------------------------------------------------- CSP
def test_csp_solution_satisfies_all_constraints(appliances, tariff):
    p = make_problem(appliances, tariff, unavailable_hours=[0, 1, 2, 3], capacity_kw=3.0)
    r = csp_backtracking(p)
    assert r["found"]
    assert_hard_constraints(p, r["schedule"])


def test_csp_reports_failure_when_impossible(appliances, tariff):
    # capacity below the always-on fixed load of the AC makes every assignment invalid
    p = make_problem(appliances, tariff, capacity_kw=0.1)
    r = csp_backtracking(p)
    assert r["found"] is False
    assert r["schedule"] is None
    assert "no valid schedule" in r["explanation"].lower()


def test_csp_fails_when_all_hours_unavailable(appliances, tariff):
    p = make_problem(appliances, tariff, unavailable_hours=list(range(24)))
    r = csp_backtracking(p)
    assert r["found"] is False


# ---------------------------------------------------------------- search
def test_a_star_reaches_goal_with_consistent_path(appliances, tariff):
    p = make_problem(appliances, tariff)
    r = a_star_search(p)
    assert r["found"]
    flexible = {b.id for b in p.flexible_blocks}
    assert {s["appliance"] for s in r["path"]} == {p.block(i).name for i in flexible}   # goal: all placed
    assert_hard_constraints(p, r["schedule"])
    assert r["path"][-1]["g"] == pytest.approx(sum(s["step_cost"] for s in r["path"]))
    assert r["path"][-1]["g"] == pytest.approx(r["stats"]["goal_cost"])


def test_a_star_not_worse_than_best_first_or_original(appliances, tariff):
    p = make_problem(appliances, tariff)
    a, b = a_star_search(p), best_first_search(p)
    assert a["found"] and b["found"]
    assert a["schedule"]["objective"] <= b["schedule"]["objective"] + 1e-6
    assert a["schedule"]["objective"] <= a["original"]["objective"] + 1e-6
    assert b["optimal"] is False          # greedy search must not claim optimality


def test_a_star_matches_brute_force_on_small_problem(tariff):
    aps = [
        dict(id=1, name="A", category="Other", power_w=1000, quantity=1, hours_per_day=2, days_per_month=30,
             preferred_start=19, flexible=True, min_hours=1, max_hours=3, priority=2, standby_w=0,
             window_start=16, window_end=24),
        dict(id=2, name="B", category="Other", power_w=500, quantity=1, hours_per_day=1, days_per_month=30,
             preferred_start=19, flexible=True, min_hours=1, max_hours=3, priority=2, standby_w=0,
             window_start=16, window_end=24),
    ]
    p = make_problem(aps, tariff, capacity_kw=1.2)
    best = min(
        (p.evaluate({1: s1, 2: s2}) for s1 in p.domain(p.block(1)) for s2 in p.domain(p.block(2))),
        key=lambda ev: ev["objective"] if ev["feasible"] else float("inf"))
    r = a_star_search(p)
    assert r["found"] and r["optimal"]
    assert r["schedule"]["objective"] == pytest.approx(best["objective"])


def test_search_failure_is_reported(appliances, tariff):
    p = make_problem(appliances, tariff, capacity_kw=0.1)
    for fn in (a_star_search, best_first_search):
        r = fn(p)
        assert r["found"] is False and r["schedule"] is None


# ---------------------------------------------------------------- hill climbing
def test_hill_climbing_never_worsens_objective(appliances, tariff):
    p = make_problem(appliances, tariff)
    r = hill_climbing(p)
    assert r["found"]
    objs = [h["objective"] for h in r["log"]]
    assert all(b <= a + 1e-9 for a, b in zip(objs, objs[1:]))
    assert r["final_objective"] <= r["initial_objective"] + 1e-9
    assert r["final_objective"] < r["initial_objective"]   # sample data has a cheaper off-peak slot
    assert_hard_constraints(p, r["schedule"])


# ---------------------------------------------------------------- optimizer + recommendations
@pytest.mark.parametrize("method", ["astar", "best_first", "hill_climbing", "csp"])
def test_optimizer_respects_hard_constraints(appliances, tariff, method):
    r = optimize_schedule(appliances, tariff, {"capacity_kw": 4.0, "unavailable_hours": [3, 4]}, method=method)
    if r["found"]:
        p = make_problem(appliances, tariff, capacity_kw=4.0, unavailable_hours=[3, 4])
        assert_hard_constraints(p, r["optimized"])


def test_recommendations_are_ranked_and_non_negative(appliances, tariff):
    r = generate_recommendations(appliances, tariff, {})
    recs = r["recommendations"]
    assert recs
    assert [x["rank"] for x in recs] == list(range(1, len(recs) + 1))
    scores = [x["score"] for x in recs]
    assert scores == sorted(scores, reverse=True)
    assert all(x["monthly_kwh_saved"] >= 0 and x["monthly_rs_saved"] >= 0 for x in recs)
    assert all(x["assumptions"] for x in recs)


# ---------------------------------------------------------------- forward chaining
def test_forward_chaining_fires_expected_rules(appliances, tariff):
    r = run_forward_chaining(appliances, tariff, {}, {})
    fired = {s["rule"] for s in r["inference_steps"]}
    assert any(n.startswith("R1") for n in fired)        # high consumption
    assert any(n.startswith("R3") for n in fired)        # standby
    assert r["stats"]["rules_fired"] == len(r["inference_steps"])
    assert r["flagged_for_review"]
    assert any("Air Conditioner" in str(s["derived"]) for s in r["inference_steps"])


def test_forward_chaining_with_no_trigger(tariff):
    aps = [dict(id=1, name="Lamp", category="Lighting", power_w=5, quantity=1, hours_per_day=1,
                days_per_month=30, preferred_start=19, flexible=False, min_hours=1, max_hours=1,
                priority=1, standby_w=0, window_start=0, window_end=24)]
    r = run_forward_chaining(aps, tariff, {}, {"high_share_pct": 101, "high_monthly_kwh": 1e9})
    assert r["flagged_for_review"] == []
    assert r["recommendations"] == []


# ---------------------------------------------------------------- Bayesian network
def test_bn_cpts_sum_to_one():
    net = BayesianNetwork()
    assert net.validate() is True
    for row in net.cpt_rows():
        assert row["row_sum"] == pytest.approx(1.0)


def test_bn_posterior_normalised_and_responds_to_evidence():
    net = BayesianNetwork()
    prior, _ = net.query("ConsumptionCategory", {})
    heavy, p_e = net.query("ConsumptionCategory", {"UsageIntensity": "Heavy", "HighPowerCount": "Many",
                                              "StandbyLevel": "High"})
    light, _ = net.query("ConsumptionCategory", {"UsageIntensity": "Light", "HighPowerCount": "None",
                                              "StandbyLevel": "Low"})
    assert 0 < p_e <= 1
    for dist in (prior, heavy, light):
        assert sum(dist.values()) == pytest.approx(1.0)
    assert heavy["High"] > prior["High"] > light["High"]
    assert light["Low"] > prior["Low"] > heavy["Low"]


def test_bn_run_on_appliances(appliances):
    r = run_bayesian_network(appliances)
    assert sum(r["posterior"].values()) == pytest.approx(1.0)
    assert r["most_probable"] in ("Low", "Moderate", "High")


def test_bn_rejects_bad_evidence(appliances):
    with pytest.raises(ValueError):
        run_bayesian_network(appliances, {"UsageIntensity": "Gigantic"})
