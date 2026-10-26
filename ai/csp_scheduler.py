"""Constraint Satisfaction Problem (CSP) solver with recursive backtracking.

Variables   : one per flexible appliance (its start hour).
Domains     : start hours permitted by the *unary* constraints
              - the appliance's operating window,
              - its required duration (block must fit entirely inside the window),
              - the user's unavailable hours.
Constraints : unary constraints above (applied by pruning domains) and the
              *global* capacity constraint - for every hour, total load of all placed
              appliances (plus the fixed ones) <= capacity_kw (if a capacity is set).
Variable selection : Minimum Remaining Values (MRV) - choose the unassigned variable
              with the fewest currently legal values (ties: higher power draw first).
Value ordering     : ``cost`` (cheapest placement first) or ``preferred`` (closest to the
              user's preferred start first).
Search      : depth-first recursive backtracking; returns the first complete valid
              assignment found, or reports failure with an explanation.
"""
import time

LOG_LIMIT = 300


def csp_backtracking(problem, value_order="cost", max_backtracks=200000):
    t0 = time.perf_counter()
    variables = problem.flexible_blocks
    stats = {
        "variables": len(variables), "nodes_visited": 0, "backtracks": 0,
        "values_pruned_by_unary_constraints": sum(problem.unary_pruned(b) for b in variables),
        "capacity_violations_avoided": 0, "truncated": False,
    }
    constraints = [
        "Window: each flexible appliance must run entirely inside its allowed operating window.",
        "Duration: each appliance needs ceil(hours per day) consecutive one-hour slots.",
        f"Availability: no flexible appliance may use unavailable hours {sorted(problem.unavailable) or '(none set)'}.",
        (f"Capacity: total load in every hour <= {problem.capacity:.2f} kW."
         if problem.capacity is not None else "Capacity: no limit set."),
    ]
    log = []

    def note(entry):
        if len(log) < LOG_LIMIT:
            log.append(entry)

    reasons = problem.diagnose()
    if reasons:
        return problem.package(
            "CSP Backtracking", None, log=log, stats=stats,
            runtime_ms=(time.perf_counter() - t0) * 1000,
            explanation="No valid schedule exists: " + " ".join(reasons),
            extra={"constraints": constraints, "domains": problem.describe()["domains"]},
        )

    def ordered_values(b, load):
        legal, rejected = [], 0
        for s in problem.domain(b):
            if problem.fits(b, s, load):
                legal.append(s)
            else:
                rejected += 1
        if value_order == "preferred":
            legal.sort(key=lambda s: (abs(s - b.preferred_start), s))
        else:
            legal.sort(key=lambda s: (problem.step_cost(b, s), s))
        return legal, rejected

    def legal_count(b, load):
        return sum(1 for s in problem.domain(b) if problem.fits(b, s, load))

    solution = {}

    def backtrack(unassigned, partial, load):
        if stats["backtracks"] > max_backtracks:
            stats["truncated"] = True
            return False
        if not unassigned:
            solution.update(partial)
            return True
        stats["nodes_visited"] += 1
        # MRV: fewest legal values, then biggest load
        var = min(unassigned, key=lambda b: (legal_count(b, load), -b.power_kw, b.id))
        values, rejected = ordered_values(var, load)
        stats["capacity_violations_avoided"] += rejected
        note({"event": "select", "variable": var.name, "legal_values": [f"{s:02d}:00" for s in values],
              "rejected_for_capacity": rejected, "depth": len(partial)})
        rest = [b for b in unassigned if b.id != var.id]
        for s in values:
            note({"event": "assign", "variable": var.name, "value": f"{s:02d}:00", "depth": len(partial) + 1})
            partial[var.id] = s
            if backtrack(rest, partial, problem.add_load(load, var, s)):
                return True
            del partial[var.id]
            stats["backtracks"] += 1
            note({"event": "backtrack", "variable": var.name, "value": f"{s:02d}:00", "depth": len(partial)})
            if stats["truncated"]:
                return False
        return False

    ok = backtrack(variables, {}, problem.base_load())
    runtime = (time.perf_counter() - t0) * 1000
    extra = {"constraints": constraints, "domains": problem.describe()["domains"],
             "variable_selection": "Minimum Remaining Values (MRV)", "value_order": value_order}
    if not ok:
        msg = ("Backtracking stopped at the backtrack limit; no schedule is reported."
               if stats["truncated"] else
               "Every combination of start hours was ruled out by the constraints: no valid schedule exists. "
               + " ".join(problem.diagnose()))
        return problem.package("CSP Backtracking", None, log=log, stats=stats, runtime_ms=runtime,
                               explanation=msg, extra=extra)
    assignment = {b.id: b.preferred_start for b in problem.fixed_blocks}
    assignment.update(solution)
    result = problem.package(
        "CSP Backtracking", assignment, log=log, stats=stats, runtime_ms=runtime, extra=extra,
        explanation=(
            f"Found a valid assignment for all {len(variables)} flexible appliance(s) after visiting "
            f"{stats['nodes_visited']} node(s) with {stats['backtracks']} backtrack(s). Constraint checks "
            f"removed {stats['values_pruned_by_unary_constraints']} start time(s) up front (window / duration / "
            f"availability) and rejected {stats['capacity_violations_avoided']} placement(s) that would have "
            f"exceeded the capacity limit. Values are tried in '{value_order}' order, so the first complete "
            "valid schedule is returned (valid, not necessarily optimal)."
        ),
    )
    result["violations_found"] = len(result["schedule"]["violations"])
    return result
