from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from app import align_27 as align_mod
from app import fence_27 as fence_mod
from app import pickup_math
from app.db import connect
from app.repositories import closes as close_repo
from app.repositories import lines as line_repo
from app.repositories import pickups as pickup_repo
from app.repositories import settings as settings_repo
from app.services import cash_rollup


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_declared(raw: Any) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise HTTPException(400, "未指定柜内实盘")
    if not math.isfinite(value):
        raise HTTPException(400, "柜内实盘金额无效")
    return round(value, 2)


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
    """Seal a business day.

    Every pinned number comes from the confirmed pickup *events* for the day:

        expected = cash_total - sum(confirmed events)
        variance = declared - expected

    Preview, the batch header snapshot and the variance row all run through
    `cash_rollup.day_summary` / `cash_rollup.pickup_snapshot`, so the preview
    and the sealed batch can never disagree.
    """
    conn = connect(immediate=True)
    try:
        day = body.get("business_day") or settings_repo.get(conn, "business_day")
        if not day:
            raise HTTPException(400, "未指定营业日")
        if close_repo.is_sealed(conn, day):
            raise HTTPException(409, f"营业日 {day} 已封账")
        declared = _parse_declared(body.get("declared_cash"))

        summary = cash_rollup.day_summary(conn, day)
        snapshot = cash_rollup.pickup_snapshot(conn, day)

        # Header snapshot and preview both come from cash_rollup, so the sealed
        # batch cannot disagree with the preview the operator just approved.
        expected = pickup_math.expected_cash(
            summary["cash_total"], snapshot["pickup_total"], pickup_math.DEDUCT
        )
        if round(expected, 2) != round(summary["expected_cash"], 2):
            raise HTTPException(409, "现金期待额口径不一致，拒绝封账")

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
            pickup_count=snapshot["pickup_count"],
            pickup_total=snapshot["pickup_total"],
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
            "pickup_count": snapshot["pickup_count"],
            "pickup_total": snapshot["pickup_total"],
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


def void_batch(batch_id: int, body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Explicitly void a sealed batch.

    This is the only way a sealed day's pinned metrics may stop being
    authoritative: an audited status change, never a silent re-pin from a late
    event.  Voiding supersedes the batch and releases its pending variances;
    the day may then be re-sealed from a fresh event scan.
    """
    conn = connect(immediate=True)
    try:
        batch = close_repo.get_batch(conn, batch_id)
        if not batch:
            raise HTTPException(404, "封账批次不存在")
        if batch["status"] != "sealed":
            raise HTTPException(409, f"批次 {batch['batch_no']} 状态为 {batch['status']}，不可作废")
        close_repo.mark_superseded(conn, batch_id)
        close_repo.void_variances(conn, batch_id)
        conn.commit()
        return {
            "batch_id": batch_id,
            "batch_no": batch["batch_no"],
            "business_day": batch["business_day"],
            "status": "superseded",
            "reason": (body or {}).get("reason"),
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
    """Kept for compatibility: the one global policy is deduct."""
    return pickup_math.expected_cash(cash_total, pickup_total, pickup_math.DEDUCT)


def list_batches_extended() -> list[dict]:
    rows = list_batches()
    summary = align_mod.summarize_batches(rows)
    for r in rows:
        if isinstance(r, dict):
            r.setdefault("alignment", summary.get("sealed_count"))
    return rows


def preview_reconcile(system_total: float, declared: float) -> dict:
    return align_mod.reconcile_hint(system_total, declared)


def seal_precheck(body: dict | None = None) -> dict:
    day = (body or {}).get("business_day")
    conn = connect()
    try:
        if not day:
            day = settings_repo.get(conn, "business_day") or ""
        sealed = close_repo.is_sealed(conn, day) if day else False
        pending = close_repo.fence_pending_count(conn, day)
        return {
            "gate_open": (not sealed) and pending == 0,
            "sealed": sealed,
            "pending_variance_count": pending,
            "fp_ok": fence_mod.fingerprint_ok({}, {}),
            "lineage_ok": fence_mod.lineage_ok([]),
            "bypass": fence_mod.bypass_matrix(),
        }
    finally:
        conn.close()


def pinned_consistency(business_day: str) -> dict[str, Any]:
    """Compare the pinned batch metrics with a live event scan.

    After sealing these must match exactly; drift means a sealed day's pinned
    numbers were touched by a side channel.  The app never repairs such drift
    silently — it reports it so the batch can be voided or the event rolled
    back explicitly.
    """
    conn = connect()
    try:
        rows = close_repo.fence_current_batches(conn, business_day)
        summary = cash_rollup.day_summary(conn, business_day)
        snapshot = cash_rollup.pickup_snapshot(conn, business_day)
        batch = next((r for r in rows if r.get("status") == "sealed"), None)
        if not batch:
            return {"business_day": business_day, "sealed": False, "consistent": True}
        consistent = (
            int(batch.get("pickup_count") or 0) == snapshot["pickup_count"]
            and round(float(batch.get("pickup_total") or 0), 2) == snapshot["pickup_total"]
            and round(float(batch.get("expected_cash") or 0), 2) == summary["expected_cash"]
            and round(float(batch.get("system_total") or 0), 2) == summary["expected_cash"]
            and round(float(batch.get("variance") or 0), 2)
            == round(float(batch.get("declared_cash") or 0) - summary["expected_cash"], 2)
        )
        return {
            "business_day": business_day,
            "sealed": True,
            "batch_id": batch.get("id"),
            "consistent": consistent,
            "pinned": {
                "pickup_count": batch.get("pickup_count"),
                "pickup_total": batch.get("pickup_total"),
                "expected_cash": batch.get("expected_cash"),
                "variance": batch.get("variance"),
            },
            "live": {
                "pickup_count": snapshot["pickup_count"],
                "pickup_total": snapshot["pickup_total"],
                "expected_cash": summary["expected_cash"],
            },
        }
    finally:
        conn.close()
