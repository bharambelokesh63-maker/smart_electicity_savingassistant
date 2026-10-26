"""A small, fully documented Bayesian Network for household energy category.

Structure (a directed acyclic graph)

    UsageIntensity --\\
    HighPowerCount ---+--> ConsumptionCategory
    StandbyLevel   --/

* UsageIntensity  : Light / Normal / Heavy  - total appliance-hours per day
                    (sum of quantity x hours/day; < 30 = Light, 30-80 = Normal, > 80 = Heavy).
* HighPowerCount  : None / Few / Many       - number of appliances rated >= 1000 W in total
                    (0 = None, 1-2 = Few, >= 3 = Many).
* StandbyLevel    : Low / High              - standby energy as a share of total energy
                    (>= 10 % = High). Unobserved when the user entered no standby data.
* ConsumptionCategory : Low / Moderate / High  - the query variable.

Priors P(parent) and the conditional probability table P(Category | parents) are
EDUCATIONAL ASSUMPTIONS written down explicitly below. The CPT is generated from an
additive "load score" (usage level + power level + standby level, 0-5) so that it is
monotone: more intensive evidence never makes a Low category more likely. Every row
sums to 1 (checked by ``validate``).

Inference is exact, by enumeration of the joint distribution:

    P(Q | e) = alpha * sum over hidden variables of  prod_v P(v | parents(v))

Unobserved evidence variables are marginalised out, which is how the model handles
missing data (for example no standby information).

IMPORTANT: the result is an educational estimate under the stated model and
assumptions - not a measurement and not a guaranteed forecast.
"""
import itertools
import time

USAGE_STATES = ["Light", "Normal", "Heavy"]
POWER_STATES = ["None", "Few", "Many"]
STANDBY_STATES = ["Low", "High"]
CATEGORY_STATES = ["Low", "Moderate", "High"]

PRIORS = {
    "UsageIntensity": {"Light": 0.30, "Normal": 0.50, "Heavy": 0.20},
    "HighPowerCount": {"None": 0.30, "Few": 0.50, "Many": 0.20},
    "StandbyLevel": {"Low": 0.70, "High": 0.30},
}

# P(category | load score) where score = usage_level + power_level + standby_level (0..5)
SCORE_TABLE = {
    0: (0.85, 0.13, 0.02),
    1: (0.70, 0.25, 0.05),
    2: (0.45, 0.40, 0.15),
    3: (0.20, 0.45, 0.35),
    4: (0.08, 0.32, 0.60),
    5: (0.03, 0.17, 0.80),
}


def _category_cpt():
    cpt = {}
    for u, p, s in itertools.product(USAGE_STATES, POWER_STATES, STANDBY_STATES):
        score = USAGE_STATES.index(u) + POWER_STATES.index(p) + STANDBY_STATES.index(s)
        cpt[(u, p, s)] = dict(zip(CATEGORY_STATES, SCORE_TABLE[score]))
    return cpt


class BayesianNetwork:
    def __init__(self):
        # variables listed in topological order
        self.states = {
            "UsageIntensity": USAGE_STATES, "HighPowerCount": POWER_STATES,
            "StandbyLevel": STANDBY_STATES, "ConsumptionCategory": CATEGORY_STATES,
        }
        self.parents = {
            "UsageIntensity": [], "HighPowerCount": [], "StandbyLevel": [],
            "ConsumptionCategory": ["UsageIntensity", "HighPowerCount", "StandbyLevel"],
        }
        self.cpt = {v: {(): dict(PRIORS[v])} for v in PRIORS}
        self.cpt["ConsumptionCategory"] = _category_cpt()

    # ----------------------------------------------------------------- checks
    def validate(self, tol=1e-9):
        """Raise ValueError if any CPT row is not a probability distribution."""
        for var, table in self.cpt.items():
            combos = list(itertools.product(*[self.states[p] for p in self.parents[var]]))
            if set(table) != set(combos):
                raise ValueError(f"CPT of {var} does not cover every parent combination")
            for key, dist in table.items():
                if abs(sum(dist.values()) - 1.0) > tol or any(p < 0 for p in dist.values()):
                    raise ValueError(f"CPT row {var}|{key} is not a valid distribution")
        return True

    # -------------------------------------------------------------- inference
    def joint(self, assignment):
        prob = 1.0
        for var in self.states:
            key = tuple(assignment[p] for p in self.parents[var])
            prob *= self.cpt[var][key][assignment[var]]
        return prob

    def query(self, target, evidence=None):
        """Exact posterior P(target | evidence) by enumeration.

        Returns (distribution, probability_of_evidence)."""
        evidence = evidence or {}
        for var, val in evidence.items():
            if var not in self.states or val not in self.states[var]:
                raise ValueError(f"Invalid evidence {var}={val}")
        unnormalised = {}
        for t in self.states[target]:
            fixed = dict(evidence)
            fixed[target] = t
            hidden = [v for v in self.states if v not in fixed]
            total = 0.0
            for combo in itertools.product(*[self.states[v] for v in hidden]):
                full = dict(fixed)
                full.update(zip(hidden, combo))
                total += self.joint(full)
            unnormalised[t] = total
        z = sum(unnormalised.values())
        return {k: v / z for k, v in unnormalised.items()}, z

    def cpt_rows(self):
        rows = []
        for (u, p, s), dist in self.cpt["ConsumptionCategory"].items():
            rows.append({"UsageIntensity": u, "HighPowerCount": p, "StandbyLevel": s,
                         **{k: round(v, 4) for k, v in dist.items()},
                         "row_sum": round(sum(dist.values()), 6)})
        return rows


