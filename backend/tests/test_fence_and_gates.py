from __future__ import annotations

import pytest

from app import align_27, fence_27
from app.repositories import closes as close_repo


def test_gate_matrix_closes_every_path_when_sealed():
    sealed = align_27.gate_matrix(True, 0, False)
    assert sealed == {
        "allow_create": False,
        "allow_patch": False,
        "allow_import": False,
        "allow_reverse": False,
        "allow_pickup": False,
        "pending_ok": True,  # no pending variance, but the day stays closed
    }
    assert align_27.gate_matrix(False, 2, False)["pending_ok"] is False
    assert align_27.gate_matrix(False, 2, True)["pending_ok"] is True
    open_day = align_27.gate_matrix(False, 0, False)
    assert all(open_day.values())


def test_bypass_matrix_offers_no_sealed_bypass():
    assert not any(fence_27.bypass_matrix().values())


def test_fence_overlay_derives_from_pending_variances():
    clear = fence_27.overlay_counts({"open_variance_count": 2}, open_variance_count=0, sealed=False)
    assert clear["pending_fence"] == "clear"
    assert clear["seal_allowed"] is True

    pending = fence_27.overlay_counts({}, open_variance_count=2, sealed=False)
    assert pending["pending_fence"] == "pending"
    assert pending["seal_allowed"] is False
    assert pending["open_variance_count"] == 2

    sealed = fence_27.overlay_counts({}, open_variance_count=0, sealed=True)
    assert sealed["seal_allowed"] is False


def test_gate_open_consults_sealed_state(client, fresh_day):
    from app.db import connect

    conn = connect()
    try:
        assert fence_27.gate_open(conn, business_day=fresh_day, close_repo=close_repo) is True
    finally:
        conn.close()

    summary = client.get("/api/close/preview", params={"business_day": fresh_day}).json()
    client.post(
        "/api/close/seal",
        json={"business_day": fresh_day, "declared_cash": summary["expected_cash"]},
    )

    conn = connect()
    try:
        assert fence_27.gate_open(conn, business_day=fresh_day, close_repo=close_repo) is False
    finally:
        conn.close()


def test_fence_current_batches_does_not_promote_superseded(client, fresh_day):
    from app.db import connect

    summary = client.get("/api/close/preview", params={"business_day": fresh_day}).json()
    batch_id = client.post(
        "/api/close/seal",
        json={"business_day": fresh_day, "declared_cash": summary["expected_cash"]},
    ).json()["batch_id"]

    conn = connect(immediate=True)
    try:
        conn.execute(
            "UPDATE close_batches SET status='superseded' WHERE id=?", (batch_id,)
        )
        conn.commit()
        rows = close_repo.fence_current_batches(conn, fresh_day)
    finally:
        conn.close()

    assert rows[0]["status"] == "superseded"
    assert rows[0]["current"] is False
