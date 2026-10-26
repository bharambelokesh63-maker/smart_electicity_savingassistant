"""Generic state-space search over the appliance-scheduling problem.

Used by both Best-First (greedy) search and A* search; the two differ ONLY in
the priority function that orders the frontier.

State representation
    A partial schedule: ``starts`` is a tuple holding the chosen start hour for
    the first ``depth`` flexible appliances (appliances are assigned in the fixed
    order given by ``problem.search_order()`` - most constrained first).
    ``load`` is the hourly load (kWh/h) of the fixed appliances plus every
    appliance placed so far.

Actions / transitions
    Place the next flexible appliance at any start hour in its domain that keeps
    every hour's load within the optional capacity limit.

Cost g(n)
    Sum of ``step_cost`` (monthly energy cost + soft penalty) of the placements
    made so far.  Every step cost is >= 0.

Heuristic h(n)
    Sum, over the appliances that are still unplaced, of the cheapest step cost
    that appliance could ever have if capacity were ignored.  Because capacity can
    only remove options, h(n) never over-estimates the true remaining cost
    (admissible), and h(parent) <= step_cost + h(child) (consistent).

Goal
    Every flexible appliance has been placed (depth == number of flexible
    appliances).  Hard constraints (window, duration, unavailable hours, capacity)
    are enforced when actions are generated, so any goal state is valid.
"""
import heapq
import time

LOG_LIMIT = 300  # maximum number of explored states returned to the UI


def search(problem, priority_fn, algorithm, max_expansions=20000):
    t0 = time.perf_counter()
    order = problem.search_order()
    n = len(order)

    reasons = problem.diagnose()
    if reasons:
        return problem.package(
            algorithm, None, runtime_ms=(time.perf_counter() - t0) * 1000,
            explanation="No valid schedule exists: " + " ".join(reasons),
            stats={"expanded": 0, "generated": 0, "truncated": False},
            extra={"path": [], "optimal": False},
        )

    min_costs = [problem.min_step_cost(b) for b in order]
    suffix = [0.0] * (n + 1)          # suffix[i] = h(n) for a node at depth i
    for i in range(n - 1, -1, -1):
        suffix[i] = suffix[i + 1] + min_costs[i]

    counter = 0
    heap = []
    root = (0, (), problem.base_load(), 0.0)
    heapq.heappush(heap, (priority_fn(0.0, suffix[0], 0), counter, root))
    stats = {"expanded": 0, "generated": 1, "capacity_rejections": 0, "max_frontier": 1, "truncated": False}
    log = []
    goal = None

    while heap:
        if stats["expanded"] >= max_expansions:
            stats["truncated"] = True
            break
        _, _, (depth, starts, load, g) = heapq.heappop(heap)
        stats["expanded"] += 1
        h = suffix[depth]
        if len(log) < LOG_LIMIT:
            placed = ", ".join(f"{order[i].name}@{starts[i]:02d}:00" for i in range(depth)) or "(nothing placed)"
            log.append({
                "step": stats["expanded"], "depth": depth, "state": placed,
                "last": (f"{order[depth - 1].name} -> {starts[-1]:02d}:00" if depth else "start"),
                "g": round(g, 4), "h": round(h, 4), "f": round(g + h, 4), "goal": depth == n,
            })
        if depth == n:
            goal = (starts, g)
            break
        b = order[depth]
        for s in problem.domain(b):
            if not problem.fits(b, s, load):
                stats["capacity_rejections"] += 1
                continue
            step = problem.step_cost(b, s)
            child = (depth + 1, starts + (s,), problem.add_load(load, b, s), g + step)
            counter += 1
            stats["generated"] += 1
            heapq.heappush(heap, (priority_fn(child[3], suffix[depth + 1], depth + 1), counter, child))
        stats["max_frontier"] = max(stats["max_frontier"], len(heap))

    runtime = (time.perf_counter() - t0) * 1000
    if goal is None:
        if stats["truncated"]:
            msg = (f"Search stopped after {max_expansions} expansions without reaching a goal state. "
                   "No schedule is reported because none was verified.")
        else:
            msg = ("The search space was exhausted: no placement of all flexible appliances satisfies "
                   "every hard constraint. " + " ".join(problem.diagnose()))
        return problem.package(algorithm, None, log=log, stats=stats, runtime_ms=runtime,
                               explanation=msg, extra={"path": [], "optimal": False})

    starts, g_goal = goal
    assignment = {b.id: b.preferred_start for b in problem.fixed_blocks}
    path, running = [], 0.0
    for i, b in enumerate(order):
        assignment[b.id] = starts[i]
        step = problem.step_cost(b, starts[i])
        running += step
        path.append({"depth": i + 1, "appliance": b.name, "start": starts[i],
                     "start_label": f"{starts[i]:02d}:00", "step_cost": round(step, 4),
                     "g": round(running, 4)})
    stats["goal_cost"] = round(g_goal, 4)
    return problem.package(algorithm, assignment, log=log, stats=stats, runtime_ms=runtime,
                           extra={"path": path, "optimal": False,
                                  "log_truncated": stats["expanded"] > LOG_LIMIT})
