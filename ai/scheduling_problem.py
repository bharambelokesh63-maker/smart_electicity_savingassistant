"""Shared model of the appliance-scheduling problem.

All search / local-search / CSP algorithms in this package work on the same
``SchedulingProblem`` object, so their results are directly comparable.

Model
-----
* Time is divided into 24 one-hour slots (0 = 00:00-01:00 ... 23 = 23:00-24:00).
* Each appliance is one *block*: it runs for ``duration = ceil(hours_per_day)``
  consecutive hours starting at hour ``s``.  Its energy is spread evenly over
  those slots (``kwh_per_slot = power_kW x quantity x hours / duration``), so the
  total daily energy always equals the calculator formula.
* Non-flexible appliances are FIXED at their preferred start hour.
* Flexible appliances are VARIABLES whose domain is every start hour ``s`` with
  ``window_start <= s`` and ``s + duration <= window_end`` such that none of the
  occupied hours is in the user's "unavailable hours".
* Optional hard constraint: total load in any hour must not exceed ``capacity_kw``
  (a typical operating day is assumed).
* Cost of a placement = monthly energy cost using hourly (time-of-use) rates
  + a documented soft penalty (see ``penalty``).  Objective = cost + penalty;
  lower is better.
"""
import math
from dataclasses import dataclass

PRIORITY_WEIGHT = {1: 3.0, 2: 2.0, 3: 1.0}   # high-priority appliances are costlier to move
EPS = 1e-9


def hour_in_range(hour, start, end):
    """True if ``hour`` lies in [start, end), supporting ranges that wrap past midnight."""
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def hourly_rates(tariff):
    """24 Rs/kWh values.  Flat base rate unless time-of-use (ToU) is enabled."""
    base = float(tariff["base_rate"])
    rates = [base] * 24
    if tariff.get("tou_enabled"):
        for h in range(24):
            if hour_in_range(h, tariff["peak_start"], tariff["peak_end"]):
                rates[h] = base * float(tariff["peak_multiplier"])
            elif hour_in_range(h, tariff["offpeak_start"], tariff["offpeak_end"]):
                rates[h] = base * float(tariff["offpeak_multiplier"])
    return rates


def fmt_hour(h):
    return f"{h % 24:02d}:00"


@dataclass
class Block:
    id: int
    name: str
    power_kw: float          # rated kW x quantity
    hours: float
    duration: int            # whole one-hour slots
    days: int
    window_start: int
    window_end: int
    preferred_start: int
    flexible: bool
    priority: int

    @property
    def kwh_per_slot(self):
        return self.power_kw * self.hours / self.duration


