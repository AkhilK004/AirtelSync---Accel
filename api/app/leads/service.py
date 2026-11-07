"""Leads: creation, lazy derivation (abandoned / unaccepted / stuck KYC), scoring, routing, back-office list and status."""
from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache

import yaml

from app import clock
from app.advisor.models import AdvisorSession
from app.audit import audit
from app.config import API_ROOT, settings
from app.data.loaders import get_data
from app.engine.money import fmt_inr
from app.engine.pricing import build_quote, new_id
from app.errors import ApiError
from app.leads import engagement, scoring
from app.models.engine import QuoteState
from app.repo import get_repo

STATUSES = ("new", "contacted", "won", "lost")
KYC_STUCK_HOURS = 24


@lru_cache(maxsize=1)
def routing() -> dict:
    with open(API_ROOT / "config" / "routing.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def partner_for_city(city: str | None) -> str | None:
    return next((p["code"] for p in routing()["partners"] if city and city in p["cities"]), None)


def team_for_city(city: str | None) -> str:
    state = get_data().city_states().get(city or "")
    return next((t for t, states in routing()["field_teams"].items() if state in states), "Unassigned")


def compliance_hold(l: dict) -> str | None:
    """Business rule over the model (A61): a lead whose GSTIN is Cancelled/Suspended cannot be sold GSTIN-gated products, however
    likely it is to convert (finding 9: Cancelled GSTINs converted at 10.8%). Returns 'gstin_cancelled' / 'gstin_suspended' /
    'gstin_inactive' or None. Sources: seeded CSV row's GSTIN, the quote profile, or the GSTIN looked up during KYC."""
    d = get_data()
    gstin = None
    if l.get("seed_lead_id"):
        hit = d.leads.loc[d.leads["lead_id"] == l["seed_lead_id"], "gstin"]
        gstin = hit.iloc[0] if len(hit) and isinstance(hit.iloc[0], str) else None
    if not gstin and l.get("order_id"):
        from app.kyc import service as kyc
        gstin = kyc.load(l["order_id"]).declared_gstin
    if gstin:
        rec = d.gstin.get(gstin)
        if rec and rec.status != "Active":
            return f"gstin_{rec.status.lower()}"
    qd = get_repo().get("quotes", l["quote_id"]) if l.get("quote_id") else None
    if qd and (qd.get("profile") or {}).get("gstin_status") == "inactive":
        return "gstin_inactive"
    return None


@lru_cache(maxsize=1)
def _quote_accepted_rates() -> tuple[float, float]:
    """Activation rate after quote acceptance, (with GSTIN, without), from the leads data (finding 1: ~50% vs ~16%)."""
    L = get_data().leads
    q = L[L["stage_reached"].isin(["Quote accepted", "KYC complete", "Activated"])]
    r = q.groupby(q["has_gstin"].astype(bool))["activated"].mean()
    return float(r.get(True, 0.0)), float(r.get(False, 0.0))


def _has_gstin(l: dict) -> bool | None:
    """True / False when we know, None when we do not."""
    raw = l.get("raw_features")
    if raw is not None and raw.get("has_gstin") is not None:
        return bool(raw["has_gstin"])
    if l.get("order_id"):
        from app.kyc import service as kyc
        if kyc.load(l["order_id"]).declared_gstin:
            return True
    ctx = scoring.context(l)
    return bool(ctx["has_gstin"]) if (ctx.get("employees") or l.get("quote_id")) else None


def next_action(l: dict) -> dict | None:
    """The concrete step for the person working the lead (A65). Beyond a score: GSTIN is the gate at the quote -> KYC step."""
    hold = l.get("compliance_hold")
    if hold:
        return {"code": "restore_gstin", "text": f"{HOLD_TEXT.get(hold, 'GSTIN not active')}: GST-only products cannot be sold. Help the owner restore the GSTIN with the tax office, or switch to the Udyam-number KYC path."}
    if l.get("stage_reached") == "kyc" and _has_gstin(l) is False:  # KYC not complete yet (at "order" it already is)
        w, wo = _quote_accepted_rates()
        return {"code": "kyc_assist_udyam", "text": f"No GSTIN after quote acceptance: offer the Udyam-number KYC path (Udyam lookup + utility bill) and help with the paperwork. "
                                                      f"Only {wo:.0%} of such leads activate vs {w:.0%} with a GSTIN."}
    return None


HOLD_TEXT = {"gstin_cancelled": "GSTIN is Cancelled", "gstin_suspended": "GSTIN is Suspended", "gstin_inactive": "GSTIN is not active"}


def expected_value_paise(l: dict) -> int:
    """Expected monthly revenue if called = P(activate) x median monthly bundle value of the lead's segment (A62). 0 while on compliance hold."""
    if l.get("score") is None or l.get("compliance_hold"):
        return 0
    values = get_data().segment_median_bundle_value()
    inr = values.get(scoring.SEGMENT_NAME.get(l.get("segment") or "", ""), values["_all"])
    return int(round(l["score"] * inr)) * 100  # whole rupees: it is an estimate, not a price


def route_for(segment: str | None, partner_code: str | None, city: str | None = None, assisted: bool = False) -> tuple[str, str | None]:
    """Field force owns multi-site, manufacturers and assisted leads; partners own their cities / their code; telesales gets the rest."""
    if assisted or segment in ("multi_site", "manufacturer"):
        return "field_sales", partner_code
    code = partner_code or partner_for_city(city)
    return ("partner", code) if code else ("telesales", None)


def create_lead(sess: AdvisorSession, reason: str, segment: str | None, stage: str = "advisor",
                phone: str | None = None, preferred_time: str | None = None) -> str:
    repo = get_repo()
    existing = repo.get("leads", sess.lead_id) if sess.lead_id else None
    if existing:  # one lead per session; enrich it
        existing.update({k: v for k, v in (("phone", phone), ("preferred_time", preferred_time)) if v})
        if reason == "requested_human":
            existing["reason"] = reason
        repo.put("leads", existing["id"], existing)
        return existing["id"]
    lid = new_id()
    route, code = route_for(segment, sess.partner_code, sess.slots.city, assisted=reason == "needs_site_survey")
    repo.put("leads", lid, {
        "id": lid, "created_at": clock.now_iso(), "session_id": sess.id, "profile": sess.slots.model_dump(), "segment": segment,
        "stage_reached": stage, "reason": reason, "quote_id": sess.quote_id, "order_id": None, "score": None, "score_reasons": [],
        "route_to": route, "partner_code": code, "status": "new", "phone": phone, "preferred_time": preferred_time,
    })
    return lid


# ------------------------------------------------------------------ lazy derivation
def _age_minutes(iso: str) -> float:
    return (clock.now() - datetime.fromisoformat(iso)).total_seconds() / 60


def refresh() -> int:
    """Creates leads that are only knowable by the passage of time. Idempotent. Returns how many were created."""
    repo = get_repo()
    leads = repo.list("leads")
    have_sessions = {l["session_id"] for l in leads if l.get("session_id")}
    ordered_quotes = {o["quote_id"] for o in repo.list("orders")}
    made = 0
    for sd in repo.list("sessions"):
        s = AdvisorSession.model_validate(sd)
        if s.id in have_sessions or s.messages < 1 or _age_minutes(s.updated_at) < settings.ABANDON_MINUTES:
            continue
        if s.quote_id and s.quote_id in ordered_quotes:
            continue
        lid = new_id()
        reason, stage = ("quote_not_accepted", "quote") if s.recommended else ("abandoned", "advisor")
        route, code = route_for(None, s.partner_code, s.slots.city)
        repo.put("leads", lid, {"id": lid, "created_at": s.updated_at, "session_id": s.id, "profile": s.slots.model_dump(), "segment": None,
                                "stage_reached": stage, "reason": reason, "quote_id": s.quote_id, "order_id": None, "score": None,
                                "score_reasons": [], "route_to": route, "partner_code": code, "status": "new"})
        made += 1
    kyc_leads = {l["order_id"] for l in leads if l.get("reason") == "kyc_issue" and l.get("order_id")}
    for o in repo.list("orders"):
        if o["state"] != "KYC_ACTION_REQUIRED" or o["id"] in kyc_leads:
            continue
        last = max((e["ts"] for e in o["events"] if e["state"] == "KYC_ACTION_REQUIRED"), default=None)
        if last and _age_minutes(last) >= KYC_STUCK_HOURS * 60:
            lid = new_id()
            repo.put("leads", lid, {"id": lid, "created_at": last, "session_id": None, "profile": {"business_name": o.get("business_name")}, "segment": None,
                                    "stage_reached": "kyc", "reason": "kyc_issue", "kyc_status": "ACTION_REQUIRED", "quote_id": o.get("quote_id"),
                                    "order_id": o["id"], "score": None, "score_reasons": [], "route_to": "telesales", "partner_code": None, "status": "new"})
            made += 1
    return made


def _enrich(l: dict) -> dict:
    """Scores, checks compliance and routes a lead once, then persists (so the list is cheap afterwards)."""
    if l.get("score") is not None and "compliance_hold" in l and "next_action" in l and l.get("score_stage") == l["stage_reached"]:
        return l  # already scored for this stage (a lead that moves to a later stage is re-scored with that stage's model, A64)
    ctx = scoring.context(l)
    prob, reasons = scoring.score_lead(l)
    if not l.get("segment"):
        l["segment"] = ctx.get("segment")
    l["city"] = l.get("city") or ctx.get("city")
    if l["route_to"] != "field_sales":
        l["route_to"], l["partner_code"] = route_for(l["segment"], l.get("partner_code"), l.get("city"))
    l["score"], l["score_reasons"], l["score_stage"] = round(prob, 4), reasons, l["stage_reached"]
    l["compliance_hold"] = compliance_hold(l)
    if l["compliance_hold"]:
        l["route_to"] = "compliance"  # KYC-assist / GST-restoration desk, not a sales queue
    l["next_action"] = next_action(l)
    get_repo().put("leads", l["id"], l)
    return l


def _name(l: dict) -> str:
    p = l.get("profile") or {}
    if p.get("business_name"):
        return p["business_name"]
    bt = p.get("business_type") or "Business"
    return f"{bt}{' · ' + l['city'] if l.get('city') else ''}"


def row(l: dict) -> dict:
    return {"id": l["id"], "name": _name(l), "segment": l.get("segment"), "stage": l["stage_reached"], "reason": l["reason"], "route": l["route_to"],
            "partner_code": l.get("partner_code"), "territory_team": team_for_city(l.get("city")), "city": l.get("city"), "score": l.get("score"),
            "score_reasons": l.get("score_reasons", []),
            "expected_value_paise": (ev := expected_value_paise(l)), "expected_value_display": fmt_inr(ev), "compliance_hold": l.get("compliance_hold"), "next_action": l.get("next_action"), "age_hours": round(_age_minutes(l["created_at"]) / 60, 1), "status": l["status"],
            "order_id": l.get("order_id"), "quote_id": l.get("quote_id")}


def list_leads(route: str | None = None, segment: str | None = None, stage: str | None = None, status: str | None = None) -> list[dict]:
    refresh()
    out = [_enrich(l) for l in get_repo().list("leads")]
    out = [l for l in out if (not route or l["route_to"] == route) and (not segment or l.get("segment") == segment)
           and (not stage or l["stage_reached"] == stage) and (not status or l["status"] == status)]
    # Rank by expected monthly value (A62), then probability. Scores are comparable within a routing queue; filter by route for a queue view.
    out.sort(key=lambda l: (-expected_value_paise(l), -(l["score"] if l["score"] is not None else -1), l["created_at"]))
    return [row(l) for l in out]


def detail(lead_id: str) -> dict:
    l = get_repo().get("leads", lead_id)
    if not l:
        raise ApiError(404, "LEAD_NOT_FOUND", "lead.not_found")
    l = _enrich(l)
    repo = get_repo()
    out = row(l) | {"profile": _profile_view(l), "phone_masked": ("•" * 6 + l["phone"][-4:]) if l.get("phone") else None,
                    "preferred_time": l.get("preferred_time"), "engagement": engagement.for_lead(l), "kyc": None, "quote": None, "order": None}
    qd = repo.get("quotes", l["quote_id"]) if l.get("quote_id") else None
    if qd:
        q = build_quote(QuoteState.model_validate(qd), "en")
        out["quote"] = {"bundle": q.bundle_title, "monthly_total_display": q.monthly_total_display, "one_time_total_display": q.one_time_total_display,
                        "lines": [{"name": x.name, "qty": x.qty, "monthly": x.line_monthly_display} for x in q.lines],
                        "assumptions": [a.text for a in q.assumptions if a.key != "gst_extra"], "assisted": q.assisted}
    if l.get("order_id"):
        from app.kyc import service as kyc
        from app.orders import service as orders
        od = repo.get("orders", l["order_id"])
        if od:
            out["order"] = {"state": od["state"], "business_name": od.get("business_name")}
            v = kyc.view(l["order_id"], "en")
            out["kyc"] = {"decision": v["decision"], "issues": [c for c in v["checks"] if c["status"] != "PASS"]}
    return out


def _profile_view(l: dict) -> dict:
    p = dict(l.get("profile") or {})
    p.pop("business_name", None)
    ctx = scoring.context(l) if not l.get("raw_features") else {}
    shown = {k: v for k, v in {**ctx, **p}.items() if v not in (None, [], "", False) and k in
             ("business_type", "employees", "locations", "city", "city_tier", "has_gstin", "language", "tools", "wants", "current_tools", "budget_monthly", "segment")}
    if l.get("raw_features"):
        r = l["raw_features"]
        shown.update({"business_type": r["business_type"], "employees": r["employee_count"], "locations": r["num_sites"], "city_tier": r["city_tier"],
                      "has_gstin": r["has_gstin"], "language": r["preferred_language"], "source": r["lead_source"], "current_internet": r.get("current_internet")})
    return shown


def set_status(lead_id: str, status: str, actor: str) -> dict:
    if status not in STATUSES:
        raise ApiError(422, "STATUS_INVALID", "lead.status_invalid")
    repo = get_repo()
    l = repo.get("leads", lead_id)
    if not l:
        raise ApiError(404, "LEAD_NOT_FOUND", "lead.not_found")
    old, l["status"] = l["status"], status
    repo.put("leads", lead_id, l)
    audit(actor, "lead_status", lead_id, {"from": old, "to": status})
    return row(_enrich(l))
