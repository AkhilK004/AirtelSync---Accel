"""Quote computation. All money is int paise; the LLM and frontend never compute money."""
from __future__ import annotations

import os
import time

from app.advisor import templates as T
from app.advisor.slots import product_name
from app.config import PRICE_POINT_RULE, settings
from app.data.loaders import get_data
from app.engine.dependencies import dependents_to_drop, pick_dependency, unmet
from app.engine.money import fmt_inr, midpoint_rupee_paise, pct_of
from app.engine.recommender import blocked_skus, dep_qty, recommend
from app.models.engine import (AddonOption, Note, Profile, Quote, QuoteLine, QuoteState,
                               Recommendation, ToggleResult)


class EngineError(Exception):
    def __init__(self, status: int, code: str, message_key: str, params: dict | None = None, text: str = ""):
        super().__init__(text or code)
        self.status, self.code, self.message_key, self.params, self.text = status, code, message_key, params or {}, text


def new_id() -> str:
    """Time-sortable ULID-like id (48-bit ms timestamp + 40 random bits)."""
    return f"{int(time.time() * 1000):012x}{os.urandom(5).hex()}"


def unit_price_paise(sku: str) -> int:
    p = get_data().products[sku]
    return midpoint_rupee_paise(p.monthly_price_min_paise, p.monthly_price_max_paise)


def initial_state(profile: Profile, quote_id: str | None = None) -> QuoteState:
    rec = recommend(profile)
    selected = {l.sku: l.qty for l in rec.lines}
    by_sku = {a.sku: a for a in rec.addons}
    for sku in rec.default_on:
        selected[sku] = by_sku[sku].qty
    return QuoteState(id=quote_id or new_id(), profile=profile, recommendation=rec, selected=selected)


def _need_of(rec: Recommendation, sku: str) -> tuple[str, bool, list[str]]:
    for l in rec.lines:
        if l.sku == sku:
            return l.need, True, l.why
    for a in rec.addons:
        if a.sku == sku:
            return a.need, False, a.why
    return "dependency", False, ["needed_by:addon"]


def _reason(need: str, state: QuoteState, lang: str) -> str:
    p = state.profile
    return T.tr(T.NEED_REASON.get(need, T.NEED_REASON["dependency"]), lang, employees=p.employees, locations=p.locations)


def build_quote(state: QuoteState, lang: str = "en") -> Quote:
    prods = get_data().products
    rec = state.recommendation
    order = [l.sku for l in rec.lines] + [a.sku for a in rec.addons] + sorted(set(state.selected) - {l.sku for l in rec.lines} - {a.sku for a in rec.addons})
    lines: list[QuoteLine] = []
    for sku in order:
        if sku not in state.selected:
            continue
        p, qty = prods[sku], state.selected[sku]
        need, required, why = _need_of(rec, sku)
        up = unit_price_paise(sku)
        lines.append(QuoteLine(
            sku=sku, name=product_name(sku, lang), category=p.category, description=p.description, unit=p.unit, need=need, qty=qty,
            required=required, why=why, unit_price_paise=up, unit_price_display=fmt_inr(up),
            line_monthly_paise=up * qty, line_monthly_display=fmt_inr(up * qty),
            setup_paise=p.setup_fee_paise * qty, setup_display=fmt_inr(p.setup_fee_paise * qty),
            contract_months=p.contract_months, reason=_reason(need, state, lang)))
    sub = sum(l.line_monthly_paise for l in lines)
    gst = pct_of(sub, settings.GST_RATE)
    one = sum(l.setup_paise for l in lines)
    one_gst = pct_of(one, settings.GST_RATE)
    addons = []
    for a in rec.addons:
        p, up = prods[a.sku], unit_price_paise(a.sku)
        addons.append(AddonOption(sku=a.sku, name=product_name(a.sku, lang), reason=_reason(a.need, state, lang), need=a.need, qty=a.qty, on=a.sku in state.selected,
                                  monthly_paise=up * a.qty, monthly_display=fmt_inr(up * a.qty),
                                  setup_display=fmt_inr(p.setup_fee_paise * a.qty), can_toggle=True))
    assumptions = [n.model_copy(update={"text": T.note_text(n.key, lang, n.params, n.text)}) for n in rec.assumptions]
    assumptions.append(Note(key="gst_extra", params={"rate": int(settings.GST_RATE * 100)},
                            text=T.note_text("gst_extra", lang, {"rate": int(settings.GST_RATE * 100)}, "")))
    return Quote(
        id=state.id, segment=rec.segment, bundle_name=rec.bundle_name, bundle_title=rec.bundle_name.get(lang) or rec.bundle_name["en"], lines=lines, addons=addons,
        monthly_subtotal_paise=sub, gst_paise=gst, monthly_total_paise=sub + gst,
        one_time_paise=one, one_time_gst_paise=one_gst, one_time_total_paise=one + one_gst,
        monthly_subtotal_display=fmt_inr(sub), gst_display=fmt_inr(gst), monthly_total_display=fmt_inr(sub + gst),
        one_time_display=fmt_inr(one), one_time_gst_display=fmt_inr(one_gst), one_time_total_display=fmt_inr(one + one_gst),
        contract_months=max((l.contract_months for l in lines), default=0), price_rule=PRICE_POINT_RULE,
        gst_rate_pct=int(settings.GST_RATE * 100), assumptions=assumptions, exclusions=rec.exclusions,
        assisted=rec.assisted, assisted_reason=rec.assisted_reason)


