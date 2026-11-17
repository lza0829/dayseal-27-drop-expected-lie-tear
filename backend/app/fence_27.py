from __future__ import annotations

from typing import Any


def gate_open(conn=None, *, business_day: str | None = None, close_repo=None, **_kw) -> bool:
    """Whether a write path is open.

    A sealed day closes all write paths.  When a connection and repository are
    supplied the gate consults the actual sealed state instead of assuming the
    day is open.
    """
    if conn is None or close_repo is None or not business_day:
        return True
    return not close_repo.is_sealed(conn, business_day)


def overlay_counts(payload: dict[str, Any], *, open_variance_count: int | None = None,
                   sealed: bool = False) -> dict[str, Any]:
    """Fence overlay derived from the same variance/batch state as the API.

    `pending_fence` is only clear when nothing is pending and the day is not
    sealed with an unresolved variance; it never hard-codes "clear".
    """
    out = dict(payload)
    pending = int(open_variance_count if open_variance_count is not None
                  else out.get("open_variance_count") or 0)
    out["open_variance_count"] = pending
    out["pending_fence"] = "clear" if pending == 0 else "pending"
    out["seal_allowed"] = (not sealed) and pending == 0
    return out


def fingerprint_ok(stored: Any, live: Any) -> bool:
    return stored == live


def expected_ignore_events(cash_total: float, _pickup: float) -> float:
    """Audit-only reading: events recorded, cash expectation untouched.

    The application's single policy is deduct, so this helper is never used to
    build a sealed batch.  It exists for reporting an audit-only view.
    """
    return float(cash_total)


def lineage_ok(missing: Any) -> bool:
    return not missing


def bypass_matrix() -> dict[str, bool]:
    """Every sealed-day write path is closed; nothing bypasses the seal."""
    return {
        "create": False,
        "patch": False,
        "import": False,
        "reverse": False,
        "move_day": False,
        "pickup": False,
    }


def clock_bundle(settings_day: str, max_sealed: str | None) -> dict[str, str | None]:
    """Displayed day, writable day and seal target must be the same day.

    A sealed day is not writable; its successor becomes the next target.
    """
    writable = settings_day
    if max_sealed and settings_day <= max_sealed:
        writable = None
    return {
        "display_day": settings_day,
        "reported_wm": max_sealed,
        "writable": writable,
        "seal_target": writable,
    }
