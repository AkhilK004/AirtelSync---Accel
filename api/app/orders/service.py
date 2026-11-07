"""Orders: creation, transitions, per-line fulfilment, ETAs, simulated notifications, tracker view."""
from __future__ import annotations

import hashlib
from datetime import date, timedelta
from functools import lru_cache

import yaml

from app import clock
from app.advisor.slots import product_name
from app.analytics.events import log_event
from app.config import API_ROOT, MAX_SLOT_DAYS_AHEAD, SLOT_WINDOWS
from app.data.loaders import get_data
from app.engine.pricing import new_id
from app.errors import ApiError
from app.i18n import catalog
from app.orders import state as S
from app.repo import get_repo

CALLBACK_HOURS = 4
TECHNICIANS = ("Ramesh K.", "Sunita P.", "Imran S.", "Deepak M.")  # MOCK names for the demo
KYC_REVIEW_HOURS = 24
SLA_KYC_DAYS = 1          # documents are checked within a day of upload (review queue: KYC_REVIEW_HOURS)
SLA_SCHEDULE_DAYS = 1     # install scheduled the day after KYC passes
KYC_FAMILY = {S.PLACED, S.KYC_PENDING, S.KYC_ACTION_REQUIRED, S.KYC_REVIEW}
# notification channel per event: critical ones go by SMS, the rest by WhatsApp
SMS_KEYS = {"kyc_action_required", "cancelled", "on_hold"}


@lru_cache(maxsize=1)
def _instant_digital() -> frozenset[str]:
    with open(API_ROOT / "config" / "fulfilment.yaml", encoding="utf-8") as f:
        return frozenset(yaml.safe_load(f)["instant_digital"])


def mode_of(sku: str) -> str:
    return "digital" if sku in _instant_digital() else "physical"


def _repo():
    return get_repo()


def load(order_id: str) -> dict:
    o = _repo().get("orders", order_id)
    if not o:
        raise ApiError(404, "ORDER_NOT_FOUND", "order.not_found")
    return o


def save(o: dict) -> None:
    _repo().put("orders", o["id"], o)


# ------------------------------------------------------------------ creation
def new_lines(quote_snapshot: dict) -> list[dict]:
    return [{"sku": l["sku"], "qty": l["qty"], "mode": mode_of(l["sku"]), "status": S.L_PENDING, "activated_at": None} for l in quote_snapshot["lines"]]


def init_order(o: dict, quote_snapshot: dict) -> dict:
    """Adds fulfilment structure to a freshly created order document (called by checkout)."""
    o.update({"lines": new_lines(quote_snapshot), "events": [], "tech": None, "held_from": None, "history": [S.PLACED]})
    _event(o, S.PLACED, "order_placed")
    return o


# ------------------------------------------------------------------ events / notifications
def _event(o: dict, state: str, key: str, line_sku: str | None = None, **params) -> None:
    o["events"].append({"ts": clock.now_iso(), "state": state, "line_sku": line_sku, "message_key": key, "params": params,
                        "channel": "sms" if key in SMS_KEYS else "whatsapp"})


def _line_active(o: dict, line: dict) -> None:
    line["status"], line["activated_at"] = S.L_ACTIVE, clock.now_iso()
    _event(o, o["state"], "line_activated", line["sku"])