def toggle(state: QuoteState, sku: str, on: bool, lang: str = "en") -> tuple[QuoteState, list[Note]]:
    prods = get_data().products
    rec = state.recommendation
    required = {l.sku for l in rec.lines}
    pool = {a.sku: a for a in rec.addons}
    notices: list[Note] = []
    sel = dict(state.selected)
    if sku in required:
        if on:
            return state, []
        raise EngineError(409, "REQUIRED_LINE", "quote.required_line", {"sku": sku},
                          f"{prods[sku].name} is part of your core bundle and cannot be removed.")
    if sku not in pool:
        raise EngineError(404, "UNKNOWN_ADDON", "quote.unknown_addon", {"sku": sku}, f"{sku} is not an add-on of this quote.")
    if on:
        if sku in sel:
            return state, []
        sel[sku] = pool[sku].qty
        p = prods[sku]
        if unmet(p, set(sel)):
            dep = pick_dependency(p, state.profile, prods, blocked_skus(state.profile))
            if dep is None:
                raise EngineError(409, "DEPENDENCY_INELIGIBLE", "quote.dependency_ineligible", {"sku": sku},
                                  f"{p.name} needs an internet link that is not available for you.")
            sel[dep] = dep_qty(dep, state.profile)
            notices.append(Note(key="dep_added", params={"sku": dep, "because": sku},
                                text=T.tr(T.NOTE["dep_added"], lang, name=product_name(dep, lang), because=product_name(sku, lang))))
    else:
        if sku not in sel:
            return state, []
        del sel[sku]
        for gone in dependents_to_drop(set(sel), prods):
            if gone in required:
                continue
            del sel[gone]
            notices.append(Note(key="dep_removed", params={"sku": gone, "because": sku},
                                text=T.tr(T.NOTE["dep_removed"], lang, name=product_name(gone, lang), because=product_name(sku, lang))))
    return state.model_copy(update={"selected": sel}), notices


def make_quote(profile: Profile) -> tuple[QuoteState, Quote]:
    st = initial_state(profile)
    return st, build_quote(st)


def toggled_quote(state: QuoteState, sku: str, on: bool, lang: str = "en") -> tuple[QuoteState, ToggleResult]:
    st, notices = toggle(state, sku, on, lang)
    return st, ToggleResult(quote=build_quote(st, lang), notices=notices)
