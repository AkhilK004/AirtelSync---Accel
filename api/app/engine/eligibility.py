from __future__ import annotations

from app.models.domain import Product
from app.models.engine import Eligibility, Profile

_GSTIN_WHY = {
    "none": "needs an active GSTIN",
    "applied": "needs an active GSTIN (yours is still being applied for)",
    "inactive": "needs an active GSTIN (the one on record is not active)",
}


def eligible(product: Product, profile: Profile) -> Eligibility:
    """Pure check of catalogue rules. Dependencies are handled in dependencies.py."""
    if profile.city_tier not in product.eligible_city_tiers:
        return Eligibility(ok=False, reason_code="CITY_TIER",
                           reason_text=f"{product.name} is not sold in tier-{profile.city_tier} cities yet.")
    if profile.employees < product.min_employees:
        return Eligibility(ok=False, reason_code="SIZE_TOO_SMALL",
                           reason_text=f"{product.name} is for businesses with {product.min_employees}+ people.")
    if profile.locations < product.min_sites:
        return Eligibility(ok=False, reason_code="TOO_FEW_SITES",
                           reason_text=f"{product.name} is for businesses with {product.min_sites}+ locations.")
    if product.requires_gstin and profile.gstin_status != "active":
        return Eligibility(ok=False, reason_code="GSTIN_REQUIRED",
                           reason_text=f"{product.name} {_GSTIN_WHY[profile.gstin_status]}.")
    return Eligibility(ok=True)
