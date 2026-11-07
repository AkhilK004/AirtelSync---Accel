"""Turn handling: NLU (LLM) -> merge -> deterministic policy -> engine -> NLG (LLM) with post-check."""
from __future__ import annotations

import json
import logging
import re

from app.advisor import templates as T
from app.advisor.models import (AdvisorReply, AdvisorSession, BudgetInfo, Progress, QuickReply, RecLine, RecSummary, now_iso)
from app.advisor.policy import Action, missing_slots, next_action
from app.advisor.postcheck import violations
from app.advisor.slots import (DEFAULT_CITY_TIER, DEFAULT_EMPLOYEES, DEFAULT_GSTIN, DEFAULT_LOCATIONS, REQUIRED_ORDER, SlotUpdate, Slots,
                               product_name, resolve_city, to_profile)
from app.analytics.events import log_event
from app.config import ASSISTED_CALLBACK_HOURS, settings
from app.data.loaders import get_data
from app.engine.eligibility import eligible
from app.engine.money import fmt_inr
from app.engine.pricing import build_quote, initial_state, new_id
from app.leads.service import create_lead
from app.llm import get_llm
from app.llm.prompts import NLG_SYSTEM, NLU_SYSTEM
from app.llm.rules_nlu import parse as rule_parse
from app.models.engine import Note, QuoteState
from app.repo import get_repo

log = logging.getLogger("advisor")
ASSUME_KEY = {"business_type": "business_type_default", "employees": "employees_default", "locations": "locations_default",
              "city": "city_default", "has_gstin": "gstin_default"}


# ------------------------------------------------------------------ sessions
def load_session(sid: str) -> AdvisorSession | None:
    d = get_repo().get("sessions", sid)
    return AdvisorSession.model_validate(d) if d else None


def save_session(s: AdvisorSession) -> None:
    s.updated_at = now_iso()
    s.history = s.history[-20:]
    get_repo().put("sessions", s.id, s.model_dump(mode="json"))


def start_session(language: str | None = None, channel: str | None = None, partner_code: str | None = None) -> AdvisorReply:
    s = AdvisorSession(id=new_id(), channel=channel, partner_code=partner_code)
    if language in T.LANGS:
        s.language, s.language_locked = language, True
    s.questions_asked, s.pending_slot = 1, "business_type"
    msg = T.tr(T.GREETING, s.language) + " " + T.tr(T.QUESTION["business_type"], s.language)
    s.history.append({"role": "assistant", "text": msg})
    save_session(s)
    log_event("advisor_started", s.id, {"channel": channel, "partner": bool(partner_code), "language": s.language})
    return _reply(s, msg, "ASK", chips_for="business_type")


# ------------------------------------------------------------------ NLU
def hybrid(u: SlotUpdate, r: SlotUpdate) -> SlotUpdate:
    """LLM understanding first; the deterministic parser fills what the LLM left empty and adds keyword-certain facts
    (tools, wants, unavailable items, injection and handoff intents). Lists are unions; on conflict the LLM wins."""
    d = u.model_copy(deep=True)
    for f in ("business_type", "employees", "locations", "city", "has_gstin", "budget_monthly", "fibre_available", "requested_unavailable_item", "language"):
        if getattr(d, f) is None and getattr(r, f) is not None:
            setattr(d, f, getattr(r, f))
    for f in ("current_tools", "wants", "dont_know"):
        setattr(d, f, list(dict.fromkeys([*getattr(u, f), *getattr(r, f)])))
    d.injection_attempt = u.injection_attempt or r.injection_attempt
    if d.intent in ("answer", "smalltalk", "off_topic") and r.intent in ("request_human", "ask_why", "ask_price"):
        d.intent = r.intent
    return d


def _nlu(sess: AdvisorSession, text: str) -> SlotUpdate:
    payload = json.dumps({"pending_slot": sess.pending_slot, "known_slots": sess.slots.model_dump(), "message": text}, ensure_ascii=False)
    rules = rule_parse(text, sess.pending_slot)
    try:
        u = get_llm().extract(NLU_SYSTEM, [payload], SlotUpdate)
        u = u if isinstance(u, SlotUpdate) else SlotUpdate.model_validate(u)
    except Exception as e:  # noqa: BLE001 - never fail a turn on NLU; fall back to deterministic rules
        log.warning("nlu_fallback %s", type(e).__name__)
        return rules
    return hybrid(u, rules)