# ------------------------------------------------------------------ transitions
def transition(o: dict, dst: str, **extra) -> dict:
    """The only place that changes order state. Raises IllegalTransition on a bad move; applies side effects."""
    src = o["state"]
    if dst == S.ON_HOLD:
        o["held_from"] = src
    S.check(src, dst)
    if src == S.ON_HOLD and dst != o.get("held_from"):
        raise S.IllegalTransition(src, dst)  # a held order can only resume where it was held (or be cancelled)
    o["state"] = dst
    o["history"].append(dst)
    o.update(extra)
    key = {S.KYC_PENDING: "kyc_pending", S.KYC_ACTION_REQUIRED: "kyc_action_required", S.KYC_REVIEW: "kyc_review", S.KYC_VERIFIED: "kyc_verified",
           S.INSTALL_SCHEDULED: "install_scheduled", S.TECHNICIAN_ASSIGNED: "technician_assigned", S.INSTALLED: "installed",
           S.ACTIVATED: "activated", S.ON_HOLD: "on_hold", S.CANCELLED: "cancelled"}[dst]
    if src == S.ON_HOLD:
        key = "resumed"
    params: dict = {}
    if dst in (S.INSTALL_SCHEDULED, S.TECHNICIAN_ASSIGNED):
        params = {"date": o["slot"]["date"], "window": o["slot"]["window"]}
    if dst == S.TECHNICIAN_ASSIGNED:
        o["tech"] = TECHNICIANS[int(hashlib.sha256(o["id"].encode()).hexdigest(), 16) % len(TECHNICIANS)]
        params["tech"] = o["tech"]
    if dst == S.KYC_REVIEW:
        params = {"hours": KYC_REVIEW_HOURS}
    if dst == S.ACTIVATED:  # physical lines go live first, then the order-level "all set" message comes last
        _lines_follow(o, dst)
    _event(o, dst, key, **params)
    if dst != S.ACTIVATED:
        _lines_follow(o, dst)
    if dst == S.KYC_VERIFIED:
        _on_kyc_verified(o)
    save(o)
    log_event("order_state_changed", o["id"], {"state": o["state"]})
    return o


def _lines_follow(o: dict, state: str) -> None:
    step = {S.INSTALL_SCHEDULED: S.L_SCHEDULED, S.TECHNICIAN_ASSIGNED: S.L_TECH, S.INSTALLED: S.L_INSTALLED}.get(state)
    for line in o["lines"]:
        if line["mode"] == "physical" and line["status"] != S.L_ACTIVE:
            if step:
                line["status"] = step
            elif state == S.ACTIVATED:
                _line_active(o, line)


def _on_kyc_verified(o: dict) -> None:
    """Digital products go live now; physical ones get their install scheduled. All-digital orders are done at once."""
    for line in o["lines"]:
        if line["mode"] == "digital" and line["status"] != S.L_ACTIVE:
            _line_active(o, line)
    if any(l["mode"] == "physical" for l in o["lines"]):
        _auto(o, S.INSTALL_SCHEDULED)
    else:
        _auto(o, S.ACTIVATED)


def _auto(o: dict, dst: str) -> None:
    """Internal follow-up transition (no recursion into KYC side effects)."""
    S.check(o["state"], dst)
    o["state"] = dst
    o["history"].append(dst)
    key = "install_scheduled" if dst == S.INSTALL_SCHEDULED else "activated"
    if dst == S.ACTIVATED:
        _lines_follow(o, dst)
    _event(o, dst, key, **({"date": o["slot"]["date"], "window": o["slot"]["window"]} if dst == S.INSTALL_SCHEDULED else {}))
    if dst != S.ACTIVATED:
        _lines_follow(o, dst)


def advance(order_id: str) -> dict:
    """Demo/ops: move the order one step forward."""
    o = load(order_id)
    if o["state"] == S.ON_HOLD:
        return transition(o, o["held_from"])
    dst = S.ADVANCE.get(o["state"])
    if dst is None:
        raise ApiError(409, "ORDER_FINAL", "order.final", {"state": o["state"]})
    return transition(o, dst)


def hold(order_id: str) -> dict:
    return transition(load(order_id), S.ON_HOLD)


def cancel(order_id: str, reason: str = "cancelled") -> dict:
    return transition(load(order_id), S.CANCELLED, cancel_reason=reason)


def kyc_result(o: dict, dst: str, **extra) -> None:
    """Called by the KYC service. Re-evaluations after the order left the KYC family are ignored."""
    if o["state"] not in KYC_FAMILY and not (o["state"] == S.ON_HOLD and dst == S.CANCELLED):
        return
    if o["state"] == dst:
        o.update(extra)
        save(o)
        return
    if o["state"] == S.PLACED and dst != S.KYC_PENDING:
        transition(o, S.KYC_PENDING)
    transition(o, dst, **extra)


