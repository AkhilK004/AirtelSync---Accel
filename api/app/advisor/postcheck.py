"""Code-level guard on LLM replies: nothing in the reply may be absent from FACTS."""
from __future__ import annotations

import json
import re

from app.advisor.slots import all_product_names

_MONEY = re.compile(r"(?:₹|rs\.?|inr)\s*[\d,]+(?:\.\d+)?", re.I)
_PCT = re.compile(r"\d+(?:\.\d+)?\s*%")
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def _norm(tok: str) -> str:
    t = re.sub(r"\s+", "", tok.lower()).replace("rs.", "₹").replace("rs", "₹").replace("inr", "₹")
    return t.rstrip(".")


def violations(reply: str, facts: dict, language: str) -> list[str]:
    facts_txt = json.dumps({k: v for k, v in facts.items() if k != "template_text"}, ensure_ascii=False)
    out: list[str] = []
    allowed_money = {_norm(m) for m in _MONEY.findall(facts_txt)}
    for m in _MONEY.findall(reply):
        if _norm(m) not in allowed_money:
            out.append(f"amount:{m}")
    allowed_pct = {_norm(p) for p in _PCT.findall(facts_txt)}
    for p in _PCT.findall(reply):
        if _norm(p) not in allowed_pct:
            out.append(f"percent:{p}")
    low = reply.lower()
    for sku, names in all_product_names().items():
        for n in names:
            if n.lower() in low and n.lower() not in facts_txt.lower():
                out.append(f"product:{sku}")
    if language in ("hi", "mr") and not _DEVANAGARI.search(reply):
        out.append("language")
    if language == "en" and len(_DEVANAGARI.findall(reply)) > 5:
        out.append("language")
    return out
