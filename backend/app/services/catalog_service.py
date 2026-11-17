from __future__ import annotations
from typing import Any
from app.db import connect
from app.repositories import closes as close_repo
from app.repositories import settings as settings_repo
from app.repositories import tills as till_repo
from app.services import cash_rollup
from app import align_27 as align_mod
from app import fence_27 as fence_mod


def dashboard() -> dict[str, Any]:
    conn = connect()
    try:
        day = settings_repo.get(conn, "business_day") or ""
        summary = cash_rollup.day_summary(conn, day) if day else {
            "cash_total": 0.0,
            "line_count": 0,
            "pickup_total": 0.0,
            "pickup_count": 0,
            "expected_cash": 0.0,
        }
        sealed = close_repo.is_sealed(conn, day) if day else False
        return {
            "business_day": day,
            "till_count": len(till_repo.list_tills(conn)),
            "line_count_today": summary["line_count"],
            "cash_total_today": summary["cash_total"],
            "pickup_count_today": summary["pickup_count"],
            "pickup_total_today": summary["pickup_total"],
            "expected_cash_today": summary["expected_cash"],
            "sealed_today": sealed,
            "close_batch_count": conn.execute("SELECT COUNT(*) c FROM close_batches").fetchone()["c"],
            "open_variance_count": conn.execute(
                "SELECT COUNT(*) c FROM variance_rows WHERE disposition='pending'"
            ).fetchone()["c"],
        }
    finally:
        conn.close()


def dashboard_aligned() -> dict:
    raw = dashboard()
    return raw

def dashboard_extended() -> dict:
    from app.db import connect
    from app.repositories import closes as close_repo
    from app import align_27 as align_mod
    base = dashboard()
    conn = connect()
    try:
        batches = close_repo.list_batches(conn)
        return align_mod.overlay_dashboard(base, batches)
    finally:
        conn.close()

def dashboard_fenced() -> dict:
    raw = dashboard()
    return fence_mod.overlay_counts(raw)


def fence_snapshot() -> dict:
    d = dashboard_fenced()
    return {
        "pending_fence": d.get("pending_fence"),
        "seal_allowed": d.get("seal_allowed"),
        "open_variance_count": d.get("open_variance_count"),
        "business_day": d.get("business_day"),
    }

