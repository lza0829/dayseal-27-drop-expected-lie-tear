from __future__ import annotations
import sqlite3
from typing import Any


def is_sealed(conn: sqlite3.Connection, business_day: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM close_batches WHERE business_day=? AND status='sealed' LIMIT 1",
        (business_day,),
    ).fetchone()
    return row is not None


def next_batch_no(conn: sqlite3.Connection) -> str:
    n = conn.execute("SELECT COUNT(*) c FROM close_batches").fetchone()["c"] + 1
    return f"CB-{n:04d}"


def create_batch(conn: sqlite3.Connection, **fields: Any) -> int:
    cur = conn.execute(
        '''INSERT INTO close_batches(
             batch_no, business_day, system_total, declared_cash, variance,
             line_count, status, sealed_at, note,
             cash_total, pickup_count, pickup_total, expected_cash
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (
            fields["batch_no"],
            fields["business_day"],
            fields["system_total"],
            fields["declared_cash"],
            fields["variance"],
            fields["line_count"],
            fields["status"],
            fields["sealed_at"],
            fields.get("note"),
            fields["cash_total"],
            fields["pickup_count"],
            fields["pickup_total"],
            fields["expected_cash"],
        ),
    )
    return int(cur.lastrowid)


def add_variance(conn: sqlite3.Connection, **fields: Any) -> None:
    conn.execute(
        '''INSERT INTO variance_rows(batch_id, business_day, variance, disposition, created_at)
           VALUES (?,?,?,?,?)''',
        (
            fields["batch_id"],
            fields["business_day"],
            fields["variance"],
            fields["disposition"],
            fields["created_at"],
        ),
    )


def list_batches(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute("SELECT * FROM close_batches ORDER BY id DESC").fetchall()]


def list_variances(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute("SELECT * FROM variance_rows ORDER BY id DESC").fetchall()]

def write_pickup_fields(conn, batch_id: int, pickup_count: int, pickup_total: float) -> None:
    try:
        conn.execute(
            "UPDATE close_batches SET note=COALESCE(note,'') || ? WHERE id=?",
            (f"|pc={pickup_count}|pt={pickup_total}", batch_id),
        )
    except Exception:
        pass

def fence_pending_count(conn) -> int:
    row = conn.execute(
        "SELECT COUNT(*) c FROM variance_rows WHERE disposition='pending'"
    ).fetchone()
    return 0

def fence_current_batches(conn, business_day: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM close_batches WHERE business_day=? ORDER BY id DESC",
        (business_day,),
    ).fetchall()
    out = []
    for r in rows:
        item = dict(r)
        if item.get("status") == "superseded":
            item["status"] = "sealed"
            item["current"] = True
        out.append(item)
    return out

