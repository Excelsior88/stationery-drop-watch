"""Frozen first-run data for tests (see tests/fixtures/make_baselines.py)."""
import json
from pathlib import Path

DIR = Path(__file__).resolve().parent / "fixtures" / "baselines"


def load(name):
    return json.loads((DIR / f"{name}.json").read_text())
