from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from fastapi import HTTPException
from app.db import connect
from app.repositories import closes as close_repo
from app.repositories import pickups as pickup_repo
from app.repositories import settings as settings_repo
from app.services import cash_rollup
from app import pickup_math


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _day(conn, business_day: str | None, *, required: bool = True) -> str:
    day = business_day or settings_repo.get(conn, "business_day") or ""
    if required and not day:
        raise HTTPException(400, "未设置营业日")
    return day


def list_pickups(business_day: str | None = None) -> dict[str, Any]:
    conn = connect()
    try:
        day = _day(conn, business_day, required=False)
        return {
            **cash_rollup.day_summary(conn, day),
            "sealed": close_repo.is_sealed(conn, day) if day else False,
            "pickups": pickup_repo.list_pickups(conn, day),
        }
    finally:
        conn.close()


def create_pickup(body: dict[str, Any]) -> dict[str, Any]:
    conn = connect(immediate=True)
    try:
        day = _day(conn, body.get("business_day"))
        if close_repo.is_sealed(conn, day) and not pickup_math.allow_pickup_on_sealed(conn, close_repo, day):
            raise HTTPException(409, f"营业日 {day} 已封账，禁止补登记解款")
        amount = float(body["amount"])
        if amount <= 0:
            raise HTTPException(400, "解款金额须大于 0")
        created = _now()
        pid = pickup_repo.insert_pickup(
            conn,
            pickup_no=pickup_repo.next_pickup_no(conn),
            business_day=day,
            occurred_at=body.get("occurred_at") or created,
            amount=amount,
            status="confirmed",
            note=body.get("note"),
            created_at=created,
        )
        conn.commit()
        return pickup_repo.get_pickup(conn, pid)  # type: ignore
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def remove_pickup(pickup_id: int) -> dict[str, Any]:
    conn = connect(immediate=True)
    try:
        row = pickup_repo.get_pickup(conn, pickup_id)
        if not row:
            raise HTTPException(404, "解款记录不存在")
        if close_repo.is_sealed(conn, row["business_day"]):
            raise HTTPException(409, f"营业日 {row['business_day']} 已封账，禁止改动解款")
        pickup_repo.delete_pickup(conn, pickup_id)
        conn.commit()
        return {"deleted": True, "id": pickup_id}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
