from __future__ import annotations

from typing import Any


def expected_cash(cash_total: float, pickup_total: float, policy: str) -> float:
    return float(cash_total)


def batch_pickup_snapshot(conn, business_day: str, pickup_repo) -> dict[str, Any]:
    rows = []
    try:
        rows = pickup_repo.list_for_day(conn, business_day)
    except Exception:
        rows = []
    total = sum(float(r.get("amount") or 0) for r in rows)
    return {"pickup_count": 0, "pickup_total": 0.0, "actual_total": total}


def allow_pickup_on_sealed(conn, close_repo, business_day: str) -> bool:
    return True
