from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.orders import service
from app.orders import state as S
from app.repo import get_repo

c = TestClient(app)
ADMIN = {"X-Admin-Token": settings.ADMIN_TOKEN}
SLOT = (date.fromisoformat(settings.TODAY) + timedelta(days=3)).isoformat()


def order(profile=None, phone="9876543210", lang="en") -> str:
    p = profile or {"business_type": "Dental clinic", "employees": 6, "locations": 1, "city_tier": 1, "gstin_status": "active"}
    q = c.post("/quotes", json=p).json()
    r = c.post("/checkout", json=dict(quote_id=q["id"], phone=phone, otp="123456", business_name="Test Clinic", address="12 Market Road, Mumbai",
                                      slot_date=SLOT, slot_window="morning", payment_mode="pay_on_activation", language=lang))
    assert r.status_code == 200, r.text
    return r.json()["order_id"]


def digital_only_order() -> str:
    """A quote whose lines are all instant-digital: take a clinic quote and drop to digital SKUs via the stored snapshot."""
    oid = order()
    o = get_repo().get("orders", oid)
    o["lines"] = [l for l in o["lines"] if l["mode"] == "digital"]
    get_repo().put("orders", oid, o)
    assert o["lines"], "clinic bundle has digital lines (email P16, security P20)"
    return oid


def adv(oid, n=1):
    for _ in range(n):
        r = c.post(f"/admin/orders/{oid}/advance", headers=ADMIN)
        assert r.status_code == 200, r.text
    return r.json()


def get(oid, last4="3210", lang="en", **kw):
    return c.get(f"/orders/{oid}", params={"phone_last4": last4, "lang": lang, **kw})


# ------------------------------------------------------------------ state machine (pure)
def test_every_listed_transition_is_legal_and_others_raise():
    for src, dsts in S.TRANSITIONS.items():
        for dst in S.TRANSITIONS:
            if dst in dsts:
                S.check(src, dst)
            else:
                with pytest.raises(S.IllegalTransition):
                    S.check(src, dst)


def test_terminal_states_have_no_exit_and_no_self_loop():
    for t in S.TERMINAL:
        assert not S.TRANSITIONS[t]
    with pytest.raises(S.IllegalTransition):
        S.check(S.PLACED, S.PLACED)


def test_cannot_skip_steps():
    for src, dst in [(S.PLACED, S.INSTALLED), (S.KYC_VERIFIED, S.INSTALLED), (S.INSTALL_SCHEDULED, S.ACTIVATED), (S.ACTIVATED, S.INSTALLED), (S.CANCELLED, S.PLACED)]:
        with pytest.raises(S.IllegalTransition):
            S.check(src, dst)


# ------------------------------------------------------------------ fulfilment modes
def test_digital_vs_physical_modes():
    assert service.mode_of("P16") == "digital" and service.mode_of("P20") == "digital" and service.mode_of("P15") == "digital"
    assert all(service.mode_of(s) == "physical" for s in ("P01", "P04", "P05", "P23", "P19", "P07"))


def test_new_order_structure():
    oid = order()
    o = get_repo().get("orders", oid)
    assert o["state"] == "PLACED" and o["history"] == ["PLACED"] and o["events"][0]["message_key"] == "order_placed"
    modes = {l["sku"]: l["mode"] for l in o["lines"]}
    assert modes["P16"] == "digital" and modes["P20"] == "digital" and modes["P01"] == "physical" and all(l["status"] == "PENDING" for l in o["lines"])


# ------------------------------------------------------------------ full happy path with per-line behaviour
def test_full_lifecycle_digital_live_first_physical_follow_steps():
    oid = order()
    v = adv(oid)                       # PLACED -> KYC_PENDING
    assert v["state"] == "KYC_PENDING" and all(l["status"] == "PENDING" for l in v["lines"])
    v = adv(oid)                       # KYC_PENDING -> KYC_VERIFIED -> auto INSTALL_SCHEDULED
    assert v["state"] == "INSTALL_SCHEDULED"
    by = {l["sku"]: l for l in v["lines"]}
    assert by["P16"]["status"] == "ACTIVATED" and by["P20"]["status"] == "ACTIVATED"        # digital: live immediately
    assert by["P01"]["status"] == "SCHEDULED" and by["P07"]["status"] == "SCHEDULED"          # physical: waiting for install
    assert any("is now live" in m["text"] for m in v["messages"])
    v = adv(oid)
    assert v["state"] == "TECHNICIAN_ASSIGNED" and v["tech"] and all(l["status"] == "TECHNICIAN_ASSIGNED" for l in v["lines"] if l["mode"] == "physical")
    v = adv(oid)
    assert v["state"] == "INSTALLED" and all(l["status"] == "INSTALLED" for l in v["lines"] if l["mode"] == "physical")
    v = adv(oid)
    assert v["state"] == "ACTIVATED" and all(l["status"] == "ACTIVATED" for l in v["lines"])
    assert c.post(f"/admin/orders/{oid}/advance", headers=ADMIN).status_code == 409           # nothing after ACTIVATED


