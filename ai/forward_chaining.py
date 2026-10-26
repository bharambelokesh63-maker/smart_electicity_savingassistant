"""Forward-chaining inference engine (facts + IF-THEN rules).

Knowledge base : a dict mapping fact keys ``(predicate, subject)`` to values.
                 A fact "holds" when its key is present.
Rules          : each rule scans the knowledge base, and for every match returns the
                 facts it can add.  The engine keeps firing rules until a full pass adds
                 no new fact (a fixed point), logging every inference step.

Initial facts are computed from the user's saved appliances (monthly kWh, share of
total, flexibility, standby energy, hours above the user's minimum) and, for flexible
appliances, from a one-appliance "cheaper slot" lookup that respects the window,
unavailable hours and capacity settings.  Nothing is invented: every number comes from
the stored appliance data or the explicit parameters below.
"""
import time

from ai.scheduling_problem import SchedulingProblem, fmt_hour
from services import energy_calculator as ec

DEFAULT_PARAMS = {
    "high_share_pct": 25.0,       # flag appliances using >= this % of total monthly kWh ...
    "high_monthly_kwh": 100.0,    # ... or >= this many kWh per month
    "min_saving_rs": 1.0,         # ignore reschedule savings below this (Rs / month)
    "min_standby_kwh": 0.5,       # ignore standby below this many kWh / month
    "standby_avoidable_pct": 80.0,  # assumption: share of standby energy that can be avoided
    "reduce_fraction": 0.10,      # assumption: trim up to 10 % of daily hours of flagged appliances
}

RESCHEDULE_FEASIBILITY = {1: 0.70, 2: 0.85, 3: 0.95}
REDUCE_FEASIBILITY = {1: 0.30, 2: 0.50, 3: 0.70}
STANDBY_FEASIBILITY = 0.85


# --------------------------------------------------------------------------- #
# Facts
# --------------------------------------------------------------------------- #
def _ids(kb):
    return [k[1] for k in kb if k[0] == "appliance"]


def _name(kb, subject):
    if isinstance(subject, str) and ":" in subject:
        subject = int(subject.split(":")[0])
    info = kb.get(("appliance", subject))
    return info["name"] if info else str(subject)


def fact_str(kb, key):
    pred, subject = key
    label = _name(kb, subject)
    if isinstance(subject, str) and ":" in subject:
        label += f"/{subject.split(':')[1]}"
    value = kb.get(key)
    if isinstance(value, bool) or value is None or key[0] == "appliance":
        return f"{pred}({label})"
    if isinstance(value, float):
        return f"{pred}({label}) = {value:.2f}"
    if isinstance(value, dict) and "monthly_rs_saved" in value:
        return f"{pred}({label}) [saves Rs {value['monthly_rs_saved']:.2f}/month]"
    if isinstance(value, dict) and "start" in value:
        return f"{pred}({label}) [start {fmt_hour(value['start'])}, saves Rs {value['monthly_cost_saving']:.2f}/month]"
    if isinstance(value, dict):
        return f"{pred}({label})"
    return f"{pred}({label}) = {value}"


def best_single_move(problem, block, load):
    """Cheapest valid start for ONE flexible appliance with all others left where they are."""
    cur = block.preferred_start
    load_wo = problem.add_load(load, block, cur, sign=-1.0)
    best = None
    for s in problem.domain(block):
        if s == cur or not problem.fits(block, s, load_wo):
            continue
        obj = problem.step_cost(block, s)
        if best is None or obj < best[0]:
            best = (obj, s)
    if best is None or best[0] >= problem.step_cost(block, cur) - 1e-9:
        return None
    s = best[1]
    return {"start": s, "current_start": cur,
            "monthly_cost_saving": problem.cost(block, cur) - problem.cost(block, s),
            "penalty": problem.penalty(block, s)}


def build_facts(appliances, tariff, config=None, params=None):
    p = {**DEFAULT_PARAMS, **(params or {})}
    problem = SchedulingProblem(appliances, tariff, config)
    original_load = problem.evaluate(problem.original_assignment())["hourly_load_kwh"]
    rate = float(tariff["base_rate"])
    metrics = {a["id"]: ec.appliance_metrics(a, rate) for a in appliances}
    total = sum(m["monthly_kwh"] for m in metrics.values())
    kb = {}
    for a in appliances:
        i, m = a["id"], metrics[a["id"]]
        kb[("appliance", i)] = {"name": a["name"], "priority": a["priority"], "data": a}
        kb[("monthly_kwh", i)] = float(m["monthly_kwh"])
        kb[("share_pct", i)] = float(m["monthly_kwh"] / total * 100.0) if total > 0 else 0.0
        if a["flexible"]:
            kb[("flexible", i)] = True
            if i in problem._by_id:
                move = best_single_move(problem, problem.block(i), original_load)
                if move:
                    kb[("cheaper_slot", i)] = move
        if (a.get("standby_w") or 0) > 0:
            kb[("standby_monthly_kwh", i)] = float(m["standby_monthly_kwh"])
        if a["hours_per_day"] > a["min_hours"] + 1e-9:
            kb[("above_min_hours", i)] = {"hours": a["hours_per_day"], "min_hours": a["min_hours"]}
    return kb, p, problem


