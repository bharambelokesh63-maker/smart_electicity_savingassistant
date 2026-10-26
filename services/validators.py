"""Input validation for appliances, tariff and scheduling configuration.

Every validator returns ``(clean_dict, errors_dict)``; ``errors_dict`` maps a
field name to a human-readable message.  The frontend performs the same checks,
but the backend never trusts it.
"""
import math

CATEGORIES = ["Lighting", "Cooling", "Heating", "Kitchen", "Entertainment",
              "Laundry", "Computing", "Other"]


def _cap(text):
    return text[:1].upper() + text[1:]


def _num(data, key, errors, *, minimum=None, maximum=None, required=True, default=None,
         integer=False, exclusive_min=False, label=None):
    label = label or key.replace("_", " ")
    raw = data.get(key, None)
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        if required:
            errors[key] = f"{_cap(label)} is required."
            return None
        return default
    if isinstance(raw, bool):
        errors[key] = f"{_cap(label)} must be a number."
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        errors[key] = f"{_cap(label)} must be a number."
        return None
    if math.isnan(value) or math.isinf(value):
        errors[key] = f"{_cap(label)} must be a finite number."
        return None
    if integer:
        if value != int(value):
            errors[key] = f"{_cap(label)} must be a whole number."
            return None
        value = int(value)
    if minimum is not None and (value < minimum or (exclusive_min and value == minimum)):
        op = ">" if exclusive_min else ">="
        errors[key] = f"{_cap(label)} must be {op} {minimum}."
        return None
    if maximum is not None and value > maximum:
        errors[key] = f"{_cap(label)} must be <= {maximum}."
        return None
    return value


def _bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return False


def validate_appliance(data):
    errors = {}
    if not isinstance(data, dict):
        return None, {"_": "Request body must be a JSON object."}

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        errors["name"] = "Name is required."
        name = ""
    elif len(name.strip()) > 60:
        errors["name"] = "Name must be at most 60 characters."
    name = name.strip()

    category = data.get("category") or "Other"
    if category not in CATEGORIES:
        errors["category"] = f"Category must be one of: {', '.join(CATEGORIES)}."

    power_w = _num(data, "power_w", errors, minimum=0, maximum=20000, exclusive_min=True, label="rated power (W)")
    quantity = _num(data, "quantity", errors, minimum=1, maximum=100, integer=True)
    hours = _num(data, "hours_per_day", errors, minimum=0, maximum=24, exclusive_min=True, label="hours per day")
    days = _num(data, "days_per_month", errors, minimum=1, maximum=31, integer=True, label="operating days per month")
    pref = _num(data, "preferred_start", errors, minimum=0, maximum=23, integer=True,
                required=False, default=18, label="preferred start hour")
    min_hours = _num(data, "min_hours", errors, minimum=0, maximum=24, required=False, default=0.0,
                     label="minimum daily hours")
    max_hours = _num(data, "max_hours", errors, minimum=0, maximum=24, required=False, default=None,
                     label="maximum daily hours")
    priority = _num(data, "priority", errors, minimum=1, maximum=3, integer=True, required=False,
                    default=2, label="priority")
    standby = _num(data, "standby_w", errors, minimum=0, maximum=1000, required=False, default=0.0,
                   label="standby power (W)")
    w_start = _num(data, "window_start", errors, minimum=0, maximum=23, integer=True, required=False,
                   default=0, label="window start hour")
    w_end = _num(data, "window_end", errors, minimum=1, maximum=24, integer=True, required=False,
                 default=24, label="window end hour")
    flexible = _bool(data.get("flexible", False))

    if hours is not None:
        if min_hours is not None and min_hours > hours and "min_hours" not in errors:
            errors["min_hours"] = "Minimum daily hours cannot exceed average hours per day."
        if max_hours is not None and max_hours < hours and "max_hours" not in errors:
            errors["max_hours"] = "Maximum daily hours cannot be less than average hours per day."
    if w_start is not None and w_end is not None:
        if w_end <= w_start:
            errors["window_end"] = "Window end must be later than window start."
        elif flexible and hours is not None and "hours_per_day" not in errors:
            need = math.ceil(hours)
            if w_end - w_start < need:
                errors["window_end"] = (
                    f"Operating window ({w_end - w_start} h) is shorter than the {need} h "
                    "block this appliance needs."
                )

    if errors:
        return None, errors
    clean = {
        "name": name, "category": category, "power_w": float(power_w), "quantity": quantity,
        "hours_per_day": float(hours), "days_per_month": days, "preferred_start": pref,
        "flexible": flexible, "min_hours": float(min_hours), "max_hours": max_hours,
        "priority": priority, "standby_w": float(standby), "window_start": w_start,
        "window_end": w_end, "is_demo": _bool(data.get("is_demo", False)),
    }
    return clean, {}


