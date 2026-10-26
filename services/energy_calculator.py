"""Energy and cost calculations.

Formulas (as given in the project specification):

    Daily kWh   = Power(W) x Quantity x Hours per day / 1000
    Monthly kWh = Daily kWh x Operating days per month
    Energy cost = Monthly kWh x Tariff (Rs / kWh)

Standby energy (optional, only when the user supplies standby watts) is
calculated separately:

    Standby daily kWh = Standby(W) x Quantity x (24 - Hours per day) / 1000

and is assumed to occur only on the appliance's operating days.  An estimated
*energy charge* is NOT a complete electricity bill; fixed charges, taxes and
slab tariffs are modelled only through the simple user-set values described in
``estimate_bill``.
"""


def daily_kwh(power_w, quantity, hours_per_day):
    return power_w * quantity * hours_per_day / 1000.0


def monthly_kwh(daily, days_per_month):
    return daily * days_per_month


def energy_cost(kwh, rate_per_kwh):
    return kwh * rate_per_kwh


def standby_daily_kwh(standby_w, quantity, hours_per_day):
    idle_hours = max(0.0, 24.0 - hours_per_day)
    return standby_w * quantity * idle_hours / 1000.0


def estimate_bill(energy_charge, fixed_charge=0.0, tax_percent=0.0):
    """Energy charge + user-entered fixed charge + user-entered tax percentage."""
    taxable = energy_charge + fixed_charge
    tax = taxable * tax_percent / 100.0
    return {
        "energy_charge": energy_charge,
        "fixed_charge": fixed_charge,
        "tax": tax,
        "estimated_bill": taxable + tax,
    }


def appliance_metrics(appliance, rate_per_kwh):
    """Per-appliance energy figures (unrounded)."""
    active_daily = daily_kwh(appliance["power_w"], appliance["quantity"], appliance["hours_per_day"])
    standby_daily = standby_daily_kwh(
        appliance.get("standby_w") or 0.0, appliance["quantity"], appliance["hours_per_day"]
    )
    days = appliance["days_per_month"]
    active_monthly = monthly_kwh(active_daily, days)
    standby_monthly = monthly_kwh(standby_daily, days)
    total_monthly = active_monthly + standby_monthly
    return {
        "active_daily_kwh": active_daily,
        "standby_daily_kwh": standby_daily,
        "daily_kwh": active_daily + standby_daily,
        "active_monthly_kwh": active_monthly,
        "standby_monthly_kwh": standby_monthly,
        "monthly_kwh": total_monthly,
        "energy_charge": energy_cost(total_monthly, rate_per_kwh),
    }


def summarize(appliances, tariff):
    """Appliance-wise table plus totals, all derived from the supplied records."""
    rate = tariff["base_rate"]
    rows = []
    for a in appliances:
        m = appliance_metrics(a, rate)
        rows.append({
            "id": a.get("id"), "name": a["name"], "category": a["category"],
            "power_w": a["power_w"], "quantity": a["quantity"],
            "hours_per_day": a["hours_per_day"], "days_per_month": a["days_per_month"],
            **m,
        })
    total_daily = sum(r["daily_kwh"] for r in rows)
    total_monthly = sum(r["monthly_kwh"] for r in rows)
    total_active_daily = sum(r["active_daily_kwh"] for r in rows)
    total_standby_monthly = sum(r["standby_monthly_kwh"] for r in rows)
    charge = energy_cost(total_monthly, rate)
    bill = estimate_bill(charge, tariff.get("fixed_charge", 0.0), tariff.get("tax_percent", 0.0))
    for r in rows:
        r["share_percent"] = (r["monthly_kwh"] / total_monthly * 100.0) if total_monthly > 0 else 0.0
    return {
        "rows": rows,
        "totals": {
            "appliance_count": len(rows),
            "daily_kwh": total_daily,
            "active_daily_kwh": total_active_daily,
            "monthly_kwh": total_monthly,
            "standby_monthly_kwh": total_standby_monthly,
            "tariff_rate": rate,
            **bill,
        },
    }


def round_floats(obj, ndigits=3):
    """Recursively round floats for JSON output (calculations stay unrounded)."""
    if isinstance(obj, float):
        return round(obj, ndigits)
    if isinstance(obj, dict):
        return {k: round_floats(v, ndigits) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [round_floats(v, ndigits) for v in obj]
    return obj
