"""Schedule optimizer: runs one of the scheduling algorithms and compares the result
with the user's original schedule."""
from ai.a_star import a_star_search
from ai.best_first import best_first_search
from ai.csp_scheduler import csp_backtracking
from ai.hill_climbing import hill_climbing
from ai.scheduling_problem import SchedulingProblem

METHODS = {
    "astar": "A* Search",
    "best_first": "Best-First Search",
    "hill_climbing": "Hill Climbing",
    "csp": "CSP Backtracking",
}


def run_method(problem, method, config):
    if method == "astar":
        return a_star_search(problem, max_expansions=config.get("max_expansions", 20000))
    if method == "best_first":
        return best_first_search(problem, max_expansions=config.get("max_expansions", 20000))
    if method == "hill_climbing":
        return hill_climbing(problem, max_iterations=config.get("max_iterations", 100))
    if method == "csp":
        return csp_backtracking(problem, value_order=config.get("value_order", "cost"))
    raise ValueError(f"Unknown method '{method}'. Choose one of: {', '.join(METHODS)}.")


def optimize_schedule(appliances, tariff, config=None, method="astar"):
    config = config or {}
    if method not in METHODS:
        raise ValueError(f"Unknown method '{method}'. Choose one of: {', '.join(METHODS)}.")
    problem = SchedulingProblem(appliances, tariff, config)
    result = run_method(problem, method, config)
    fallback = None
    if not result["found"] and result["stats"].get("truncated") and method in ("astar", "best_first"):
        fallback = f"{METHODS[method]} hit its expansion limit, so Hill Climbing was used instead."
        result = run_method(problem, "hill_climbing", config)
    original = result["original"]
    out = {
        "method": METHODS[method], "method_key": method, "found": result["found"],
        "fallback": fallback, "original": original, "optimized": result.get("schedule"),
        "moved": result.get("moved", []), "explanation": result["explanation"],
        "diagnosis": result.get("diagnosis", []), "algorithm_result": result,
        "original_violations": original["violations"],
        "has_flexible": bool(problem.flexible_blocks),
        "problem": result["problem"],
    }
    if result["found"]:
        opt = result["schedule"]
        saving = original["energy_cost"] - opt["energy_cost"]
        out["comparison"] = {
            "original_cost": original["energy_cost"], "optimized_cost": opt["energy_cost"],
            "cost_saving": saving,
            "cost_saving_percent": (saving / original["energy_cost"] * 100.0) if original["energy_cost"] else 0.0,
            "original_kwh": original["monthly_kwh"], "optimized_kwh": opt["monthly_kwh"],
            "kwh_change": opt["monthly_kwh"] - original["monthly_kwh"],
            "original_penalty": original["penalty"], "optimized_penalty": opt["penalty"],
            "original_objective": original["objective"], "optimized_objective": opt["objective"],
            "original_peak_kw": original["peak_load_kw"], "optimized_peak_kw": opt["peak_load_kw"],
        }
    else:
        out["comparison"] = None
    return out
