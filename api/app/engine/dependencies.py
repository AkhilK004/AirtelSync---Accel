from __future__ import annotations

from app.engine.eligibility import eligible
from app.engine.money import midpoint_rupee_paise
from app.models.domain import Product
from app.models.engine import Profile


def unmet(product: Product, selected: set[str]) -> bool:
    """requires_one_of is OR: satisfied if any listed SKU is selected."""
    return bool(product.requires_one_of) and not (set(product.requires_one_of) & selected)


def pick_dependency(product: Product, profile: Profile, products: dict[str, Product], blocked: frozenset[str] = frozenset()) -> str | None:
    """Cheapest eligible SKU (midpoint price, then sku) that satisfies product.requires_one_of."""
    opts = [products[s] for s in product.requires_one_of if s in products and s not in blocked and eligible(products[s], profile).ok]
    if not opts:
        return None
    return min(opts, key=lambda p: (midpoint_rupee_paise(p.monthly_price_min_paise, p.monthly_price_max_paise), p.sku)).sku


def dependents_to_drop(selected: set[str], products: dict[str, Product]) -> list[str]:
    """SKUs whose dependency is no longer met (fixpoint, deterministic order)."""
    gone: list[str] = []
    cur = set(selected)
    changed = True
    while changed:
        changed = False
        for sku in sorted(cur):
            if unmet(products[sku], cur):
                cur.discard(sku)
                gone.append(sku)
                changed = True
    return gone