def _merge(sess: AdvisorSession, u: SlotUpdate) -> bool:
    """Apply update to session slots. Returns True if any profile-relevant slot was set/changed."""
    s, progressed = sess.slots, False
    for slot in ("business_type", "employees", "locations", "has_gstin"):
        v = getattr(u, slot)
        if v is not None:
            if getattr(s, slot) != v:
                progressed = True
            setattr(s, slot, v)
            sess.assumptions.pop(slot, None)
    if u.city:
        name, tier = resolve_city(u.city)
        if name != s.city:
            progressed = True
        s.city = name
        sess.assumptions.pop("city", None)
        if tier is None:
            s.city_tier = DEFAULT_CITY_TIER
            sess.assumptions["city"] = Note(key="city_unknown", text="")
        else:
            s.city_tier = tier
    if u.fibre_available is not None and u.fibre_available != s.fibre_available:
        s.fibre_available, progressed = u.fibre_available, True
    if u.budget_monthly is not None:
        s.budget_monthly = u.budget_monthly
    for w in u.wants:
        if w not in s.wants:
            s.wants.append(w)
            progressed = progressed or sess.recommended
    for t in u.current_tools:
        if t not in s.current_tools:
            s.current_tools.append(t)
    for slot in u.dont_know:
        if slot in REQUIRED_ORDER and getattr(s, slot) is None:
            _default(sess, slot)
            progressed = True
    return progressed


def _default(sess: AdvisorSession, slot: str) -> None:
    s = sess.slots
    if slot == "employees":
        s.employees = DEFAULT_EMPLOYEES
    elif slot == "locations":
        s.locations = DEFAULT_LOCATIONS
    elif slot == "city":
        s.city, s.city_tier = "", DEFAULT_CITY_TIER
    elif slot == "has_gstin":
        s.has_gstin = DEFAULT_GSTIN
    elif slot == "business_type":
        s.business_type = "Other"
    sess.assumptions[slot] = Note(key=ASSUME_KEY[slot], text="")


# ------------------------------------------------------------------ chips / progress
def _chips(slot: str | None, lang: str) -> list[QuickReply]:
    if not slot:
        return []
    return [QuickReply(label=l, value=v) for l, v in T.CHIPS.get(slot, {}).get(lang, [])]


def _progress(sess: AdvisorSession) -> Progress:
    return Progress(asked=min(sess.questions_asked, settings.MAX_QUESTIONS), total=settings.MAX_QUESTIONS)


def _assumption_texts(sess: AdvisorSession, extra: list[Note]) -> tuple[list[str], list[str]]:
    notes = list(sess.assumptions.values()) + [n for n in extra if n.key != "gst_extra"]
    return [n.key for n in notes], [T.note_text(n.key, sess.language, n.params, n.text) for n in notes]


def _reply(sess: AdvisorSession, message: str, action: str, chips_for: str | None = None, chips: list[QuickReply] | None = None,
           rec: RecSummary | None = None, handoff: bool = False, budget: BudgetInfo | None = None, extra_notes: list[Note] | None = None,
           fallback: bool = False) -> AdvisorReply:
    keys, texts = _assumption_texts(sess, extra_notes or [])
    return AdvisorReply(session_id=sess.id, message=message, quick_replies=chips if chips is not None else _chips(chips_for, sess.language),
                        progress=_progress(sess), action=action, language=sess.language, recommendation=rec, quote_id=sess.quote_id,
                        handoff=handoff, lead_id=sess.lead_id, assumptions=keys, assumption_texts=texts, budget=budget, fallback_used=fallback)


# ------------------------------------------------------------------ recommendation
def _summary(sess: AdvisorSession) -> str:
    s = sess.slots
    bt = s.business_type if s.business_type and s.business_type != "Other" else T.tr(T.M["unknown_bt"], sess.language)
    return T.tr(T.M["summary"], sess.language, bt=bt, city=s.city or "—", employees=s.employees, locations=s.locations)