# ------------------------------------------------------------------ slot / callback
def _check_slot(d: date, window: str) -> None:
    t = clock.today()
    if window not in SLOT_WINDOWS:
        raise ApiError(422, "SLOT_INVALID", "checkout.slot_invalid")
    if not (t + timedelta(days=1) <= d <= t + timedelta(days=MAX_SLOT_DAYS_AHEAD)):
        raise ApiError(422, "SLOT_DATE_INVALID", "checkout.slot_date_invalid", {"max_days": MAX_SLOT_DAYS_AHEAD})


def reschedule(o: dict, d: date, window: str) -> dict:
    if o["state"] in (S.INSTALLED, S.ACTIVATED, S.CANCELLED):
        raise ApiError(409, "RESCHEDULE_NOT_ALLOWED", "order.reschedule_not_allowed", {"state": o["state"]})
    _check_slot(d, window)
    o["slot"] = {"date": d.isoformat(), "window": window}
    _event(o, o["state"], "rescheduled", date=d.isoformat(), window=window)
    if o["state"] == S.TECHNICIAN_ASSIGNED:  # technician must be re-assigned for the new slot
        o["tech"] = None
        S.check(S.TECHNICIAN_ASSIGNED, S.INSTALL_SCHEDULED)
        o["state"] = S.INSTALL_SCHEDULED
        o["history"].append(S.INSTALL_SCHEDULED)
        _lines_follow(o, S.INSTALL_SCHEDULED)
    save(o)
    return o


def request_callback(o: dict) -> dict:
    _event(o, o["state"], "callback_requested", hours=CALLBACK_HOURS)
    lid = new_id()
    _repo().put("leads", lid, {
        "id": lid, "created_at": clock.now_iso(), "session_id": None, "profile": {"business_name": o.get("business_name")}, "segment": None,
        "stage_reached": "order", "reason": "callback_requested", "quote_id": o.get("quote_id"), "order_id": o["id"], "score": None,
        "score_reasons": [], "route_to": "telesales", "partner_code": None, "status": "new"})
    save(o)
    return {"lead_id": lid, "callback_hours": CALLBACK_HOURS}


# ------------------------------------------------------------------ ETAs
def etas(o: dict) -> dict[str, str | None]:
    """Date per tracker step. Done steps keep their real date; the rest are estimated from SLA and the customer's slot."""
    prods = get_data().products
    physical = [prods[l["sku"]] for l in o["lines"] if l["mode"] == "physical"]
    placed = date.fromisoformat(o["created_at"][:10])
    done = {}
    for e in o["events"]:
        done.setdefault(e["state"], e["ts"][:10])
    kyc = date.fromisoformat(done[S.KYC_VERIFIED]) if S.KYC_VERIFIED in done else placed + timedelta(days=SLA_KYC_DAYS)
    slot = date.fromisoformat(o["slot"]["date"])
    install_days = max((p.install_days for p in physical), default=0)
    sched = kyc + timedelta(days=SLA_SCHEDULE_DAYS)
    installed = max(slot, kyc + timedelta(days=install_days))
    out: dict[str, str | None] = {S.PLACED: placed.isoformat(), S.KYC_VERIFIED: kyc.isoformat()}
    if physical:
        out.update({S.INSTALL_SCHEDULED: sched.isoformat(), S.TECHNICIAN_ASSIGNED: (installed - timedelta(days=1)).isoformat(),
                    S.INSTALLED: installed.isoformat(), S.ACTIVATED: installed.isoformat()})
    else:
        out[S.ACTIVATED] = kyc.isoformat()
    for st, d in done.items():
        if st in out:
            out[st] = d
    return out


