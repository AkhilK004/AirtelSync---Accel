"""Builds the propensity model's raw input for a lead from whatever we know about it (advisor session, quote profile, seeded CSV row)."""
from __future__ import annotations

from app.advisor.models import AdvisorSession
from app.engine.recommender import recommend
from app.leads.propensity import score
from app.models.engine import Profile, QuoteState
from app.repo import get_repo

SEGMENT_NAME = {"micro_retail": "Micro retail & services", "professional_office": "Professional offices",
                "multi_site": "Small multi-site businesses", "manufacturer": "Small manufacturers"}
LANG_NAME = {"en": "English", "hi": "Hindi", "mr": "Marathi"}
ACCEL_TOOL = "Accel mobile"  # current_tools chip -> accel_existing feature (docs/assumptions.md A58)


def context(lead: dict) -> dict:
    """Normalised facts about a lead. Keys may be None when unknown."""
    repo = get_repo()
    ctx = {"business_type": None, "employees": None, "locations": None, "city": None, "city_tier": None, "has_gstin": False,
           "language": "en", "tools": [], "wants": [], "channel": None, "segment": lead.get("segment"), "partner_code": lead.get("partner_code")}
    sd = repo.get("sessions", lead["session_id"]) if lead.get("session_id") else None
    if sd:
        s = AdvisorSession.model_validate(sd)
        sl = s.slots
        ctx.update(business_type=sl.business_type, employees=sl.employees, locations=sl.locations, city=sl.city, city_tier=sl.city_tier,
                   has_gstin=sl.has_gstin == "yes", language=s.language, tools=sl.current_tools, wants=sl.wants, channel=s.channel)
        return ctx
    qd = repo.get("quotes", lead["quote_id"]) if lead.get("quote_id") else None
    if qd:
        st = QuoteState.model_validate(qd)
        p: Profile = st.profile
        ctx.update(business_type=p.business_type, employees=p.employees, locations=p.locations, city_tier=p.city_tier,
                   has_gstin=p.gstin_status == "active", wants=p.wants, segment=st.recommendation.segment.value)
        od = repo.get("orders", lead["order_id"]) if lead.get("order_id") else None
        if od:
            ctx["language"] = od.get("language", "en")
    return ctx


def raw_row(ctx: dict) -> dict:
    """Model inputs (features.RAW_INPUTS) for a live lead. Only facts the advisor collected; nothing imputed except the channel mapping."""
    seg = ctx.get("segment")
    if not seg and ctx.get("employees"):
        prof = Profile(business_type=ctx["business_type"], employees=ctx["employees"] or 1, locations=ctx["locations"] or 1,
                       city_tier=ctx["city_tier"] or 2, gstin_status="active" if ctx["has_gstin"] else "none")
        seg = recommend(prof).segment.value
    seg_name = SEGMENT_NAME.get(seg or "", "Micro retail & services")
    tools = ctx.get("tools") or []
    internet = next((t for t in ("Mobile hotspot", "Home broadband", "Leased line") if t in tools), None)
    source = "Channel partner" if ctx.get("partner_code") else ("WhatsApp campaign" if ctx.get("channel") == "whatsapp" else "Website form")
    return {
        "segment": seg_name, "city_tier": ctx.get("city_tier") or 2, "lead_source": source, "current_internet": internet,
        "has_gstin": bool(ctx.get("has_gstin")), "current_provider": "Accel" if ACCEL_TOOL in tools else None,
        "employee_count": ctx.get("employees") or 2, "num_sites": ctx.get("locations") or 1,
        # display only (not model inputs)
        "business_type": ctx.get("business_type") or "Other", "preferred_language": LANG_NAME.get(ctx.get("language") or "en", "English"),
    }


def score_lead(lead: dict) -> tuple[float, list[str]]:
    import pandas as pd
    row = lead.get("raw_features") or raw_row(context(lead))  # seeded leads carry their real CSV row
    return score(pd.DataFrame([row]))
