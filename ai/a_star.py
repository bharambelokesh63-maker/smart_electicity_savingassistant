"""A* search for appliance scheduling.

f(n) = g(n) + h(n)

* g(n): actual accumulated cost of the placements made so far.
* h(n): sum of each unplaced appliance's cheapest possible cost (capacity ignored).
  Admissible and consistent (see ``state_space`` for the argument).
* Ties in f are broken in favour of deeper nodes so the search reaches a goal quickly.

Optimality statement: the returned schedule is optimal *for the modelled objective*
(energy cost + soft penalty) when the search finishes without hitting the expansion
limit - because step costs are non-negative, the state space is finite, h is
admissible/consistent, and the goal test is applied when a node is removed from the
priority queue.  If the expansion limit is reached the result is reported as a failure,
not as an optimum.
"""
from ai.state_space import search


def a_star_search(problem, max_expansions=20000):
    result = search(problem, lambda g, h, depth: (g + h, -depth), "A* Search", max_expansions)
    if result["found"]:
        result["optimal"] = not result["stats"]["truncated"]
        result["explanation"] = (
            f"A* removed a complete schedule from the priority queue with total cost g = "
            f"{result['stats']['goal_cost']:.2f} (energy cost + penalty, Rs/month) after expanding "
            f"{result['stats']['expanded']} state(s). Because h(n) is admissible and consistent and all "
            "step costs are non-negative, no cheaper complete schedule exists under the modelled "
            "constraints. The schedule beats the original by "
            f"Rs {result['objective_improvement']:.2f} in objective value."
        )
    return result