def test_all_digital_order_activates_at_verification():
    oid = digital_only_order()
    adv(oid)
    v = adv(oid)
    assert v["state"] == "ACTIVATED" and all(l["status"] == "ACTIVATED" for l in v["lines"])
    assert [s["key"] for s in v["steps"]] == ["PLACED", "KYC_VERIFIED", "ACTIVATED"] and all(s["status"] == "done" for s in v["steps"])


def test_stepper_current_step_and_etas():
    oid = order()
    v = get(oid).json()
    assert [s["status"] for s in v["steps"]] == ["done", "current", "upcoming", "upcoming", "upcoming", "upcoming"]
    assert all(s["eta"] for s in v["steps"])
    etas = {s["key"]: s["eta"] for s in v["steps"]}
    assert etas["INSTALL_SCHEDULED"] <= etas["TECHNICIAN_ASSIGNED"] <= etas["INSTALLED"] and etas["INSTALLED"] >= SLOT  # install not before the chosen slot
    adv(oid, 3)
    v = get(oid).json()
    assert [s["status"] for s in v["steps"]][:4] == ["done", "done", "done", "done"] and v["steps"][4]["status"] == "current"
    assert v["slot"]["date"] == SLOT and "morning" in v["slot"]["window_label"]


# ------------------------------------------------------------------ side states
def test_hold_and_resume_returns_to_held_state_and_cannot_jump():
    oid = order()
    adv(oid, 3)  # INSTALL_SCHEDULED -> TECHNICIAN_ASSIGNED
    assert c.post(f"/admin/orders/{oid}/hold", headers=ADMIN).json()["state"] == "ON_HOLD"
    v = get(oid).json()
    assert v["side_state"] == "ON_HOLD" and v["side_message"]
    o = get_repo().get("orders", oid)
    with pytest.raises(S.IllegalTransition):
        service.transition(o, S.INSTALLED)   # a held order resumes where it was held, no skipping
    assert adv(oid)["state"] == "TECHNICIAN_ASSIGNED"  # advance on a held order = resume
    assert any("moving again" in m["text"] for m in get(oid).json()["messages"])


def test_cancel_is_terminal():
    oid = order()
    r = c.post(f"/admin/orders/{oid}/cancel", headers=ADMIN).json()
    assert r["state"] == "CANCELLED" and r["side_state"] == "CANCELLED" and not r["can_reschedule"]
    assert c.post(f"/admin/orders/{oid}/advance", headers=ADMIN).status_code == 409
    assert c.post(f"/admin/orders/{oid}/hold", headers=ADMIN).json()["error"]["code"] == "ILLEGAL_TRANSITION"


def test_kyc_family_moves_both_ways():
    o = get_repo().get("orders", order())
    for dst in (S.KYC_PENDING, S.KYC_ACTION_REQUIRED, S.KYC_PENDING, S.KYC_REVIEW, S.KYC_ACTION_REQUIRED):
        o = service.transition(o, dst)
    assert o["state"] == S.KYC_ACTION_REQUIRED
    assert get(o["id"]).json()["needs_kyc"] is True