def _build_rec(sess: AdvisorSession):
    for slot in missing_slots(sess.slots):  # question budget spent: fill the rest with visible assumptions
        _default(sess, slot)
    profile, _ = to_profile(sess.slots)
    sig = profile.model_dump_json()
    repo = get_repo()
    stored = repo.get("quotes", sess.quote_id) if sess.quote_id else None
    if stored and sess.profile_sig == sig:
        state = QuoteState.model_validate(stored)
    else:
        state = initial_state(profile, sess.quote_id)  # same quote id on re-recommendation: the quote "updates"
        repo.put("quotes", state.id, state.model_dump(mode="json"))
        sess.quote_id, sess.profile_sig = state.id, sig
    return profile, state, build_quote(state)


def _budget(sess: AdvisorSession, state: QuoteState, quote) -> BudgetInfo | None:
    b = sess.slots.budget_monthly
    if not b:
        return None
    budget_paise = b * 100
    core_state = state.model_copy(update={"selected": {l.sku: l.qty for l in state.recommendation.lines}})
    cheapest = build_quote(core_state).monthly_total_paise  # cheapest eligible = core lines only; never a made-up price
    if cheapest > budget_paise:
        return BudgetInfo(budget_display=fmt_inr(budget_paise), cheapest_display=fmt_inr(cheapest), gap_display=fmt_inr(cheapest - budget_paise),
                          over_budget_by_extras=False)
    if quote.monthly_total_paise > budget_paise:
        return BudgetInfo(budget_display=fmt_inr(budget_paise), cheapest_display=fmt_inr(cheapest), gap_display=None, over_budget_by_extras=True)
    return None


def _leased_line(sess: AdvisorSession, profile, quote) -> dict | None:
    if "leased_line" not in sess.slots.wants or quote.segment.value == "manufacturer":
        return None
    prods = get_data().products
    checks = [eligible(prods[k], profile) for k in ("P05", "P06")]
    if any(c.ok for c in checks):
        return {"available": True}
    return {"available": False, "reason": (checks[0].reason_text or "").rstrip(".")}


def _rec_summary(sess: AdvisorSession, quote, profile) -> RecSummary:
    lang = sess.language
    lines = [RecLine(sku=l.sku, name=product_name(l.sku, lang), qty=l.qty, line_monthly_display=l.line_monthly_display,
                     reason=T.tr(T.NEED_REASON.get(l.need, T.NEED_REASON["dependency"]), lang, employees=profile.employees, locations=profile.locations))
             for l in quote.lines]
    addons_off = [product_name(a.sku, lang) for a in quote.addons if not a.on][:4]
    skipped = []
    shown = {l.sku for l in quote.lines}
    for e in quote.exclusions:
        if e.sku and e.sku not in shown and e.reason_code in ("GSTIN_REQUIRED", "CITY_TIER", "SIZE_TOO_SMALL", "TOO_FEW_SITES"):
            n = product_name(e.sku, lang)
            if n not in skipped:
                skipped.append(n)
    return RecSummary(bundle_name=quote.bundle_name.get(lang) or quote.bundle_name["en"], segment=quote.segment.value, lines=lines,
                      addon_names=addons_off, monthly_total_display=quote.monthly_total_display, monthly_total_paise=quote.monthly_total_paise,
                      one_time_total_display=quote.one_time_total_display if quote.one_time_total_paise else "", contract_months=quote.contract_months,
                      assisted=quote.assisted, skipped=skipped[:3])


