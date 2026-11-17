from __future__ import annotations
import sqlite3
from typing import Any


def list_pickups(conn: sqlite3.Connection, business_day: str | None = None) -> list[dict[str, Any]]:
    if business_day:
        rows = conn.execute(
            "SELECT * FROM cash_pickups WHERE business_day=? ORDER BY occurred_at, id",
            (business_day,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM cash_pickups ORDER BY business_day DESC, occurred_at, id"
        ).fetchall()
    return [dict(r) for r in rows]


def day_pickup_total(conn: sqlite3.Connection, business_day: str) -> tuple[float, int]:
    row = conn.execute(
        "SELECT COALESCE(SUM(amount),0) s, COUNT(*) c FROM cash_pickups "
        "WHERE business_day=? AND status='confirmed'",
        (business_day,),
    ).fetchone()
    return float(row["s"]), int(row["c"])


def next_pickup_no(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT MAX(id) m FROM cash_pickups").fetchone()
    n = int(row["m"] or 0) + 1
    return f"PK-{n:04d}"


def insert_pickup(conn: sqlite3.Connection, **fields: Any) -> int:
    cur = conn.execute(
        '''INSERT INTO cash_pickups(pickup_no, business_day, occurred_at, amount, status, note, created_at)
           VALUES (?,?,?,?,?,?,?)''',
        (
            fields["pickup_no"],
            fields["business_day"],
            fields["occurred_at"],
            fields["amount"],
            fields["status"],
            fields.get("note"),
            fields["created_at"],
        ),
    )
    return int(cur.lastrowid)


def get_pickup(conn: sqlite3.Connection, pickup_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM cash_pickups WHERE id=?", (pickup_id,)).fetchone()
    return dict(row) if row else None


def delete_pickup(conn: sqlite3.Connection, pickup_id: int) -> None:
    conn.execute("DELETE FROM cash_pickups WHERE id=?", (pickup_id,))