# --------------------------------------------------------------------------- #
# Rules
# --------------------------------------------------------------------------- #
class Rule:
    def __init__(self, name, if_text, then_text, fn):
        self.name, self.if_text, self.then_text, self.fn = name, if_text, then_text, fn


def _avg_rate(problem, start, duration):
    sl = problem.slots(start, duration)
    return sum(problem.rates[h] for h in sl) / len(sl)


def r1_high_consumption(kb, p, problem):
    out = []
    for i in _ids(kb):
        if kb[("share_pct", i)] >= p["high_share_pct"] or kb[("monthly_kwh", i)] >= p["high_monthly_kwh"]:
            out.append({"because": [("monthly_kwh", i), ("share_pct", i)],
                        "derive": {("flag_review", i): True}})
    return out


def r2_reschedule(kb, p, problem):
    out = []
    for i in _ids(kb):
        slot = kb.get(("cheaper_slot", i))
        if ("flexible", i) in kb and slot and slot["monthly_cost_saving"] >= p["min_saving_rs"]:
            b = problem.block(i)
            cur_rate = _avg_rate(problem, slot["current_start"], b.duration)
            new_rate = _avg_rate(problem, slot["start"], b.duration)
            end = slot["start"] + b.duration
            payload = {
                "appliance_id": i, "appliance": b.name, "kind": "reschedule",
                "issue": (f"{b.name} is flexible but currently runs {fmt_hour(slot['current_start'])}-"
                          f"{fmt_hour(slot['current_start'] + b.duration)} at an average Rs {cur_rate:.2f}/kWh."),
                "action": (f"Start it at {fmt_hour(slot['start'])} (runs until {fmt_hour(end)}) instead of "
                           f"{fmt_hour(slot['current_start'])}."),
                "reason": (f"The same energy costs about Rs {new_rate:.2f}/kWh in the new slot. The slot lies inside "
                           "its allowed window, avoids your unavailable hours and respects the capacity limit."),
                "daily_kwh_saved": 0.0, "monthly_kwh_saved": 0.0,
                "monthly_rs_saved": float(slot["monthly_cost_saving"]),
                "feasibility": RESCHEDULE_FEASIBILITY.get(b.priority, 0.85),
                "assumptions": ("Rescheduling does not change kWh, only the price per kWh under your time-of-use "
                                "tariff settings. Assumes the appliance runs on all its operating days each month."),
            }
            out.append({"because": [("flexible", i), ("cheaper_slot", i)],
                        "derive": {("recommend_reschedule", i): payload}})
    return out


def r3_standby(kb, p, problem):
    out = []
    rate = float(problem.tariff["base_rate"])
    for i in _ids(kb):
        kwh = kb.get(("standby_monthly_kwh", i))
        if kwh is not None and kwh >= p["min_standby_kwh"]:
            a = kb[("appliance", i)]["data"]
            saved = kwh * p["standby_avoidable_pct"] / 100.0
            idle = max(0.0, 24 - a["hours_per_day"])
            payload = {
                "appliance_id": i, "appliance": a["name"], "kind": "standby",
                "issue": (f"{a['name']} draws {a['standby_w'] * a['quantity']:.1f} W on standby for about "
                          f"{idle:.1f} h/day (about {kwh:.2f} kWh/month)."),
                "action": "Switch it off at the socket (or use a smart plug / timer) when it is not in use.",
                "reason": "Standby energy provides no service while the appliance is idle.",
                "daily_kwh_saved": saved / a["days_per_month"], "monthly_kwh_saved": saved,
                "monthly_rs_saved": saved * rate,
                "feasibility": STANDBY_FEASIBILITY,
                "assumptions": (f"Uses the standby watts you entered; assumes {p['standby_avoidable_pct']:.0f}% of "
                                f"standby energy is avoidable, idle hours = 24 - hours/day on operating days, "
                                f"flat rate Rs {rate:.2f}/kWh."),
            }
            out.append({"because": [("standby_monthly_kwh", i)],
                        "derive": {("recommend_reduce_standby", i): payload}})
    return out


