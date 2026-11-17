from __future__ import annotations
import sqlite3
from typing import Any
from app import pickup_math


def day_summary(conn: sqlite3.Connection, business_day: str) -> dict[str, Any]:
    """营业日现金口径的唯一汇总源。

    封账预览、封账落库、总览、解款页均从这里取数，避免各处各算一套。
    期待实盘 = 现金流水合计 − 当日已确认解款合计。
    """
    from app.repositories import lines as line_repo
    from app.repositories import pickups as pickup_repo

    cash_total, line_count = line_repo.day_total(conn, business_day)
    pickup_total, pickup_count = pickup_repo.day_pickup_total(conn, business_day)
    return {
        "business_day": business_day,
        "cash_total": round(cash_total, 2),
        "line_count": line_count,
        "pickup_total": round(pickup_total, 2),
        "pickup_count": pickup_count,
        "expected_cash": round(cash_total - pickup_total, 2),
    }
