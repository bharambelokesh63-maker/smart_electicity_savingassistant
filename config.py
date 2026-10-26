"""Application configuration."""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    DATABASE = os.environ.get("SEA_DATABASE", os.path.join(BASE_DIR, "database", "electricity.db"))
    JSON_SORT_KEYS = False
    TESTING = False
    DEBUG = False


class TestConfig(Config):
    TESTING = True
    DATABASE = ":memory:"  # overridden per-test with a temp file path
