from __future__ import annotations

from typing import Any

# The application runs exactly one policy (see README): confirmed cash-movement
# events are deducted from cash sales to get the expected cash on hand.
DEDUCT = "deduct"

# Kept for callers that need the audit-only reading explicitly: events are
# recorded but must *not* move the cash expectation.  The app itself never
# selects this policy.
AUDIT = "audit"


def expected_cash(cash_total: float, pickup_total: float, policy: str = DEDUCT) -> float:
    """The single expected-cash formula used by preview, seal and snapshots.

    deduct: expected = cash sales - confirmed pickup events
    audit:  expected = cash sales (pickup events are audit-only)
    """
    cash = round(float(cash_total), 2)
    if policy == AUDIT:
        return cash
    if policy == DEDUCT:
        return round(cash - float(pickup_total or 0), 2)
    raise ValueError(f"unknown pickup policy: {policy!r}")


def batch_pickup_snapshot(conn, business_day: str, pickup_repo) -> dict[str, Any]:
    """Snapshot the exact same confirmed events the preview aggregates.

    The batch header must never compute its own count/total from a different
    query; whatever populates `cash_pickups` for the day is what gets pinned.
    """
    if hasattr(pickup_repo, "day_pickup_total"):
        total, count = pickup_repo.day_pickup_total(conn, business_day)
        pickup_total = round(float(total), 2)
        pickup_count = int(count)
    else:  # pragma: no cover - compatibility with alternate repositories
        rows = pickup_repo.list_for_day(conn, business_day)
        confirmed = [
            r for r in rows if str(r.get("status") or "confirmed") == "confirmed"
        ]
        pickup_total = round(sum(float(r.get("amount") or 0) for r in confirmed), 2)
        pickup_count = len(confirmed)
    return {
        "pickup_count": pickup_count,
        "pickup_total": pickup_total,
        "actual_total": pickup_total,
    }


def allow_pickup_on_sealed(conn, close_repo, business_day: str) -> bool:
    """Missed pickups may not be back-filled into a sealed business day."""
    return not close_repo.is_sealed(conn, business_day)
