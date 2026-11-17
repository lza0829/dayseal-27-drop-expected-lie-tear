from __future__ import annotations

import sqlite3

import pytest

from app import pickup_math
from app.db import connect
from app.repositories import closes as close_repo
from app.repositories import pickups as pickup_repo


def _summary(client, day):
    return client.get("/api/close/preview", params={"business_day": day}).json()


def _add_pickup(client, day, amount):
    r = client.post(
        "/api/pickups", json={"business_day": day, "amount": amount, "note": "押运"}
    )
    assert r.status_code == 200, r.text
    return r.json()


def _seal(client, day, declared):
    return client.post(
        "/api/close/seal", json={"business_day": day, "declared_cash": declared}
    )


# 1. 事件在期待未扣
def test_expected_cash_deducts_confirmed_events(client, fresh_day):
    _add_pickup(client, fresh_day, 10)
    _add_pickup(client, fresh_day, 25.5)
    summary = _summary(client, fresh_day)
    assert summary["pickup_count"] == 2
    assert summary["pickup_total"] == 35.5
    assert summary["expected_cash"] == round(summary["cash_total"] - 35.5, 2)

    body = _seal(client, fresh_day, summary["expected_cash"]).json()
    assert body["expected_cash"] == summary["expected_cash"]
    assert body["system_total"] == summary["expected_cash"]
    assert body["variance"] == 0.0


def test_single_global_policy_is_deduct(client, fresh_day):
    _add_pickup(client, fresh_day, 12)
    summary = _summary(client, fresh_day)
    assert pickup_math.expected_cash(
        summary["cash_total"], summary["pickup_total"], pickup_math.DEDUCT
    ) == summary["expected_cash"]
    # The audit-only reading is expressed but never used for the pinned batch.
    assert pickup_math.expected_cash(
        summary["cash_total"], summary["pickup_total"], pickup_math.AUDIT
    ) == summary["cash_total"]
    with pytest.raises(ValueError):
        pickup_math.expected_cash(1.0, 0.0, "deduct-but-audit")


# 2. 批快照 = 事件表扫描
def test_batch_snapshot_matches_event_scan(client, fresh_day):
    _add_pickup(client, fresh_day, 7)
    _add_pickup(client, fresh_day, 8)
    _add_pickup(client, fresh_day, 9)
    summary = _summary(client, fresh_day)
    body = _seal(client, fresh_day, summary["expected_cash"]).json()

    conn = connect()
    try:
        total, count = pickup_repo.day_pickup_total(conn, fresh_day)
        snapshot = pickup_math.batch_pickup_snapshot(conn, fresh_day, pickup_repo)
    finally:
        conn.close()

    assert snapshot["pickup_count"] == count == summary["pickup_count"] == body["pickup_count"]
    assert snapshot["pickup_total"] == total == summary["pickup_total"] == body["pickup_total"]

    batches = client.get("/api/close/batches").json()
    batch = next(b for b in batches if b["business_day"] == fresh_day)
    assert batch["pickup_count"] == count
    assert batch["pickup_total"] == pytest.approx(total)
    assert batch["expected_cash"] == pytest.approx(summary["expected_cash"])


# 3. 封后补事件不能改长短款
def test_sealed_day_refuses_late_events(client, fresh_day):
    _add_pickup(client, fresh_day, 10)
    summary = _summary(client, fresh_day)
    sealed = _seal(client, fresh_day, summary["expected_cash"] - 5).json()
    assert sealed["variance"] == -5.0

    before = client.get("/api/close/variances").json()
    late = client.post(
        "/api/pickups", json={"business_day": fresh_day, "amount": 100}
    )
    assert late.status_code == 409
    delete = client.delete("/api/pickups/1")
    assert delete.status_code in {404, 409}

    after = client.get("/api/close/variances").json()
    assert before == after
    consistency = client.get(
        "/api/close/consistency", params={"business_day": fresh_day}
    ).json()
    assert consistency["consistent"] is True
    assert consistency["pinned"]["variance"] == sealed["variance"]


