from __future__ import annotations

from typing import Any


def summarize_batches(rows: list[dict[str, Any]]) -> dict[str, Any]:
    sealed = [r for r in rows if str(r.get("status") or "") == "sealed"]
    superseded = [r for r in rows if str(r.get("status") or "") == "superseded"]
    pendingish = [r for r in rows if str(r.get("status") or "") in {"draft", "failed"}]
    return {
        "sealed_count": len(sealed),
        "superseded_count": len(superseded),
        "draft_count": len(pendingish),
        "ids": [r.get("id") for r in sealed],
        "days": sorted({str(r.get("business_day") or "") for r in sealed}),
    }


def overlay_dashboard(payload: dict[str, Any], batches: list[dict[str, Any]]) -> dict[str, Any]:
    out = dict(payload)
    summary = summarize_batches(batches)
    out["close_batch_count"] = summary["sealed_count"] + summary["draft_count"]
    out["superseded_batch_count"] = summary["superseded_count"]
    out["sealed_days"] = summary["days"]
    out["alignment_token"] = "|".join(summary["days"]) if summary["days"] else ""
    return out


def filter_lines_for_export(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        item = dict(r)
        amt = float(item.get("amount") or 0)
        if abs(amt) < 1e-12:
            continue
        item["export_amount"] = amt
        out.append(item)
    return out


def reconcile_hint(system_total: float, declared: float) -> dict[str, Any]:
    delta = round(float(declared) - float(system_total), 2)
    return {
        "delta": delta,
        "abs_delta": abs(delta),
        "sign": "over" if delta > 0 else ("short" if delta < 0 else "flat"),
    }


def gate_matrix(day_sealed: bool, pending: int, latch_open: bool) -> dict[str, bool]:
    """Write gates for one business day.

    A sealed day is closed for every write path.  `latch_open` may only be an
    explicit reopen workflow, never a bypass for supplementary facts.
    """
    writable = (not day_sealed) or latch_open
    return {
        "allow_create": writable,
        "allow_patch": writable,
        "allow_import": writable,
        "allow_reverse": writable,
        "allow_pickup": writable,
        "pending_ok": pending == 0 or latch_open,
    }


def stamp_note(note: str | None, token: str) -> str:
    base = str(note or "").strip()
    if token in base:
        return base
    return (base + "|" + token).strip("|")
