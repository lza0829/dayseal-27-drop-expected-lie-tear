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
    row = conn.execute("SELECT MAX(id) m FROM close_batches").fetchone()
    n = int(row["m"] or 0) + 1
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


def mark_superseded(conn: sqlite3.Connection, batch_id: int) -> None:
    conn.execute(
        "UPDATE close_batches SET status='superseded' WHERE id=? AND status='sealed'",
        (batch_id,),
    )


def void_variances(conn: sqlite3.Connection, batch_id: int) -> None:
    conn.execute(
        "UPDATE variance_rows SET disposition='voided' WHERE batch_id=? AND disposition='pending'",
        (batch_id,),
    )


def get_batch(conn: sqlite3.Connection, batch_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM close_batches WHERE id=?", (batch_id,)).fetchone()
    return dict(row) if row else None


def write_pickup_fields(
    conn: sqlite3.Connection, batch_id: int, pickup_count: int, pickup_total: float
) -> None:
    """Re-pin the batch pickup snapshot into its real columns.

    Only a still-writable batch may be re-pinned.  A sealed batch's pinned
    metrics are frozen: re-pinning it from a late event scan would rewrite the
    variance after the fact, so callers must fail loudly instead.
    """
    row = conn.execute(
        "SELECT status FROM close_batches WHERE id=?", (batch_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"close batch {batch_id} not found")
    if row["status"] == "sealed":
        raise PermissionError(f"close batch {batch_id} is sealed; pickup snapshot is frozen")
    conn.execute(
        "UPDATE close_batches SET pickup_count=?, pickup_total=? WHERE id=?",
        (int(pickup_count), float(pickup_total), batch_id),
    )


def fence_pending_count(
    conn: sqlite3.Connection, business_day: str | None = None
) -> int:
    if business_day is None:
        row = conn.execute(
            "SELECT COUNT(*) c FROM variance_rows WHERE disposition='pending'"
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) c FROM variance_rows WHERE disposition='pending' AND business_day=?",
            (business_day,),
        ).fetchone()
    return int(row["c"])


def fence_current_batches(conn: sqlite3.Connection, business_day: str) -> list[dict]:
    """Batches for a day with an honest `current` flag.

    A superseded batch stays superseded; it is never relabelled as sealed.
    """
    rows = conn.execute(
        "SELECT * FROM close_batches WHERE business_day=? ORDER BY id DESC",
        (business_day,),
    ).fetchall()
    current_id = next(
        (r["id"] for r in rows if r["status"] == "sealed"),
        None,
    )
    out = []
    for r in rows:
        item = dict(r)
        item["current"] = item.get("id") == current_id
        out.append(item)
    return out