class SchedulingProblem:
    def __init__(self, appliances, tariff, config=None):
        cfg = config or {}
        self.tariff = tariff
        self.rates = hourly_rates(tariff)
        self.unavailable = set(int(h) for h in cfg.get("unavailable_hours") or [])
        self.preferred_hours = set(int(h) for h in cfg.get("preferred_hours") or [])
        cap = cfg.get("capacity_kw")
        self.capacity = float(cap) if cap not in (None, "") else None
        if self.capacity is not None and self.capacity <= 0:
            raise ValueError("capacity_kw must be positive")
        self.shift_penalty = float(cfg.get("shift_penalty", 3.0))
        self.preference_penalty = float(cfg.get("preference_penalty", 2.0))
        self.blocks = []
        for a in appliances:
            hours = float(a["hours_per_day"])
            if hours <= 0:
                continue
            duration = max(1, min(24, math.ceil(hours - 1e-12)))
            self.blocks.append(Block(
                id=a["id"], name=a["name"],
                power_kw=float(a["power_w"]) * int(a["quantity"]) / 1000.0,
                hours=hours, duration=duration, days=int(a["days_per_month"]),
                window_start=int(a.get("window_start", 0)), window_end=int(a.get("window_end", 24)),
                preferred_start=int(a.get("preferred_start", 0)) % 24,
                flexible=bool(a.get("flexible")), priority=int(a.get("priority", 2)),
            ))
        self._by_id = {b.id: b for b in self.blocks}

    # ------------------------------------------------------------------ basics
    def block(self, block_id):
        return self._by_id[block_id]

    @property
    def flexible_blocks(self):
        return [b for b in self.blocks if b.flexible]

    @property
    def fixed_blocks(self):
        return [b for b in self.blocks if not b.flexible]

    @staticmethod
    def slots(start, duration):
        return [(start + i) % 24 for i in range(duration)]

    def domain(self, b):
        """Permitted start hours (unary constraints: window, duration, availability)."""
        if not b.flexible:
            return [b.preferred_start]
        return [
            s for s in range(b.window_start, b.window_end - b.duration + 1)
            if not any(h in self.unavailable for h in self.slots(s, b.duration))
        ]

    def unary_pruned(self, b):
        """How many of the 24-duration+1 possible start hours the unary constraints removed."""
        if not b.flexible:
            return 0
        return (24 - b.duration + 1) - len(self.domain(b))

    # ------------------------------------------------------------------- costs
    def cost(self, b, start):
        """Monthly energy cost (Rs) if block ``b`` starts at ``start``."""
        rate_sum = sum(self.rates[h] for h in self.slots(start, b.duration))
        return b.kwh_per_slot * rate_sum * b.days

    def penalty(self, b, start):
        """Soft penalty (Rs-equivalent per month) for deviating from the user's habits.

        * shift penalty = shift_penalty x priority weight x |start - preferred_start|
        * preference penalty = preference_penalty per occupied hour outside the
          user's preferred hours (only when preferred hours were provided).
        Fixed appliances never move, so they carry no penalty.
        """
        if not b.flexible:
            return 0.0
        p = self.shift_penalty * PRIORITY_WEIGHT.get(b.priority, 2.0) * abs(start - b.preferred_start)
        if self.preferred_hours:
            outside = sum(1 for h in self.slots(start, b.duration) if h not in self.preferred_hours)
            p += self.preference_penalty * outside
        return p

    def step_cost(self, b, start):
        return self.cost(b, start) + self.penalty(b, start)

    # ------------------------------------------------------------------- load
    def add_load(self, load, b, start, sign=1.0):
        new = list(load)
        for h in self.slots(start, b.duration):
            new[h] += sign * b.kwh_per_slot
        return new

    def base_load(self):
        load = [0.0] * 24
        for b in self.fixed_blocks:
            load = self.add_load(load, b, b.preferred_start)
        return load

    def fits(self, b, start, load):
        if self.capacity is None:
            return True
        return all(load[h] + b.kwh_per_slot <= self.capacity + EPS for h in self.slots(start, b.duration))

    # -------------------------------------------------------------- assignment
    def original_assignment(self):
        return {b.id: b.preferred_start for b in self.blocks}

    def search_order(self):
        """Most-constrained flexible appliances first (smallest domain, then largest power)."""
        return sorted(self.flexible_blocks, key=lambda b: (len(self.domain(b)), -b.power_kw, b.id))

    def min_step_cost(self, b):
        dom = self.domain(b)
        return min(self.step_cost(b, s) for s in dom) if dom else math.inf

    def evaluate(self, assignment):
        """Full evaluation of a (complete) assignment {block_id: start_hour}."""
        load = [0.0] * 24
        entries, violations = [], []
        cost = penalty = kwh = 0.0
        for b in self.blocks:
            s = assignment.get(b.id)
            if s is None:
                continue
            sl = self.slots(s, b.duration)
            for h in sl:
                load[h] += b.kwh_per_slot
            c, p = self.cost(b, s), self.penalty(b, s)
            cost += c
            penalty += p
            kwh += b.kwh_per_slot * b.duration * b.days
            entries.append({
                "appliance_id": b.id, "name": b.name, "flexible": b.flexible, "priority": b.priority,
                "start": s, "end": s + b.duration,
                "duration": b.duration, "slots": sl, "start_label": fmt_hour(s),
                "end_label": fmt_hour(s + b.duration), "daily_kwh": b.kwh_per_slot * b.duration,
                "monthly_kwh": b.kwh_per_slot * b.duration * b.days,
                "monthly_cost": c, "penalty": p,
            })
            if b.flexible:
                if s < b.window_start or s + b.duration > b.window_end:
                    violations.append({
                        "type": "window", "appliance": b.name,
                        "message": f"{b.name} runs {fmt_hour(s)}-{fmt_hour(s + b.duration)}, outside its "
                                   f"allowed window {fmt_hour(b.window_start)}-{fmt_hour(b.window_end)}.",
                    })
                bad = [h for h in sl if h in self.unavailable]
                if bad:
                    violations.append({
                        "type": "unavailable", "appliance": b.name,
                        "message": f"{b.name} uses unavailable hour(s) {', '.join(fmt_hour(h) for h in bad)}.",
                    })
        if self.capacity is not None:
            for h in range(24):
                if load[h] > self.capacity + EPS:
                    violations.append({
                        "type": "capacity", "hour": h,
                        "message": f"Load {load[h]:.2f} kW at {fmt_hour(h)} exceeds the {self.capacity:.2f} kW limit.",
                    })
        return {
            "entries": entries, "hourly_load_kwh": load, "monthly_kwh": kwh,
            "energy_cost": cost, "penalty": penalty, "objective": cost + penalty,
            "violations": violations, "feasible": not violations,
            "peak_load_kw": max(load) if load else 0.0,
        }

    # --------------------------------------------------------------- diagnosis
    def diagnose(self):
        """Human-readable reasons why no feasible schedule can exist (empty list = none found)."""
        reasons = []
        for b in self.flexible_blocks:
            if not self.domain(b):
                reasons.append(
                    f"{b.name} needs {b.duration} consecutive hour(s) inside "
                    f"{fmt_hour(b.window_start)}-{fmt_hour(b.window_end)}, but the window is too short or "
                    f"the unavailable hours {sorted(self.unavailable)} block every possible start time."
                )
        if self.capacity is not None:
            base = self.base_load()
            for h in range(24):
                if base[h] > self.capacity + EPS:
                    reasons.append(
                        f"Fixed (non-flexible) appliances alone draw {base[h]:.2f} kW at {fmt_hour(h)}, "
                        f"above the {self.capacity:.2f} kW capacity."
                    )
            for b in self.flexible_blocks:
                if self.domain(b) and not any(
                    self.fits(b, s, base) for s in self.domain(b)
                ):
                    reasons.append(
                        f"{b.name} ({b.kwh_per_slot:.2f} kW per hour) cannot fit in any allowed time slot "
                        f"because the fixed appliances plus the {self.capacity:.2f} kW capacity leave no room."
                    )
        return reasons

    # ---------------------------------------------------------------- results
    def package(self, algorithm, assignment, *, log=None, stats=None, explanation="", runtime_ms=0.0,
                extra=None):
        """Standard result dictionary shared by every scheduling algorithm."""
        original_eval = self.evaluate(self.original_assignment())
        result = {
            "algorithm": algorithm, "found": assignment is not None,
            "runtime_ms": round(runtime_ms, 3), "log": log or [], "stats": stats or {},
            "explanation": explanation, "original": original_eval,
            "problem": self.describe(),
        }
        if assignment is not None:
            ev = self.evaluate(assignment)
            moved = [
                {"appliance": e["name"], "from": fmt_hour(self.block(e["appliance_id"]).preferred_start),
                 "to": e["start_label"]}
                for e in ev["entries"]
                if e["flexible"] and e["start"] != self.block(e["appliance_id"]).preferred_start
            ]
            result.update({
                "assignment": {str(k): v for k, v in assignment.items()},
                "schedule": ev, "moved": moved, "objective": ev["objective"],
                "cost_saving": original_eval["energy_cost"] - ev["energy_cost"],
                "objective_improvement": original_eval["objective"] - ev["objective"],
            })
        else:
            result.update({"assignment": None, "schedule": None, "moved": [], "objective": None,
                           "diagnosis": self.diagnose()})
        if extra:
            result.update(extra)
        return result

    def describe(self):
        return {
            "flexible_appliances": [b.name for b in self.flexible_blocks],
            "fixed_appliances": [b.name for b in self.fixed_blocks],
            "unavailable_hours": sorted(self.unavailable),
            "preferred_hours": sorted(self.preferred_hours),
            "capacity_kw": self.capacity,
            "hourly_rates": [round(r, 4) for r in self.rates],
            "shift_penalty": self.shift_penalty,
            "domains": {b.name: self.domain(b) for b in self.flexible_blocks},
        }
