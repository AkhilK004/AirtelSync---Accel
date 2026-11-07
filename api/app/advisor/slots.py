"""Slot schema, order, defaults, quick-reply values, city->tier lookup, product display names."""
from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field

from app.config import API_ROOT
from app.data.loaders import get_data
from app.models.engine import Note, Profile

DERIVED = (API_ROOT / ".." / "data" / "derived").resolve()

REQUIRED_ORDER = ["business_type", "employees", "locations", "city", "has_gstin"]  # fixed question order
OPTIONAL_SLOT = "current_tools"  # asked after the recommendation (refinement), never blocks it
LANGS = ("en", "hi", "mr")

# Defaults applied on "don't know" or when the question budget is spent. Each adds a visible assumption.
DEFAULT_EMPLOYEES = 2
DEFAULT_LOCATIONS = 1
DEFAULT_CITY_TIER = 2
DEFAULT_GSTIN = "no"

# need names the owner can ask for (maps to bundle needs in config/bundles.yaml)
WANT_NEEDS = ["cctv", "billing_pos", "failover", "customer_messaging", "guest_wifi", "backup", "static_ip", "business_phone",
              "central_management", "firewall", "toll_free", "website", "machine_monitoring", "fleet_tracking", "leased_line"]
INTENTS = ["answer", "ask_why", "ask_price", "change_answer", "request_human", "off_topic", "smalltalk"]


class Slots(BaseModel):
    business_type: str | None = None
    employees: int | None = None
    locations: int | None = None
    city: str | None = None
    city_tier: int | None = None
    has_gstin: Literal["yes", "no", "applied"] | None = None
    current_tools: list[str] = []
    budget_monthly: int | None = None
    wants: list[str] = []
    fibre_available: bool = True


class SlotUpdate(BaseModel):
    """NLU output. Every field optional; the LLM must never invent values."""
    business_type: str | None = None
    employees: int | None = Field(None, ge=1, le=5000)
    locations: int | None = Field(None, ge=1, le=500)
    city: str | None = None
    has_gstin: Literal["yes", "no", "applied"] | None = None
    current_tools: list[str] = []
    budget_monthly: int | None = Field(None, ge=0)
    wants: list[str] = []
    fibre_available: bool | None = None
    dont_know: list[str] = []
    intent: Literal["answer", "ask_why", "ask_price", "change_answer", "request_human", "off_topic", "smalltalk"] = "answer"
    language: Literal["en", "hi", "mr"] | None = None
    injection_attempt: bool = False
    requested_unavailable_item: str | None = None


def load_json(name: str) -> dict:
    with open(DERIVED / name, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def city_tiers() -> dict[str, int]:
    return load_json("city_tiers.json")


# Devanagari spellings of data cities (so Hindi/Marathi users are understood without an LLM)
CITY_ALIASES = {"पुणे": "Pune", "पुण्यात": "Pune", "पुण्यातील": "Pune", "मुंबई": "Mumbai", "मुंबईत": "Mumbai", "दिल्ली": "Delhi",
                "लखनऊ": "Lucknow", "जयपुर": "Jaipur", "जयपूर": "Jaipur", "नागपूर": "Nagpur", "नागपुर": "Nagpur", "नाशिक": "Nashik",
                "इंदौर": "Indore", "इंदूर": "Indore", "भोपाल": "Bhopal", "पटना": "Patna", "सूरत": "Surat", "अहमदाबाद": "Ahmedabad",
                "चेन्नई": "Chennai", "कोलकाता": "Kolkata", "हैदराबाद": "Hyderabad", "बेंगलुरु": "Bengaluru", "बंगलौर": "Bengaluru",
                "लुधियाना": "Ludhiana", "कोच्ची": "Kochi", "वडोदरा": "Vadodara", "म्हैसूर": "Mysuru", "मैसूर": "Mysuru"}


def resolve_city(city: str | None) -> tuple[str | None, int | None]:
    """Free text city -> (canonical city, tier) using data/derived/city_tiers.json. Unknown -> (text, None)."""
    if not city:
        return None, None
    c = city.strip()
    c = CITY_ALIASES.get(c, c)
    for name, tier in city_tiers().items():
        if name.lower() == c.lower() or (name == "Bengaluru" and c.lower() in ("bangalore", "bengalooru")) or (name == "Mysuru" and c.lower() == "mysore"):
            return name, tier
    return c, None


# ---- product display names
@lru_cache(maxsize=1)
def _i18n() -> dict:
    return load_json("catalogue_i18n.json")


def product_name(sku: str, lang: str) -> str:
    if lang in ("hi", "mr"):
        n = _i18n().get(lang, {}).get(sku)
        if n:
            return n
    return get_data().products[sku].name


def all_product_names() -> dict[str, set[str]]:
    """sku -> every display name in every language (for the NLG post-check)."""
    out: dict[str, set[str]] = {}
    for sku, p in get_data().products.items():
        out[sku] = {p.name} | {_i18n().get(l, {}).get(sku) for l in ("hi", "mr")} - {None}
    return out


def to_profile(s: Slots) -> tuple[Profile, list[Note]]:
    """Slots -> engine Profile. Missing values must already have defaults applied by the caller."""
    status = {"yes": "active", "no": "none", "applied": "applied"}[s.has_gstin or "no"]
    p = Profile(business_type=s.business_type, employees=s.employees or DEFAULT_EMPLOYEES, locations=s.locations or DEFAULT_LOCATIONS,
                city_tier=s.city_tier or DEFAULT_CITY_TIER, gstin_status=status, fibre_available=s.fibre_available,
                wants=[w for w in s.wants if w != "leased_line"])
    return p, []


# ---- chip -> representative value (documented: band midpoint rounded up; "N+" -> N*1.6 employees / N+1 locations)
def band_value(text: str, slot: str) -> int | None:
    t = text.strip().replace("–", "-").replace("—", "-").replace(" ", "")
    m = re.fullmatch(r"(\d+)-(\d+)", t)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return math.ceil((lo + hi) / 2)
    m = re.fullmatch(r"(\d+)\+", t)
    if m:
        n = int(m.group(1))
        return round(n * 1.6) if slot == "employees" else n + 1
    return None