# ------------------------------------------------------------------ template composition (fallback + offline NLG)
def _compose(facts: dict) -> str:
    lang, act = facts["language"], facts["action"]
    pre = ""
    if facts.get("refusal"):
        pre += T.tr(T.M["ack_refusal"], lang)
    if facts.get("unavailable_item"):
        pre += T.tr(T.M["ack_unavailable"], lang, item=facts["unavailable_item"])
    if act == "ASK":
        return pre + facts["question"]
    if act == "CLARIFY":
        return pre + ("" if pre or facts.get("smalltalk") else T.tr(T.CLARIFY, lang)) + facts["question"]
    if act == "HANDOFF":
        return pre + T.tr(T.M["handoff"], lang, hours=ASSISTED_CALLBACK_HOURS)
    rec = facts["recommendation"]
    if act == "EXPLAIN":
        out = T.tr(T.M["explain_intro"], lang, summary=facts["summary"]) + "\n"
        return pre + out + "\n".join(f"• {l['name']} — {l['reason']}" for l in rec["lines"])
    # RECOMMEND
    ll = facts.get("leased_line")
    if ll:
        pre += (T.tr(T.M["leased_unavailable"], lang, reason=ll["reason"]) + T.tr(T.M["leased_alt"], lang)) if not ll["available"] else T.tr(T.M["leased_survey"], lang)
    out = pre + T.tr(T.M["plan_intro"], lang, bundle=rec["bundle_name"]) + "\n"
    out += "\n".join(f"• {l['name']} — {l['reason']} ({l['line_monthly_display']})" for l in rec["lines"][:6]) + "\n"
    out += T.tr(T.M["total"], lang, total=rec["monthly_total_display"])
    if rec["one_time_total_display"]:
        out += T.tr(T.M["setup"], lang, setup=rec["one_time_total_display"])
    out += T.tr(T.M["contract"], lang, months=rec["contract_months"])
    b = facts.get("budget")
    if b:
        key = "budget_trim" if b["over_budget_by_extras"] else "budget_over"
        out += "\n" + T.tr(T.M[key], lang, budget=b["budget_display"], cheapest=b["cheapest_display"], gap=b["gap_display"] or "", names=", ".join(rec["addon_names"]) or "—")
    if rec.get("skipped"):
        out += "\n" + T.tr(T.M["skipped"], lang, names=", ".join(rec["skipped"]))
    if facts.get("no_gstin_hint"):
        out += " " + T.tr(T.M["no_gstin_hint"], lang)
    if rec["addon_names"] and not b:
        out += "\n" + T.tr(T.M["addons_hint"], lang, names=", ".join(rec["addon_names"][:3]))
    for a in facts.get("assumptions", []):
        out += "\n" + a
    out += "\n" + T.tr(T.M["refine"], lang)
    return out


def ensure_required(text: str, facts: dict) -> tuple[str, bool]:
    """Facts the owner must be told are appended (deterministic template sentence) when the LLM's wording left them out."""
    lang, low, extra = facts["language"], text.lower(), []
    item = facts.get("unavailable_item")
    if item and item.lower() not in low:
        extra.append(T.tr(T.M["ack_unavailable"], lang, item=item).strip())
    ll = facts.get("leased_line")
    if ll and not any(w in low for w in ("leased", "लीज़्ड", "लीज्ड")):
        extra.append((T.tr(T.M["leased_unavailable"], lang, reason=ll["reason"]) + T.tr(T.M["leased_alt"], lang)).strip() if not ll["available"] else T.tr(T.M["leased_survey"], lang).strip())
    rec = facts.get("recommendation")
    if rec and facts.get("no_gstin_hint") and "udyam" not in low and "उद्यम" not in low:
        extra.append(T.tr(T.M["no_gstin_hint"], lang))
    b = facts.get("budget")
    if b and b["budget_display"] not in text:
        key = "budget_trim" if b["over_budget_by_extras"] else "budget_over"
        extra.append(T.tr(T.M[key], lang, budget=b["budget_display"], cheapest=b["cheapest_display"], gap=b["gap_display"] or "", names=", ".join((rec or {}).get("addon_names", [])) or "—"))
    if rec and rec.get("assisted") and str(ASSISTED_CALLBACK_HOURS) not in text:
        extra.append(T.tr(T.M["assisted_called"], lang, hours=ASSISTED_CALLBACK_HOURS))
    if facts.get("refusal") and not any(w in low for w in ("can't", "cannot", "unable", "नहीं", "नाही")):
        extra.append(T.tr(T.M["ack_refusal"], lang).strip())
    return (text + chr(10) + chr(10).join(extra), True) if extra else (text, False)


def _render(sess: AdvisorSession, facts: dict) -> tuple[str, bool]:
    facts["template_text"] = _compose(facts)
    try:
        text = get_llm().generate(NLG_SYSTEM, facts, sess.language).strip()
    except Exception as e:  # noqa: BLE001
        log.warning("nlg_failed %s", type(e).__name__)
        return facts["template_text"], True
    if text == facts["template_text"]:
        return text, False
    text = re.sub(r"\*+", "", text)  # the chat bubble is plain text: strip any markdown the model adds
    bad = violations(text, facts, sess.language)
    if bad or not text:
        log.warning("nlg_violation count=%d kinds=%s", len(bad), sorted({b.split(":")[0] for b in bad}))
        return facts["template_text"], True
    text, added = ensure_required(text, facts)
    return text, added


