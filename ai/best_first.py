"""Greedy Best-First Search for appliance scheduling.

The frontier is a priority queue ordered by the heuristic alone:

    priority(n) = h(n)         (ties broken by smaller g(n))

h(n) = estimated remaining cost = sum of each unplaced appliance's cheapest possible
placement (capacity ignored).  Nodes with fewer unplaced appliances therefore have a
lower h and are expanded first, so the search "dives" towards a complete schedule and,
among siblings, prefers the locally cheapest slot.  It is fast but ignores the cost
already spent beyond tie-breaking, so it gives NO optimality guarantee.
"""
from ai.state_space import search


def best_first_search(problem, max_expansions=20000):
    result = search(problem, lambda g, h, depth: (h, g), "Best-First Search", max_expansions)
    result["optimal"] = False
    if result["found"]:
        result["explanation"] = (
            f"Greedy best-first search followed the lowest-h states and reached a complete schedule after "
            f"expanding {result['stats']['expanded']} state(s). It picks the cheapest-looking slot for each "
            "appliance in turn and backtracks only when the capacity limit blocks a branch, so the result is "
            "a good schedule but is not guaranteed to be the cheapest (use A* for that guarantee)."
        )
    return result