# ------------------------------------------------------------------ view
def check_access(o: dict, phone_last4: str | None) -> None:
    if not phone_last4 or phone_last4 != o.get("phone_last4"):
        raise ApiError(403, "ORDER_ACCESS", "order.access_denied")


def _fmt(tpl: str, params: dict) -> str:
    try:
        return tpl.format(**params)
    except (KeyError, IndexError):
        return tpl


def render_event(e: dict, lang: str) -> str:
    cat = catalog(lang)["order"]
    p = dict(e["params"])
    if e["line_sku"]:
        p["name"] = product_name(e["line_sku"], lang)
    if "window" in p:
        p["window"] = cat["window"].get(p["window"], p["window"])
    if "date" in p:
        d = date.fromisoformat(p["date"])
        p["date"] = f"{d.day} {cat['months'][d.month - 1]}"
    return _fmt(cat["msg"].get(e["message_key"]) or catalog("en")["order"]["msg"].get(e["message_key"], e["message_key"]), p)


def view(o: dict, lang: str) -> dict:
    cat = catalog(lang)["order"]
    et = etas(o)
    all_digital = all(l["mode"] == "digital" for l in o["lines"])
    flow = [s for s in S.MAIN_FLOW if not (all_digital and s in (S.INSTALL_SCHEDULED, S.TECHNICIAN_ASSIGNED, S.INSTALLED))]
    eff = o["state"]
    if eff == S.ON_HOLD:
        eff = o.get("held_from") or S.PLACED
    elif eff == S.CANCELLED:
        eff = next((h for h in reversed(o["history"]) if h in flow), S.PLACED)
    reached = flow.index(eff) if eff in flow else 0  # KYC family states (pending / action / review) sit at "placed"
    open_order = o["state"] not in (S.CANCELLED, S.ACTIVATED)
    steps = [{"key": s, "label": cat["step"][s], "status": "done" if i <= reached else ("current" if i == reached + 1 and open_order else "upcoming"),
              "eta": et.get(s)} for i, s in enumerate(flow)]
    prods = get_data().products
    lines = [{"sku": l["sku"], "name": product_name(l["sku"], lang), "qty": l["qty"], "mode": l["mode"], "status": l["status"],
              "status_label": cat["line"]["AWAITING_KYC" if l["status"] == S.L_PENDING else l["status"]],
              "eta": None if l["status"] == S.L_ACTIVE else (et.get(S.INSTALLED) if l["mode"] == "physical" else et.get(S.KYC_VERIFIED)),
              "install_days": prods[l["sku"]].install_days if l["mode"] == "physical" else 0} for l in o["lines"]]
    side = o["state"] if o["state"] in (S.KYC_ACTION_REQUIRED, S.KYC_REVIEW, S.ON_HOLD, S.CANCELLED) else None
    q = o["quote_snapshot"]
    messages = [{"ts": e["ts"], "channel": e["channel"], "text": render_event(e, lang)} for e in o["events"]]
    return {
        "id": o["id"], "state": o["state"], "state_label": cat["state"].get(o["state"], o["state"]), "side_state": side,
        "side_message": cat["side"].get(side) if side else None, "business_name": o.get("business_name"),
        "slot": {**o["slot"], "window_label": cat["window"][o["slot"]["window"]]}, "tech": o.get("tech"),
        "steps": steps, "lines": lines, "eta_activation": et.get(S.ACTIVATED),
        "events": [{"ts": e["ts"], "state": e["state"], "text": render_event(e, lang)} for e in o["events"]],
        "messages": list(reversed(messages)), "monthly_total_display": q["monthly_total_display"],
        "one_time_total_display": q["one_time_total_display"] if q["one_time_paise"] else "", "can_reschedule": o["state"] not in (S.INSTALLED, S.ACTIVATED, S.CANCELLED),
        "needs_kyc": o["state"] in (S.PLACED, S.KYC_PENDING, S.KYC_ACTION_REQUIRED), "callback_hours": CALLBACK_HOURS,
        "payment_mode": o.get("payment_mode"),
    }
