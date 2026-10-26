"""Appliance management: presets, demonstration data and CRUD orchestration."""
from database import db as dbm
from services import energy_calculator as ec
from services.validators import validate_appliance

# Presets shown in the "Add appliance" form.  Values are typical nameplate-style
# figures for convenience only - users should replace them with their own.
APPLIANCE_TEMPLATES = [
    {"template": "LED Bulb", "name": "LED Bulbs", "category": "Lighting", "power_w": 9, "quantity": 6,
     "hours_per_day": 5, "days_per_month": 30, "preferred_start": 18, "flexible": False,
     "min_hours": 3, "max_hours": 8, "priority": 2, "standby_w": 0, "window_start": 0, "window_end": 24},
    {"template": "Ceiling Fan", "name": "Ceiling Fan", "category": "Cooling", "power_w": 75, "quantity": 3,
     "hours_per_day": 10, "days_per_month": 30, "preferred_start": 12, "flexible": False,
     "min_hours": 5, "max_hours": 16, "priority": 2, "standby_w": 0, "window_start": 0, "window_end": 24},
    {"template": "Refrigerator", "name": "Refrigerator", "category": "Kitchen", "power_w": 150, "quantity": 1,
     "hours_per_day": 8, "days_per_month": 30, "preferred_start": 0, "flexible": False,
     "min_hours": 8, "max_hours": 24, "priority": 1, "standby_w": 0, "window_start": 0, "window_end": 24},
    {"template": "Television", "name": "Television", "category": "Entertainment", "power_w": 100, "quantity": 1,
     "hours_per_day": 4, "days_per_month": 30, "preferred_start": 19, "flexible": False,
     "min_hours": 1, "max_hours": 8, "priority": 3, "standby_w": 5, "window_start": 0, "window_end": 24},
    {"template": "Air Conditioner", "name": "Air Conditioner (1.5 ton)", "category": "Cooling", "power_w": 1500,
     "quantity": 1, "hours_per_day": 5, "days_per_month": 30, "preferred_start": 18, "flexible": False,
     "min_hours": 3, "max_hours": 10, "priority": 2, "standby_w": 3, "window_start": 0, "window_end": 24},
    {"template": "Washing Machine", "name": "Washing Machine", "category": "Laundry", "power_w": 500, "quantity": 1,
     "hours_per_day": 1.5, "days_per_month": 12, "preferred_start": 19, "flexible": True,
     "min_hours": 1, "max_hours": 3, "priority": 3, "standby_w": 2, "window_start": 6, "window_end": 23},
    {"template": "Computer", "name": "Desktop Computer", "category": "Computing", "power_w": 150, "quantity": 1,
     "hours_per_day": 6, "days_per_month": 30, "preferred_start": 10, "flexible": False,
     "min_hours": 3, "max_hours": 12, "priority": 2, "standby_w": 3, "window_start": 0, "window_end": 24},
    {"template": "Water Heater", "name": "Water Heater (Geyser)", "category": "Heating", "power_w": 2000,
     "quantity": 1, "hours_per_day": 1, "days_per_month": 30, "preferred_start": 19, "flexible": True,
     "min_hours": 0.5, "max_hours": 2, "priority": 2, "standby_w": 0, "window_start": 5, "window_end": 23},
]

# Demonstration data - always stored with is_demo = 1 so it can be identified and reset.
SAMPLE_APPLIANCES = [
    dict(t, is_demo=True) for t in [
        APPLIANCE_TEMPLATES[0], APPLIANCE_TEMPLATES[1], APPLIANCE_TEMPLATES[2], APPLIANCE_TEMPLATES[3],
        APPLIANCE_TEMPLATES[4], APPLIANCE_TEMPLATES[5], APPLIANCE_TEMPLATES[6], APPLIANCE_TEMPLATES[7],
    ]
]
for _a in SAMPLE_APPLIANCES:
    _a.pop("template", None)


def with_metrics(appliances, tariff):
    out = []
    for a in appliances:
        m = ec.appliance_metrics(a, tariff["base_rate"])
        out.append({**a, **m})
    return out


def load_sample_data(conn):
    """Insert demonstration appliances.  Returns number inserted (0 if already loaded)."""
    if dbm.count_demo_appliances(conn) > 0:
        return 0
    for item in SAMPLE_APPLIANCES:
        clean, errors = validate_appliance(item)
        if errors:  # a bug in the sample data should fail loudly in tests
            raise ValueError(f"Invalid sample appliance {item.get('name')}: {errors}")
        dbm.insert_appliance(conn, clean)
    return len(SAMPLE_APPLIANCES)