# --------------------------------------------------------------------------- #
# Evidence from appliance data
# --------------------------------------------------------------------------- #
def derive_evidence(appliances):
    """Discretise saved appliance data into evidence values (with the numbers used)."""
    if not appliances:
        return {}, {}
    appliance_hours = sum(a["quantity"] * a["hours_per_day"] for a in appliances)
    high_power = sum(1 for a in appliances if a["power_w"] >= 1000)
    active = sum(a["power_w"] * a["quantity"] * a["hours_per_day"] * a["days_per_month"] / 1000.0
                 for a in appliances)
    standby = sum((a.get("standby_w") or 0) * a["quantity"] * max(0.0, 24 - a["hours_per_day"])
                  * a["days_per_month"] / 1000.0 for a in appliances)
    evidence = {
        "UsageIntensity": "Light" if appliance_hours < 30 else ("Normal" if appliance_hours <= 80 else "Heavy"),
        "HighPowerCount": "None" if high_power == 0 else ("Few" if high_power <= 2 else "Many"),
    }
    has_standby = any((a.get("standby_w") or 0) > 0 for a in appliances)
    standby_share = standby / (active + standby) * 100.0 if (active + standby) > 0 else 0.0
    if has_standby:
        evidence["StandbyLevel"] = "High" if standby_share >= 10.0 else "Low"
    numbers = {
        "appliance_hours_per_day": appliance_hours, "high_power_appliances": high_power,
        "standby_share_percent": standby_share if has_standby else None,
        "monthly_kwh": active + standby,
    }
    return evidence, numbers


def rule_of_thumb_band(monthly_kwh):
    """Plain consumption bands used ONLY as a sanity comparison (assumed thresholds)."""
    if monthly_kwh < 150:
        return "Low"
    return "Moderate" if monthly_kwh <= 300 else "High"


def run_bayesian_network(appliances, overrides=None):
    """overrides: {variable: 'auto' | 'none' | <state>} for the three evidence variables."""
    t0 = time.perf_counter()
    net = BayesianNetwork()
    net.validate()
    auto, numbers = derive_evidence(appliances)
    overrides = overrides or {}
    evidence, notes = {}, []
    for var in ("UsageIntensity", "HighPowerCount", "StandbyLevel"):
        choice = overrides.get(var, "auto")
        if choice == "auto":
            if var in auto:
                evidence[var] = auto[var]
                notes.append(f"{var} = {auto[var]} (derived from your appliances)")
            else:
                notes.append(f"{var}: no data available, treated as unobserved (marginalised out)")
        elif choice == "none":
            notes.append(f"{var}: left unobserved by the user (marginalised out)")
        elif choice in net.states[var]:
            evidence[var] = choice
            notes.append(f"{var} = {choice} (set manually)")
        else:
            raise ValueError(f"Invalid state '{choice}' for {var}")

    prior, _ = net.query("ConsumptionCategory", {})
    posterior, p_e = net.query("ConsumptionCategory", evidence)
    best = max(posterior, key=posterior.get)
    runtime = (time.perf_counter() - t0) * 1000
    band = rule_of_thumb_band(numbers["monthly_kwh"]) if numbers else None
    return {
        "algorithm": "Bayesian Network", "found": True,
        "structure": {"nodes": list(net.states), "edges": [[p, "ConsumptionCategory"] for p in
                                                           net.parents["ConsumptionCategory"]]},
        "states": net.states, "priors": PRIORS, "cpt": net.cpt_rows(),
        "evidence": evidence, "evidence_notes": notes, "data_summary": numbers,
        "prior": prior, "posterior": posterior, "most_probable": best,
        "probability_of_evidence": p_e, "posterior_sum": sum(posterior.values()),
        "rule_of_thumb_band": band,
        "comparison_note": (
            f"For comparison only: your estimated {numbers['monthly_kwh']:.0f} kWh/month falls in the '{band}' band of a "
            "simple threshold rule (<150 Low, 150-300 Moderate, >300 High). The network uses coarse evidence "
            "(usage intensity, number of high-power appliances, standby share) and assumed probabilities, so it "
            "can disagree with that rule; neither is a measurement of your real bill." if numbers else ""),
        "stats": {"variables": 4, "cpt_rows": len(net.cpt["ConsumptionCategory"]),
                  "joint_terms_enumerated": 3 * 3 * 3 * 2 * 3},
        "runtime_ms": round(runtime, 3),
        "explanation": (
            f"Given the evidence ({'; '.join(f'{k}={v}' for k, v in evidence.items()) or 'none'}), exact inference by "
            f"enumeration gives P({best}) = {posterior[best]:.1%} for the most probable category. This is an "
            "educational estimate based on the stated priors and CPT assumptions - not a measurement or a "
            "guaranteed forecast."),
    }
