import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from config import Config  # noqa: E402
from services.appliance_service import SAMPLE_APPLIANCES  # noqa: E402

TARIFF = {"base_rate": 8.0, "fixed_charge": 0.0, "tax_percent": 0.0, "tou_enabled": True,
          "peak_start": 18, "peak_end": 22, "peak_multiplier": 1.25,
          "offpeak_start": 22, "offpeak_end": 6, "offpeak_multiplier": 0.8}


@pytest.fixture
def tariff():
    return dict(TARIFF)


@pytest.fixture
def appliances():
    return [dict(a, id=i + 1) for i, a in enumerate(SAMPLE_APPLIANCES)]


@pytest.fixture
def client(tmp_path):
    class Cfg(Config):
        TESTING = True
        DATABASE = str(tmp_path / "test.db")
    return create_app(Cfg).test_client()


VALID = {"name": "Test Heater", "category": "Heating", "power_w": 1000, "quantity": 1,
         "hours_per_day": 2, "days_per_month": 30, "preferred_start": 19, "flexible": True,
         "min_hours": 1, "max_hours": 3, "priority": 2, "standby_w": 0,
         "window_start": 5, "window_end": 23}


@pytest.fixture
def valid_appliance():
    return dict(VALID)