def r4_reduce_hours(kb, p, problem):
    out = []
    rate = float(problem.tariff["base_rate"])
    for i in _ids(kb):
        room = kb.get(("above_min_hours", i))
        if ("flag_review", i) in kb and room:
            a = kb[("appliance", i)]["data"]
            cut = min(room["hours"] * p["reduce_fraction"], room["hours"] - room["min_hours"])
            if cut < 0.05:
                continue
            power_kw = a["power_w"] * a["quantity"] / 1000.0
            daily = power_kw * cut
            monthly = daily * a["days_per_month"]
            payload = {
                "appliance_id": i, "appliance": a["name"], "kind": "reduce_hours",
                "issue": (f"{a['name']} is a high consumer: {kb[('monthly_kwh', i)]:.1f} kWh/month "
                          f"({kb[('share_pct', i)]:.0f}% of your total)."),
                "action": (f"Trim use by about {cut:.2f} h/day (from {a['hours_per_day']:g} h to "
                           f"{a['hours_per_day'] - cut:.2f} h); never below your minimum of {a['min_hours']:g} h."),
                "reason": ("Big consumers give the largest saving per hour trimmed; the cut is capped by the "
                           "minimum daily hours you specified."),
                "daily_kwh_saved": daily, "monthly_kwh_saved": monthly, "monthly_rs_saved": monthly * rate,
                "feasibility": REDUCE_FEASIBILITY.get(a["priority"], 0.5),
                "assumptions": (f"Assumes you can reduce use by {p['reduce_fraction'] * 100:.0f}% (limited by your "
                                f"minimum hours); flat rate Rs {rate:.2f}/kWh; operating days unchanged."),
            }
            out.append({"because": [("flag_review", i), ("above_min_hours", i)],
                        "derive": {("recommend_reduce_hours", i): payload}})
    return out


def r5_saving_opportunity(kb, p, problem):
    out = []
    for (pred, i), payload in list(kb.items()):
        if pred.startswith("recommend_") and payload["monthly_rs_saved"] > 0:
            out.append({"because": [(pred, i)],
                        "derive": {("saving_opportunity", f"{i}:{payload['kind']}"): dict(payload)}})
    return out


RULES = [
    Rule("R1 high-consumption", "monthly kWh >= threshold OR share of total >= threshold",
         "flag_review(appliance)", r1_high_consumption),
    Rule("R2 reschedule", "appliance is flexible AND a cheaper valid time slot exists",
         "recommend_reschedule(appliance)", r2_reschedule),
    Rule("R3 standby", "avoidable standby consumption is recorded",
         "recommend_reduce_standby(appliance)", r3_standby),
    Rule("R4 reduce-hours", "appliance is flagged for review AND runs longer than its minimum hours",
         "recommend_reduce_hours(appliance)", r4_reduce_hours),
    Rule("R5 saving-opportunity", "a recommended change saves cost/energy AND meets the user's constraints",
         "saving_opportunity(appliance, kind)", r5_saving_opportunity),
]


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
def forward_chain(kb, params, problem, max_passes=10):
    steps, passes, changed = [], 0, True
    while changed and passes < max_passes:
        changed, passes = False, passes + 1
        for rule in RULES:
            for firing in rule.fn(kb, params, problem):
                new = {k: v for k, v in firing["derive"].items() if k not in kb}
                if not new:
                    continue
                kb.update(new)
                changed = True
                steps.append({
                    "step": len(steps) + 1, "pass": passes, "rule": rule.name,
                    "if": rule.if_text, "then": rule.then_text,
                    "matched": [fact_str(kb, k) for k in firing["because"]],
                    "derived": [fact_str(kb, k) for k in new],
                })
    return steps, passes


def run_forward_chaining(appliances, tariff, config=None, params=None):
    t0 = time.perf_counter()
    kb, p, problem = build_facts(appliances, tariff, config, params)
    initial = [fact_str(kb, k) for k in kb if k[0] != "appliance"]
    initial_count = len(kb)
    steps, passes = forward_chain(kb, p, problem)
    recs = [dict(v) for (pred, _), v in kb.items() if pred == "saving_opportunity"]
    for r in recs:
        r["score"] = r["monthly_rs_saved"] * r["feasibility"]
    recs.sort(key=lambda r: (-r["score"], r["appliance"]))
    for rank, r in enumerate(recs, 1):
        r["rank"] = rank
    flagged = [kb[("appliance", i)]["name"] for i in _ids(kb) if ("flag_review", i) in kb]
    runtime = (time.perf_counter() - t0) * 1000
    if not appliances:
        expl = "No appliances were provided, so no facts could be asserted."
    elif recs:
        expl = (f"Starting from {initial_count} facts, {len(steps)} rule firing(s) in {passes} pass(es) derived "
                f"{len(recs)} saving opportunit{'y' if len(recs) == 1 else 'ies'}. Inference stopped when a full "
                "pass produced no new facts (fixed point).")
    else:
        expl = (f"{len(steps)} rule firing(s) occurred but no rule produced a saving opportunity with the current "
                "appliance data and parameters.")
    return {
        "algorithm": "Forward Chaining", "found": bool(recs), "facts": initial,
        "rules": [{"name": r.name, "if": r.if_text, "then": r.then_text} for r in RULES],
        "inference_steps": steps, "recommendations": recs, "flagged_for_review": flagged,
        "stats": {"initial_facts": initial_count, "rules_fired": len(steps), "passes": passes,
                  "recommendations": len(recs)},
        "params": p, "explanation": expl, "runtime_ms": round(runtime, 3),
    }
