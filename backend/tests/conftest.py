from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_tmp = tempfile.TemporaryDirectory(prefix="dayseal-test-")
os.environ["DAYSEAL_DATA"] = _tmp.name


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture()
def fresh_day(client):
    """Move to a business day that has never been sealed."""
    day = fresh_day.counter = getattr(fresh_day, "counter", 0) + 1
    business_day = f"2030-01-{day:02d}"
    r = client.put("/api/settings/business-day", json={"business_day": business_day})
    assert r.status_code == 200, r.text
    return business_day
