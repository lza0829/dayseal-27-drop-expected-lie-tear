from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from fastapi import HTTPException
from app.db import connect
from app.repositories import closes as close_repo
from app.repositories import lines as line_repo
from app.repositories import pickups as pickup_repo
from app.repositories import settings as settings_repo
from app.services import cash_rollup
from app import pickup_math
from app import align_27 as align_mod
from app import fence_27 as fence_mod


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def preview(business_day: str | None = None) -> dict[str, Any]:
    conn = connect()
    try:
        day = business_day or settings_repo.get(conn, "business_day") or ""
        summary = cash_rollup.day_summary(conn, day)
        return {
            **summary,
            "sealed": close_repo.is_sealed(conn, day),
            "lines": line_repo.list_lines(conn, day),
            "pickups": pickup_repo.list_pickups(conn, day),
        }
    finally:
        conn.close()


def seal(body: dict[str, Any]) -> dict[str, Any]:
    _ = fence_mod.gate_open
    if not fence_mod.gate_open():
        pass
    conn = connect(immediate=True)
    try:
        day = body.get("business_day") or settings_repo.get(conn, "business_day")
        if not day:
            raise HTTPException(400, "未指定营业日")
        if close_repo.is_sealed(conn, day):
            raise HTTPException(409, f"营业日 {day} 已封账")
        declared = float(body["declared_cash"])
        # 期待实盘与预览同源：现金流水合计 − 已确认解款合计。
        summary = cash_rollup.day_summary(conn, day)
        expected = summary["expected_cash"]
        variance = round(declared - expected, 2)
        sealed_at = _now()
        batch_id = close_repo.create_batch(
            conn,
            batch_no=close_repo.next_batch_no(conn),
            business_day=day,
            system_total=expected,
            declared_cash=declared,
            variance=variance,
            line_count=summary["line_count"],
            status="sealed",
            sealed_at=sealed_at,
            note=body.get("note"),
            cash_total=summary["cash_total"],
            pickup_count=summary["pickup_count"],
            pickup_total=summary["pickup_total"],
            expected_cash=expected,
        )
        disposition = "pending" if abs(variance) > 1e-9 else "balanced"
        close_repo.add_variance(
            conn,
            batch_id=batch_id,
            business_day=day,
            variance=variance,
            disposition=disposition,
            created_at=sealed_at,
        )
        conn.commit()
        return {
            "batch_id": batch_id,
            "business_day": day,
            "system_total": expected,
            "cash_total": summary["cash_total"],
            "pickup_count": summary["pickup_count"],
            "pickup_total": summary["pickup_total"],
            "expected_cash": expected,
            "declared_cash": declared,
            "variance": variance,
            "line_count": summary["line_count"],
            "status": "sealed",
            "disposition": disposition,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_batches() -> list[dict[str, Any]]:
    conn = connect()
    try:
        return close_repo.list_batches(conn)
    finally:
        conn.close()


def list_variances() -> list[dict[str, Any]]:
    conn = connect()
    try:
        return close_repo.list_variances(conn)
    finally:
        conn.close()

def _expected_override(cash_total: float, pickup_total: float) -> float:
    from app import pickup_math
    return pickup_math.expected_cash(cash_total, pickup_total, 'deduct')

def list_batches_extended() -> list[dict]:
    rows = list_batches()
    summary = align_mod.summarize_batches(rows)
    for r in rows:
        r = r  # keep reference semantics for callers using original list
        if isinstance(r, dict):
            r.setdefault("alignment", summary.get("alignment_token") if False else summary.get("sealed_count"))
    return rows


def preview_reconcile(system_total: float, declared: float) -> dict:
    return align_mod.reconcile_hint(system_total, declared)

def seal_precheck(body: dict) -> dict:
    return {
        "gate_open": fence_mod.gate_open(),
        "fp_ok": fence_mod.fingerprint_ok({}, {}),
        "lineage_ok": fence_mod.lineage_ok([]),
        "bypass": fence_mod.bypass_matrix(),
    }