# ------------------------------------------------------------------ main turn
def handle_message(sess: AdvisorSession, text: str) -> AdvisorReply:
    text = (text or "").strip()[:500]
    sess.messages += 1
    sess.history.append({"role": "user", "text": text})
    chip = text.lower()
    update = _nlu(sess, text)
    # language: set from the first message, then switch only on a confident non-English detection or an explicit request
    if update.language:
        explicit_en = update.language == "en" and re.search(r"in english|english (mein|me|madhe)", text.lower())
        if not sess.language_locked or (update.language != sess.language and (update.language != "en" or explicit_en)):
            sess.language, sess.language_locked = update.language, True
    if chip == "see price":
        update.intent = "ask_price"
    ask_tools = chip == "tools"
    before_slots = sess.slots.model_dump()
    progressed = _merge(sess, update)
    if sess.pending_slot == "current_tools":
        sess.tools_done = True
    if sess.slots.model_dump() != before_slots and not progressed and sess.recommended:
        progressed = True
    if not sess.recommended and update.intent == "smalltalk":
        progressed = False
    action = Action("ASK", "current_tools") if ask_tools and sess.recommended else next_action(sess, update, progressed)
    if action.kind == "CLARIFY" or (action.kind == "ASK" and not progressed):
        sess.confusion += 1 if action.kind == "CLARIFY" else 0
    else:
        sess.confusion = 0
    facts: dict = {"action": action.kind, "language": sess.language, "refusal": update.injection_attempt,
                   "unavailable_item": update.requested_unavailable_item, "smalltalk": update.intent == "smalltalk", "summary": _summary(sess)}
    reply_kwargs: dict = {}

    if action.kind in ("ASK", "CLARIFY"):
        slot = action.slot
        facts["question"] = T.tr(T.QUESTION[slot], sess.language)
        facts["slot"] = slot
        if action.kind == "ASK":
            sess.questions_asked += 1
            log_event("slot_filled", sess.id, {"asked": sess.questions_asked, "next": slot})
        sess.pending_slot = slot
        reply_kwargs.update(action=action.kind, chips_for=slot)
    elif action.kind == "HANDOFF":
        segment = None
        sess.lead_id = create_lead(sess, "requested_human", segment, stage="advisor")
        log_event("handoff_requested", sess.id, {"reason": "requested_human"})
        facts["handoff"] = {"callback_hours": ASSISTED_CALLBACK_HOURS}
        sess.pending_slot = None
        reply_kwargs.update(action="HANDOFF", handoff=True, chips=[])
    else:  # RECOMMEND / EXPLAIN
        profile, state, quote = _build_rec(sess)
        rec = _rec_summary(sess, quote, profile)
        facts["recommendation"] = rec.model_dump()
        budget = _budget(sess, state, quote)
        facts["budget"] = budget.model_dump() if budget else None
        facts["leased_line"] = _leased_line(sess, profile, quote)
        facts["no_gstin_hint"] = sess.slots.has_gstin != "yes" and any(e.reason_code == "GSTIN_REQUIRED" for e in quote.exclusions)
        keys, texts = _assumption_texts(sess, quote.assumptions)
        facts["assumptions"] = texts
        if quote.assisted:
            facts["assisted_callback_hours"] = ASSISTED_CALLBACK_HOURS
            if not sess.lead_id:
                sess.lead_id = create_lead(sess, "needs_site_survey", quote.segment.value, stage="quote")
                log_event("handoff_requested", sess.id, {"reason": "needs_site_survey"})
        if action.kind == "RECOMMEND" and not sess.recommended:
            log_event("recommendation_shown", sess.id, {"segment": quote.segment.value, "total_paise": quote.monthly_total_paise})
        sess.recommended = True
        sess.pending_slot = "current_tools" if action.kind == "RECOMMEND" and ask_tools else None
        reply_kwargs.update(action=action.kind, rec=rec, budget=budget, extra_notes=quote.assumptions, handoff=quote.assisted,
                            chips=[QuickReply(label=l, value=v) for l, v in T.POST_REC_CHIPS[sess.language]])

    msg, fb = _render(sess, facts)
    if action.kind == "ASK" and action.slot == "current_tools":
        reply_kwargs["chips_for"] = "current_tools"
        reply_kwargs.pop("chips", None)
    sess.history.append({"role": "assistant", "text": msg})
    save_session(sess)
    return _reply(sess, msg, fallback=fb, **reply_kwargs)
