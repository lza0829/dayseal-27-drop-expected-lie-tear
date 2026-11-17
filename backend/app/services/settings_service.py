from __future__ import annotations
from typing import Any
from fastapi import HTTPException
from app.db import connect
from app.repositories import closes as close_repo
from app.repositories import settings as settings_repo


def get_day() -> dict[str, Any]:
    conn = connect()
    try:
        return {"business_day": settings_repo.get(conn, "business_day")}
    finally:
        conn.close()


def set_day(body: dict[str, Any]) -> dict[str, Any]:
    day = (body.get("business_day") or "").strip()
    if not day:
        raise HTTPException(400, "营业日不能为空")
    conn = connect(immediate=True)
    try:
        # The writable day may not be a sealed day: that would point every
        # write path and the seal target at a day whose metrics are pinned.
        if close_repo.is_sealed(conn, day):
            raise HTTPException(409, f"营业日 {day} 已封账，不可设为当前营业日")
        settings_repo.set_value(conn, "business_day", day)
        conn.commit()
        return {"business_day": day}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