def test_sealed_day_refuses_events_at_database_level(client, fresh_day):
    _add_pickup(client, fresh_day, 3)
    summary = _summary(client, fresh_day)
    assert _seal(client, fresh_day, summary["expected_cash"]).status_code == 200

    conn = connect(immediate=True)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            pickup_repo.insert_pickup(
                conn,
                pickup_no="PK-SIDE",
                business_day=fresh_day,
                occurred_at="2030-01-01T00:00:00Z",
                amount=50,
                status="confirmed",
                note=None,
                created_at="2030-01-01T00:00:00Z",
            )
    finally:
        conn.rollback()
        conn.close()


def test_sealed_batch_pickup_snapshot_cannot_be_rewritten(client, fresh_day):
    summary = _summary(client, fresh_day)
    batch_id = _seal(client, fresh_day, summary["expected_cash"]).json()["batch_id"]

    conn = connect(immediate=True)
    try:
        with pytest.raises(PermissionError):
            close_repo.write_pickup_fields(conn, batch_id, 9, 999.0)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE close_batches SET pickup_total=999 WHERE id=?", (batch_id,)
            )
    finally:
        conn.rollback()
        conn.close()


def test_sealed_event_cannot_be_edited(client, fresh_day):
    pickup = _add_pickup(client, fresh_day, 4)
    summary = _summary(client, fresh_day)
    assert _seal(client, fresh_day, summary["expected_cash"]).status_code == 200

    conn = connect(immediate=True)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE cash_pickups SET amount=400 WHERE id=?", (pickup["id"],)
            )
    finally:
        conn.rollback()
        conn.close()


def test_void_is_the_only_way_to_release_a_sealed_day(client, fresh_day):
    _add_pickup(client, fresh_day, 10)
    summary = _summary(client, fresh_day)
    sealed = _seal(client, fresh_day, summary["expected_cash"]).json()

    r = client.post(f"/api/close/batches/{sealed['batch_id']}/void", json={"reason": "补登解款"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "superseded"

    # The day is writable again and the voided batch stays auditable.
    assert client.post("/api/pickups", json={"business_day": fresh_day, "amount": 5}).status_code == 200
    batches = client.get("/api/close/batches").json()
    voided = next(b for b in batches if b["id"] == sealed["batch_id"])
    assert voided["status"] == "superseded"
    assert voided["expected_cash"] == sealed["expected_cash"]

    # Re-sealing pins a fresh scan, and the two can differ honestly.
    fresh = _summary(client, fresh_day)
    resealed = _seal(client, fresh_day, fresh["expected_cash"]).json()
    assert resealed["expected_cash"] < sealed["expected_cash"]
    assert client.get("/api/close/consistency", params={"business_day": fresh_day}).json()["consistent"] is True


def test_voiding_an_already_superseded_batch_is_refused(client, fresh_day):
    summary = _summary(client, fresh_day)
    batch_id = _seal(client, fresh_day, summary["expected_cash"]).json()["batch_id"]
    assert client.post(f"/api/close/batches/{batch_id}/void", json={}).status_code == 200
    assert client.post(f"/api/close/batches/{batch_id}/void", json={}).status_code == 409
    assert client.post("/api/close/batches/9999/void", json={}).status_code == 404



# 4. 预览 = 落批
def test_preview_matches_sealed_batch(client, fresh_day):
    _add_pickup(client, fresh_day, 40)
    preview = _summary(client, fresh_day)
    sealed = _seal(client, fresh_day, preview["expected_cash"] + 1.25).json()
    for key in ("cash_total", "pickup_total", "pickup_count", "expected_cash", "line_count"):
        assert sealed[key] == pytest.approx(preview[key])
    assert sealed["variance"] == 1.25

    again = _summary(client, fresh_day)
    assert again["sealed"] is True
    assert again["expected_cash"] == preview["expected_cash"]


def test_seal_requires_declared_cash(client, fresh_day):
    r = client.post("/api/close/seal", json={"business_day": fresh_day})
    assert r.status_code == 400


def test_sealed_day_cannot_become_writable_day(client, fresh_day):
    summary = _summary(client, fresh_day)
    _seal(client, fresh_day, summary["expected_cash"])
    r = client.put("/api/settings/business-day", json={"business_day": fresh_day})
    assert r.status_code == 409
