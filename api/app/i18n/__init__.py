"""Server-side user-visible strings (PLAN 6.5). Keys come from CheckResult.message_key / fix_key."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.models.kyc import CheckResult

_DIR = Path(__file__).parent


@lru_cache(maxsize=4)
def catalog(lang: str) -> dict:
    p = _DIR / f"{lang if lang in ('en', 'hi', 'mr') else 'en'}.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _fmt(tpl: str, params: dict) -> str:
    try:
        return tpl.format(**params)
    except (KeyError, IndexError):
        return tpl


def render_check(c: CheckResult, lang: str) -> dict:
    cat, en = catalog(lang), catalog("en")
    params = dict(c.params)
    if "slot" in params:
        params["doc"] = cat["doc"].get(params["slot"], params["slot"])
    if "expected" in params:
        params["expected"] = cat["doc"].get(params["expected"], params["expected"])
    if c.slot and "doc" not in params:
        params["doc"] = cat["doc"].get(c.slot, c.slot)
    msg = cat["msg"].get(c.message_key) or en["msg"].get(c.message_key, c.message_key)
    fix = (cat["fix"].get(c.fix_key) or en["fix"].get(c.fix_key, c.fix_key)) if c.fix_key else None
    label = cat["code"].get(c.code, c.code)
    if c.slot and c.code in ("IMG_QUALITY", "DOC_TYPE", "DATE_LOGIC", "UDYAM_FORMAT", "ID_FORMAT"):
        label += f" · {cat['doc'].get(c.slot, c.slot)}"  # the same check runs on several documents
    return {"code": c.code, "status": c.status, "label": label, "message": _fmt(msg, params),
            "fix": _fmt(fix, params) if fix else None, "slot": c.slot}


def render_decision(status: str, lang: str, hours: int | None = None) -> str:
    return _fmt(catalog(lang)["decision"][status], {"hours": hours or 24})
