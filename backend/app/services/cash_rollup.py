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
    snapshot = pickup_math.batch_pickup_snapshot(conn, business_day, pickup_repo)
    return {
        "business_day": business_day,
        "cash_total": round(cash_total, 2),
        "line_count": line_count,
        "pickup_total": snapshot["pickup_total"],
        "pickup_count": snapshot["pickup_count"],
        "expected_cash": pickup_math.expected_cash(
            cash_total, snapshot["pickup_total"], pickup_math.DEDUCT
        ),
    }


def pickup_snapshot(conn: sqlite3.Connection, business_day: str) -> dict[str, Any]:
    """The event-table snapshot that the batch header must pin verbatim."""
    from app.repositories import pickups as pickup_repo

    return pickup_math.batch_pickup_snapshot(conn, business_day, pickup_repo)
