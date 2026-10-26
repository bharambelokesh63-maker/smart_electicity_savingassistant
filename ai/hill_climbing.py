"""Steepest-ascent Hill Climbing (descent on cost) for appliance scheduling.

State        : a complete valid schedule (start hour for every flexible appliance).
Initial state: the user's original schedule if it already satisfies every hard
               constraint; otherwise the first valid schedule found by CSP backtracking.
Neighbours   : move ONE flexible appliance to a different start hour in its domain,
               keeping the hourly capacity limit satisfied.
Objective    : f(schedule) = monthly energy cost (time-of-use rates)
               + soft penalties (shifting away from the preferred time, leaving the
               user's preferred hours).  Lower is better.
Strategy     : at each iteration examine ALL neighbours and move to the one with the
               largest decrease; stop when no neighbour improves the objective (a *local*
               optimum - not necessarily the global optimum) or when the iteration limit
               is reached.
"""
import time

from ai.csp_scheduler import csp_backtracking
from ai.scheduling_problem import fmt_hour


def hill_climbing(problem, max_iterations=100):
    t0 = time.perf_counter()
    reasons = problem.diagnose()
    if reasons:
        return problem.package("Hill Climbing", None, runtime_ms=(time.perf_counter() - t0) * 1000,
                               explanation="No valid starting schedule exists: " + " ".join(reasons),
                               stats={"iterations": 0})

    original = problem.original_assignment()
    if problem.evaluate(original)["feasible"]:
        current, source = dict(original), "the original schedule (it already satisfies all hard constraints)"
    else:
        csp = csp_backtracking(problem, value_order="preferred")
        if not csp["found"]:
            return problem.package("Hill Climbing", None, runtime_ms=(time.perf_counter() - t0) * 1000,
                                   explanation="The original schedule violates hard constraints and CSP could "
                                               "not repair it: " + csp["explanation"],
                                   stats={"iterations": 0})
        current = {int(k): v for k, v in csp["assignment"].items()}
        source = "a valid schedule found by CSP backtracking (the original schedule violates hard constraints)"

    ev = problem.evaluate(current)
    load, objective = ev["hourly_load_kwh"], ev["objective"]
    initial_objective = objective
    history = [{"iteration": 0, "objective": round(objective, 4), "move": "initial schedule",
                "delta": 0.0, "neighbors_evaluated": 0}]
    stop_reason, neighbors_total = "iteration limit reached", 0

    for it in range(1, max_iterations + 1):
        best, neighbors = None, 0
        for b in problem.flexible_blocks:
            cur = current[b.id]
            load_without = problem.add_load(load, b, cur, sign=-1.0)
            base_cost = problem.step_cost(b, cur)
            for s in problem.domain(b):
                if s == cur or not problem.fits(b, s, load_without):
                    continue
                neighbors += 1
                delta = problem.step_cost(b, s) - base_cost
                if delta < -1e-9 and (best is None or delta < best[0]):
                    best = (delta, b, s, cur)
        neighbors_total += neighbors
        if best is None:
            history.append({"iteration": it, "objective": round(objective, 4),
                            "move": "no improving neighbour", "delta": 0.0, "neighbors_evaluated": neighbors})
            stop_reason = "local optimum reached (no neighbour improves the objective)"
            break
        delta, b, s, cur = best
        load = problem.add_load(problem.add_load(load, b, cur, sign=-1.0), b, s)
        current[b.id] = s
        objective += delta
        history.append({"iteration": it, "objective": round(objective, 4),
                        "move": f"{b.name}: {fmt_hour(cur)} -> {fmt_hour(s)}",
                        "delta": round(delta, 4), "neighbors_evaluated": neighbors})

    final_objective = problem.evaluate(current)["objective"]
    runtime = (time.perf_counter() - t0) * 1000
    result = problem.package(
        "Hill Climbing", current, log=history, runtime_ms=runtime,
        stats={"iterations": len(history) - 1, "neighbors_evaluated": neighbors_total},
        explanation=(
            f"Started from {source} with objective Rs {initial_objective:.2f}. Each iteration moved the single "
            f"appliance giving the largest decrease. Stopped: {stop_reason}. Final objective "
            f"Rs {final_objective:.2f}. Hill climbing only guarantees a LOCAL optimum; with capacity limits "
            "it can stop before reaching the best possible schedule."
        ),
        extra={"initial_objective": initial_objective, "final_objective": final_objective,
               "initial_source": source, "stop_reason": stop_reason,
               "local_optimum": stop_reason.startswith("local")},
    )
    return result