# ------------------------------------------------------------------ reschedule / callback / access
def test_reschedule_before_install_and_reassigns_technician():
    oid = order()
    adv(oid, 3)
    assert get(oid).json()["tech"]
    new = (date.fromisoformat(settings.TODAY) + timedelta(days=6)).isoformat()
    r = c.post(f"/orders/{oid}/reschedule", params={"lang": "en"}, json={"phone_last4": "3210", "slot_date": new, "slot_window": "evening"})
    v = r.json()
    assert r.status_code == 200 and v["slot"]["date"] == new and v["state"] == "INSTALL_SCHEDULED" and v["tech"] is None
    assert any("Visit moved" in m["text"] for m in v["messages"])
    bad = c.post(f"/orders/{oid}/reschedule", json={"phone_last4": "3210", "slot_date": settings.TODAY, "slot_window": "evening"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "SLOT_DATE_INVALID"
    adv(oid, 2)  # -> INSTALLED
    late = c.post(f"/orders/{oid}/reschedule", json={"phone_last4": "3210", "slot_date": new, "slot_window": "morning"})
    assert late.status_code == 409 and late.json()["error"]["code"] == "RESCHEDULE_NOT_ALLOWED"


def test_callback_creates_lead_and_message():
    oid = order()
    r = c.post(f"/orders/{oid}/callback", json={"phone_last4": "3210"}).json()
    assert r["callback_hours"] == 4
    assert any(l["order_id"] == oid and l["reason"] == "callback_requested" for l in get_repo().list("leads"))
    assert "Callback requested" in get(oid).json()["messages"][0]["text"]


def test_access_check_and_pii():
    oid = order()
    assert get(oid, last4="0000").status_code == 403 and get(oid, last4="0000").json()["error"]["code"] == "ORDER_ACCESS"
    assert c.get(f"/orders/{oid}").status_code == 403
    assert c.get("/orders/nope", params={"phone_last4": "3210"}).status_code == 404
    assert "9876543210" not in str(get(oid).json())


def test_admin_requires_token():
    oid = order()
    assert c.post(f"/admin/orders/{oid}/advance").status_code == 401
    assert c.post(f"/admin/orders/{oid}/advance", headers={"X-Admin-Token": "wrong"}).status_code == 401


def test_admin_actions_are_audited():
    oid = order()
    adv(oid)
    assert any(a["action"] == "order_advance" and a["order_id"] == oid for a in get_repo().list("audit_log"))


# ------------------------------------------------------------------ messages, languages, analytics
def test_notifications_localised_and_channels():
    oid = order(lang="hi")
    adv(oid, 2)
    hi = get(oid, lang="hi").json()
    assert any("ऀ" <= ch <= "ॿ" for ch in hi["messages"][0]["text"])
    assert {m["channel"] for m in hi["messages"]} == {"whatsapp"}
    assert hi["steps"][0]["label"] == "ऑर्डर दिया गया" and hi["lines"][0]["name"] == "बिज़ फाइबर 100"
    mr = get(oid, lang="mr").json()
    assert mr["state_label"] == "इन्स्टॉलेशन ठरले"
    c.post(f"/admin/orders/{order()}/cancel", headers=ADMIN)
    sms = [e for o in get_repo().list("orders") for e in o["events"] if e["message_key"] == "cancelled"]
    assert sms and sms[0]["channel"] == "sms"  # critical events go by SMS


def test_prices_frozen_and_tracker_viewed_counted_only_for_page_loads():
    oid = order()
    first = get(oid).json()["monthly_total_display"]
    q = c.get(f"/quotes/{get_repo().get('orders', oid)['quote_id']}").json()
    c.post(f"/quotes/{q['id']}/toggle", json={"sku": "P17", "on": True})  # later quote edits do not change the order
    assert get(oid).json()["monthly_total_display"] == first
    before = sum(1 for e in get_repo().list("events") if e["name"] == "tracker_viewed" and e["ref_id"] == oid)
    get(oid); get(oid); get(oid, track="true")
    assert sum(1 for e in get_repo().list("events") if e["name"] == "tracker_viewed" and e["ref_id"] == oid) == before + 1


def test_dates_in_messages_are_human_readable():
    oid = order()
    adv(oid, 2)
    texts = " ".join(m["text"] for m in get(oid).json()["messages"])
    assert "18 Jul" in texts and SLOT not in texts
    assert "18 जुलै" in " ".join(m["text"] for m in get(oid, lang="mr").json()["messages"])


def test_events_timeline_is_chronological_and_complete():
    oid = order()
    adv(oid, 5)
    v = get(oid).json()
    texts = [e["text"] for e in v["events"]]
    assert texts[0].startswith("Order placed") and texts[-1].startswith("All set")
    assert [e["ts"] for e in v["events"]] == sorted(e["ts"] for e in v["events"])
    assert v["eta_activation"]


def test_kyc_service_drives_the_state_machine():
    # approved applicant: KYC_VERIFIED then auto-scheduled; rejected applicant cancels the order; re-evaluation after leaving KYC is ignored
    from tests.test_kyc_api import run
    oid, r = run("K03")
    o = get_repo().get("orders", oid)
    assert r["decision"]["status"] == "APPROVED" and o["state"] == "INSTALL_SCHEDULED" and o["history"][:3] == ["PLACED", "KYC_PENDING", "KYC_VERIFIED"]
    assert c.post(f"/kyc/{oid}/evaluate").status_code == 200
    assert get_repo().get("orders", oid)["state"] == "INSTALL_SCHEDULED"
    oid2, r2 = run("K01")
    assert get_repo().get("orders", oid2)["state"] == "CANCELLED"
    oid3, r3 = run("K11")
    assert get_repo().get("orders", oid3)["state"] == "KYC_ACTION_REQUIRED"
