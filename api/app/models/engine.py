from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class Segment(StrEnum):
    MICRO_RETAIL = "micro_retail"
    PROFESSIONAL = "professional_office"
    MULTI_SITE = "multi_site"
    MANUFACTURER = "manufacturer"


class Profile(BaseModel):
    business_type: str | None = None
    employees: int = Field(1, ge=1)
    locations: int = Field(1, ge=1)
    city_tier: int = Field(2, ge=1)
    gstin_status: Literal["none", "active", "inactive", "applied"] = "none"
    fibre_available: bool = True
    wants: list[str] = []  # need names the owner asked for, e.g. ["cctv", "failover"]


class Eligibility(BaseModel):
    ok: bool
    reason_code: str | None = None  # CITY_TIER | SIZE_TOO_SMALL | TOO_FEW_SITES | GSTIN_REQUIRED | DEPENDENCY_INELIGIBLE
    reason_text: str | None = None


class Exclusion(BaseModel):
    need: str
    sku: str | None = None
    reason_code: str
    reason_text: str


class Note(BaseModel):
    key: str
    params: dict = {}
    text: str  # English default; i18n by key later


class Line(BaseModel):
    sku: str
    need: str
    qty: int
    required: bool
    why: list[str]
    via_dependency: bool = False


class Recommendation(BaseModel):
    segment: Segment
    bundle_name: dict[str, str]
    lines: list[Line]          # core (required) + pulled-in dependencies
    addons: list[Line]         # optional, default qty; `default_on` marks pre-selected
    default_on: list[str] = []
    exclusions: list[Exclusion] = []
    unmet_needs: list[str] = []
    assumptions: list[Note] = []
    assisted: bool = False
    assisted_reason: str | None = None


class QuoteLine(BaseModel):
    sku: str
    name: str
    category: str
    description: str
    unit: str
    need: str
    qty: int
    required: bool
    why: list[str]
    unit_price_paise: int
    unit_price_display: str
    line_monthly_paise: int
    line_monthly_display: str
    setup_paise: int
    setup_display: str
    contract_months: int
    reason: str = ""  # one plain-language line, in the requested language


class AddonOption(BaseModel):
    sku: str
    name: str
    need: str
    qty: int
    on: bool
    monthly_paise: int
    monthly_display: str
    setup_display: str
    can_toggle: bool
    blocked_reason: str | None = None
    reason: str = ""


class Quote(BaseModel):
    id: str
    segment: Segment
    bundle_name: dict[str, str]
    bundle_title: str = ""
    lines: list[QuoteLine]
    addons: list[AddonOption]
    monthly_subtotal_paise: int
    gst_paise: int
    monthly_total_paise: int
    one_time_paise: int
    one_time_gst_paise: int
    one_time_total_paise: int
    monthly_subtotal_display: str
    gst_display: str
    monthly_total_display: str
    one_time_display: str
    one_time_gst_display: str
    one_time_total_display: str
    contract_months: int
    price_rule: str
    gst_rate_pct: int
    assumptions: list[Note]
    exclusions: list[Exclusion]
    assisted: bool
    assisted_reason: str | None = None


class QuoteState(BaseModel):
    """Persisted state; Quote is always recomputed from it."""
    id: str
    profile: Profile
    recommendation: Recommendation
    selected: dict[str, int]  # sku -> qty


class ToggleResult(BaseModel):
    quote: Quote
    notices: list[Note]
