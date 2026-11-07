"""Scenario runner shared by tests (in-process, FakeLLM) and scripts/run_scenarios.py (in-process or live URL)."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from app.advisor.slots import Slots, to_profile
from app.data.loaders import get_data
from app.engine.eligibility import eligible
from app.engine.pricing import build_quote, initial_state
from app.models.engine import QuoteState

SCENARIO_FILE = Path(__file__).resolve().parents[2] / "tests" / "scenarios" / "advisor_scenarios.yaml"
_DEV = re.compile(r"[ऀ-ॿ]")


def load_scenarios() -> list[dict]:
    with open(SCENARIO_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


class LocalClient:
    def __init__(self) -> None:
        from fastapi.testclient import TestClient
        from app.main import app
        self.c = TestClient(app)

    def post(self, path: str, json: dict | None = None) -> dict:
        r = self.c.post(path, json=json or {})
        r.raise_for_status()
        return r.json()

    def get(self, path: str) -> dict:
        r = self.c.get(path)
        r.raise_for_status()
        return r.json()


class HttpClient:
    def __init__(self, base_url: str) -> None:
        import httpx
        self.c = httpx.Client(base_url=base_url.rstrip("/"), timeout=60)

    def post(self, path: str, json: dict | None = None) -> dict:
        r = self.c.post(path, json=json or {})
        r.raise_for_status()
        return r.json()

    def get(self, path: str) -> dict:
        r = self.c.get(path)
        r.raise_for_status()
        return r.json()


def _lang_ok(text: str, lang: str) -> bool:
    letters = [ch for ch in text if ch.isalpha()]
    dev = len(_DEV.findall(text))
    if lang == "en":
        return dev <= 5
    return bool(letters) and dev / len(letters) >= 0.3


def run_scenario(client, sc: dict) -> list[str]:
    fails: list[str] = []
    prods = get_data().products
    first = client.post("/advisor/sessions", {})
    sid = first["session_id"]
    replies, first_rec = [], None
    for i, t in enumerate(sc["turns"]):
        r = client.post(f"/advisor/sessions/{sid}/messages", {"text": t})
        replies.append(r)
        if r.get("recommendation") and first_rec is None:
            first_rec = i + 1
    last = replies[-1]
    state = client.get(f"/advisor/sessions/{sid}")

    def need(cond: bool, msg: str) -> None:
        if not cond:
            fails.append(msg)

    need(state["questions_asked"] <= 6, f"questions_asked={state['questions_asked']} > 6")
    qid = last.get("quote_id")
    quote = client.get(f"/quotes/{qid}") if qid else None
    if "segment" in sc:
        need(quote is not None and quote["segment"] == sc["segment"], f"segment {quote and quote['segment']} != {sc['segment']}")
    if quote:
        skus = [l["sku"] for l in quote["lines"]]
        cats = {l["category"] for l in quote["lines"]}
        profile, _ = to_profile(Slots.model_validate(state["slots"]))
        need(all(s in prods for s in skus), "sku not in catalogue")
        for s in skus:
            e = eligible(prods[s], profile)
            need(e.ok, f"{s} ineligible: {e.reason_code}")
            p = prods[s]
            need(not p.requires_one_of or set(p.requires_one_of) & set(skus), f"{s} dependency unmet")
        need(profile.gstin_status == "active" or not any(prods[s].requires_gstin for s in skus), "GSTIN-only product sold without active GSTIN")
        recompute = build_quote(QuoteState.model_validate(initial_state(profile, qid).model_dump()))
        need(recompute.monthly_total_paise == quote["monthly_total_paise"], "quote total != engine recompute")
        for s in sc.get("must_include_skus", []):
            need(s in skus, f"missing {s}")
        for s in sc.get("must_exclude_skus", []):
            need(s not in skus, f"unexpected {s}")
        for c in sc.get("must_include_categories", []):
            need(c in cats, f"missing category {c}")
        for c in sc.get("must_exclude_categories", []):
            need(c not in cats, f"unexpected category {c}")
        if sc.get("quote_unchanged"):
            need(replies[-2]["recommendation"]["monthly_total_paise"] == quote["monthly_total_paise"], "price changed")
        if sc.get("quote_changes"):
            need(replies[-2]["recommendation"]["monthly_total_paise"] != quote["monthly_total_paise"], "price did not update")
            need(replies[-2]["quote_id"] == qid, "quote id changed")
    elif "segment" in sc or sc.get("must_include_skus"):
        fails.append("no quote produced")
    if "recommend_within" in sc:
        need(first_rec is not None and first_rec <= sc["recommend_within"], f"recommendation after {first_rec} replies > {sc['recommend_within']}")
    if "handoff" in sc:
        need(any(r["handoff"] for r in replies) == sc["handoff"], f"handoff expected {sc['handoff']}")
    if "language" in sc:
        need(_lang_ok(last["message"], sc["language"]) and last["language"] == sc["language"], f"reply language != {sc['language']} (got {last['language']})")
    elif quote:
        need(_lang_ok(last["message"], last["language"]), "reply not in session language")
    if sc.get("budget_gap"):
        b = last.get("budget")
        need(bool(b and b["gap_display"]), "budget gap not reported")
    for k in sc.get("assumption_keys", []):
        need(k in last["assumptions"], f"assumption {k} missing")
    for idx, chk in (sc.get("turn_checks") or {}).items():
        r = replies[int(idx)]
        if "action" in chk:
            need(r["action"] == chk["action"], f"turn {idx} action {r['action']} != {chk['action']}")
        if "contains_any" in chk:
            need(any(w.lower() in r["message"].lower() for w in chk["contains_any"]), f"turn {idx} lacks any of {chk['contains_any']}")
        for w in chk.get("not_contains", []):
            need(w.lower() not in r["message"].lower(), f"turn {idx} contains forbidden '{w}'")
    return fails