def validate_tariff(data):
    errors = {}
    if not isinstance(data, dict):
        return None, {"_": "Request body must be a JSON object."}
    base = _num(data, "base_rate", errors, minimum=0, maximum=100, exclusive_min=True, label="tariff rate (Rs/kWh)")
    fixed = _num(data, "fixed_charge", errors, minimum=0, maximum=100000, required=False, default=0.0,
                 label="fixed charge")
    tax = _num(data, "tax_percent", errors, minimum=0, maximum=100, required=False, default=0.0,
               label="tax percent")
    pk_s = _num(data, "peak_start", errors, minimum=0, maximum=23, integer=True, required=False, default=18,
                label="peak start")
    pk_e = _num(data, "peak_end", errors, minimum=0, maximum=24, integer=True, required=False, default=22,
                label="peak end")
    pk_m = _num(data, "peak_multiplier", errors, minimum=0.1, maximum=5, required=False, default=1.25,
                label="peak multiplier")
    op_s = _num(data, "offpeak_start", errors, minimum=0, maximum=23, integer=True, required=False, default=22,
                label="off-peak start")
    op_e = _num(data, "offpeak_end", errors, minimum=0, maximum=24, integer=True, required=False, default=6,
                label="off-peak end")
    op_m = _num(data, "offpeak_multiplier", errors, minimum=0.1, maximum=5, required=False, default=0.8,
                label="off-peak multiplier")
    if errors:
        return None, errors
    return {
        "base_rate": float(base), "fixed_charge": float(fixed), "tax_percent": float(tax),
        "tou_enabled": _bool(data.get("tou_enabled", True)),
        "peak_start": pk_s, "peak_end": pk_e, "peak_multiplier": float(pk_m),
        "offpeak_start": op_s, "offpeak_end": op_e, "offpeak_multiplier": float(op_m),
    }, {}


def validate_schedule_config(data):
    """Scheduler / algorithm configuration (all keys optional)."""
    data = data or {}
    errors = {}
    if not isinstance(data, dict):
        return None, {"_": "Configuration must be a JSON object."}

    def hour_list(key, label):
        raw = data.get(key) or []
        if not isinstance(raw, list):
            errors[key] = f"{label} must be a list of hours (0-23)."
            return []
        out = []
        for h in raw:
            try:
                hv = int(h)
            except (TypeError, ValueError):
                errors[key] = f"{label} must contain whole hours between 0 and 23."
                return []
            if hv != float(h) or not 0 <= hv <= 23:
                errors[key] = f"{label} must contain whole hours between 0 and 23."
                return []
            out.append(hv)
        return sorted(set(out))

    unavailable = hour_list("unavailable_hours", "Unavailable hours")
    preferred = hour_list("preferred_hours", "Preferred hours")
    cap_raw = data.get("capacity_kw")
    capacity = None
    if cap_raw not in (None, ""):
        try:
            capacity = float(cap_raw)
        except (TypeError, ValueError):
            errors["capacity_kw"] = "Capacity must be a number."
        else:
            if not capacity > 0 or capacity > 1000:
                errors["capacity_kw"] = "Capacity must be greater than 0 and at most 1000 kW."
    shift = _num(data, "shift_penalty", errors, minimum=0, maximum=1000, required=False, default=3.0,
                 label="shift penalty")
    pref_pen = _num(data, "preference_penalty", errors, minimum=0, maximum=1000, required=False, default=2.0,
                    label="preference penalty")
    max_iter = _num(data, "max_iterations", errors, minimum=1, maximum=10000, integer=True, required=False,
                    default=100, label="max iterations")
    max_exp = _num(data, "max_expansions", errors, minimum=1, maximum=200000, integer=True, required=False,
                   default=20000, label="max expansions")
    value_order = data.get("value_order", "cost")
    if value_order not in ("cost", "preferred"):
        errors["value_order"] = "Value order must be 'cost' or 'preferred'."
    if errors:
        return None, errors
    return {
        "unavailable_hours": unavailable, "preferred_hours": preferred, "capacity_kw": capacity,
        "shift_penalty": float(shift), "preference_penalty": float(pref_pen),
        "max_iterations": max_iter, "max_expansions": max_exp, "value_order": value_order,
    }, {}
