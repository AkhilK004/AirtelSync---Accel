"""Advisor-era engagement signals (A66). The 2026 Q2 CSV has none of these; they are the only way to improve the propensity model
beyond its ~0.72 ceiling. Counts only: no message text, no PII. Built from the funnel event log + session + quote + order.

`journey_rows()` is the future training table (one row per advisor session, with the 8 model inputs, the engagement features and
the outcome). Retrain once `readiness()` says ready (docs/model_card.md)."""
from __future__ import annotations

from collections import Counter

from app.advisor.models import AdvisorSession
from app.engine.pricing import build_quote
from app.leads import scoring
from app.models.engine import QuoteState
from app.repo import get_repo

RETRAIN_MIN_JOURNEYS = 300      # advisor journeys before a retrain with these features is worth trying
RETRAIN_MIN_ACTIVATIONS = 30    # positives: below this a 9+ feature model cannot be validated
ENGAGEMENT_FEATURES = ["advisor_messages", "questions_asked", "assumptions_used", "budget_stated", "budget_gap_inr", "quote_views",
                       "addon_toggles", "quote_shared", "handoff_requested", "tracker_views", "kyc_docs_uploaded", "kyc_uploads_failed"]


def _event_counts(refs: set[str]) -> dict[str, Counter]:
    out: dict[str, Counter] = {}
    for e in get_repo().list("events"):
        props = e.get("props") or {}
        if e["ref_id"] not in refs or props.get("seed"):
            continue
        out.setdefault(e["name"], Counter())[e["ref_id"]] += 1
        if e["name"] == "kyc_doc_uploaded" and not props.get("ok", True):
            out.setdefault("_kyc_failed", Counter())[e["ref_id"]] += 1
    return out


def _budget_gap_inr(sess: AdvisorSession, state: QuoteState | None) -> int:
    """How far the cheapest eligible bundle (core lines only) is above the stated budget; 0 when no budget or it fits."""
    b = sess.slots.budget_monthly
    if not b or state is None:
        return 0
    core = state.model_copy(update={"selected": {l.sku: l.qty for l in state.recommendation.lines}})
    return max(0, (build_quote(core).monthly_total_paise // 100) - b)


def compute(sess: AdvisorSession, quote_id: str | None = None, order_id: str | None = None) -> dict:
    repo = get_repo()
    quote_id = quote_id or sess.quote_id
    qd = repo.get("quotes", quote_id) if quote_id else None
    state = QuoteState.model_validate(qd) if qd else None
    ev = _event_counts({r for r in (sess.id, quote_id, order_id) if r})

    def n(name: str, ref: str | None) -> int:
        return ev.get(name, Counter()).get(ref, 0) if ref else 0

    return {
        "advisor_messages": sess.messages, "questions_asked": sess.questions_asked, "assumptions_used": len(sess.assumptions),
        "budget_stated": bool(sess.slots.budget_monthly), "budget_gap_inr": _budget_gap_inr(sess, state),
        "quote_views": n("quote_viewed", quote_id), "addon_toggles": n("addon_toggled", quote_id), "quote_shared": n("quote_shared", quote_id),
        "handoff_requested": n("handoff_requested", sess.id), "tracker_views": n("tracker_viewed", order_id),
        "kyc_docs_uploaded": n("kyc_doc_uploaded", order_id), "kyc_uploads_failed": n("_kyc_failed", order_id),
    }


def for_lead(lead: dict) -> dict | None:
    """Engagement for a back-office lead. None for seeded leads (their CSV row carries no such signals) or when there is no session."""
    if lead.get("raw_features") or not lead.get("session_id"):
        return None
    sd = get_repo().get("sessions", lead["session_id"])
    return compute(AdvisorSession.model_validate(sd), lead.get("quote_id"), lead.get("order_id")) if sd else None


def journey_rows() -> list[dict]:
    """One row per advisor session: model inputs + engagement + outcome (activated = the order for its quote reached ACTIVATED)."""
    repo = get_repo()
    orders = {o["quote_id"]: o for o in repo.list("orders") if o.get("quote_id")}
    rows = []
    for sd in repo.list("sessions"):
        s = AdvisorSession.model_validate(sd)
        o = orders.get(s.quote_id) if s.quote_id else None
        lead = {"session_id": s.id, "quote_id": s.quote_id, "order_id": o["id"] if o else None, "partner_code": s.partner_code}
        rows.append({"session_id": s.id, "created_at": s.created_at, "reached_quote": bool(s.quote_id), "ordered": o is not None,
                     "activated": bool(o and o["state"] == "ACTIVATED"), "inputs": scoring.raw_row(scoring.context(lead)),
                     "engagement": compute(s, s.quote_id, lead["order_id"])})
    return rows


def readiness(rows: list[dict] | None = None) -> dict:
    rows = journey_rows() if rows is None else rows
    act = sum(1 for r in rows if r["activated"])
    return {"journeys": len(rows), "activated": act, "min_journeys": RETRAIN_MIN_JOURNEYS, "min_activations": RETRAIN_MIN_ACTIVATIONS,
            "ready": len(rows) >= RETRAIN_MIN_JOURNEYS and act >= RETRAIN_MIN_ACTIVATIONS}
