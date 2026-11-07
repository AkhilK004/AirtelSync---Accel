"""Funnel + KPI panel computed from the event log and orders (PLAN Phase 7, key question 5)."""
from __future__ import annotations

from datetime import date
from statistics import median

from app.repo import get_repo

# Baselines (docs/findings.md) and the targets from the business case
BASELINE = {"lead_to_activation_pct": 7.4, "days_to_activate": 17.6, "status_checks_per_order": 3.0, "needs_to_quote_pct": 44.0}
TARGET = {"lead_to_activation_pct": 14.0, "days_to_activate": 5.0, "status_checks_per_order": 0.5, "needs_to_quote_pct": 65.0}

STAGES = [("advisor_started", "Advisor started"), ("recommendation_shown", "Recommendation shown"), ("quote_accepted", "Quote accepted"),
          ("order_placed", "Order placed"), ("kyc_complete", "KYC complete"), ("activated", "Activated")]


def _pct(a: int, b: int) -> float | None:
    return round(100 * a / b, 1) if b else None


def compute() -> dict:
    repo = get_repo()
    events = repo.list("events")
    by: dict[str, set[str]] = {k: set() for k, _ in STAGES}
    decisions: list[str] = []
    views = 0
    seeded = 0
    for e in events:
        n, ref, props = e["name"], e["ref_id"], e.get("props", {})
        seeded += bool(props.get("seed"))
        if n == "advisor_started":
            by["advisor_started"].add(ref)
        elif n == "recommendation_shown":
            by["recommendation_shown"].add(ref)
        elif n == "quote_accepted":
            by["quote_accepted"].add(ref)
        elif n == "checkout_completed":
            by["order_placed"].add(ref)
        elif n == "kyc_decided":
            decisions.append(props.get("decision", ""))
            if props.get("decision") == "APPROVED":
                by["kyc_complete"].add(ref)
        elif n == "order_state_changed" and props.get("state") == "ACTIVATED":
            by["activated"].add(ref)
        elif n == "tracker_viewed":
            views += 1
    stages, prev = [], None
    for k, label in STAGES:
        c = len(by[k])
        stages.append({"key": k, "label": label, "count": c, "pct_of_prev": _pct(c, prev) if prev is not None else None})
        prev = c
    orders = repo.list("orders")
    days = []
    for o in orders:
        act = next((e["ts"] for e in o.get("events", []) if e["state"] == "ACTIVATED" and e["message_key"] == "activated"), None)
        if act:
            days.append((date.fromisoformat(act[:10]) - date.fromisoformat(o["created_at"][:10])).days)
    started, activated = len(by["advisor_started"]), len(by["activated"])
    nq = len(by["recommendation_shown"])
    return {
        "stages": stages,
        "kpis": {
            "lead_to_activation_pct": _pct(activated, started), "needs_to_quote_pct": _pct(len(by["quote_accepted"]), nq),
            "median_days_to_activate": median(days) if days else None, "activated_orders": len(days),
            "kyc_auto_approval_pct": _pct(decisions.count("APPROVED"), len(decisions)), "kyc_decisions": len(decisions),
            "status_checks_per_order": round(views / len(orders), 2) if orders else None, "orders": len(orders),
            "handoffs": sum(1 for e in events if e["name"] == "handoff_requested"),
        },
        "baseline": BASELINE, "target": TARGET, "seeded_events": seeded, "total_events": len(events),
    }
