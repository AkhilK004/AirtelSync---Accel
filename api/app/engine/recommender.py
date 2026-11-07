from __future__ import annotations

import math
from functools import lru_cache

import yaml

from app.config import API_ROOT, ASSISTED_CALLBACK_HOURS
from app.data.loaders import get_data
from app.engine.dependencies import dependents_to_drop, pick_dependency, unmet
from app.engine.eligibility import eligible
from app.engine.segments import classify, is_assisted
from app.models.engine import Exclusion, Line, Note, Profile, Recommendation


@lru_cache(maxsize=1)
def templates() -> dict:
    with open(API_ROOT / "config" / "bundles.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def blocked_skus(profile: Profile) -> frozenset[str]:
    """SKUs unusable at this site: fibre products when fibre is not available (flag lives in bundles.yaml)."""
    if profile.fibre_available:
        return frozenset()
    return frozenset(c["sku"] for t in templates().values() for n in t["needs"] for c in n["candidates"] if c.get("requires_fibre"))


def qty_for(spec: dict, profile: Profile) -> int:
    k = spec["kind"]
    if k == "fixed":
        return int(spec["n"])
    if k == "sites":
        return profile.locations
    if k == "sites_x":
        return profile.locations * int(spec["n"])
    if k == "employees_ratio":
        q = math.ceil(profile.employees * float(spec["ratio"]))
        return max(int(spec["min"]), min(int(spec["max"]), q))
    raise ValueError(k)


def dep_qty(sku: str, profile: Profile) -> int:
    return profile.locations if get_data().products[sku].per_site else 1


def _choose(need: dict, profile: Profile, products):
    """Smallest eligible tier that fits team size; if none fits, the largest eligible."""
    cands = [c for c in need["candidates"] if not (c.get("requires_fibre") and not profile.fibre_available)]
    excl: list[Exclusion] = []
    if not cands:
        return None, excl
    regular_c = [c for c in cands if not c.get("fallback")] or cands
    preferred = next((c for c in regular_c if profile.employees <= c["fits_up_to"]), regular_c[-1])
    pe = eligible(products[preferred["sku"]], profile)
    if not pe.ok:
        excl.append(Exclusion(need=need["need"], sku=preferred["sku"], reason_code=pe.reason_code, reason_text=pe.reason_text))
    ok = [c for c in cands if eligible(products[c["sku"]], profile).ok]
    regular = [c for c in ok if not c.get("fallback")]
    ok = regular or ok
    if not ok:
        return None, excl
    fit = next((c for c in ok if profile.employees <= c["fits_up_to"]), ok[-1])
    return fit["sku"], excl


def recommend(profile: Profile) -> Recommendation:
    products = get_data().products
    assumptions: list[Note] = []
    if profile.city_tier > 2:
        assumptions.append(Note(key="tier_clamped", params={"given": profile.city_tier},
                                text="Only tier-1 and tier-2 cities exist in our coverage data; we treated yours as tier-2."))
        profile = profile.model_copy(update={"city_tier": 2})
    seg, notes = classify(profile)
    assumptions += notes
    tpl = templates()[seg.value]
    exclusions: list[Exclusion] = []
    unmet_needs: list[str] = []
    picks: dict[str, tuple[dict, str]] = {}
    for need in tpl["needs"]:
        sku, ex = _choose(need, profile, products)
        exclusions += ex
        if sku:
            picks[need["need"]] = (need, sku)
        elif need["required"]:
            unmet_needs.append(need["need"])
        elif not ex:
            exclusions.append(Exclusion(need=need["need"], sku=None, reason_code="NOT_AVAILABLE",
                                        reason_text="Not available for your business."))

    # dependency closure (OR semantics): add cheapest eligible provider, else drop dependent
    selected = {sku for _, sku in picks.values()}
    pulled: dict[str, str] = {}
    for need_name in list(picks):
        need, sku = picks[need_name]
        p = products[sku]
        # closure only for core lines and pre-selected add-ons; other add-ons resolve at toggle time
        if not (need["required"] or need.get("default_on") or need_name in profile.wants):
            continue
        if unmet(p, selected):
            dep = pick_dependency(p, profile, products, blocked_skus(profile))
            if dep:
                selected.add(dep)
                pulled[dep] = sku
            else:
                selected.discard(sku)
                del picks[need_name]
                exclusions.append(Exclusion(need=need_name, sku=sku, reason_code="DEPENDENCY_INELIGIBLE",
                                            reason_text=f"{p.name} needs an internet link that is not available for you."))
                if need["required"]:
                    unmet_needs.append(need_name)
    core_names = {n for n, (nd, _) in picks.items() if nd["required"] or nd.get("default_on") or n in profile.wants}
    for gone in dependents_to_drop(selected, products):
        for n, (_, s) in list(picks.items()):
            if s == gone and n in core_names:
                del picks[n]
                exclusions.append(Exclusion(need=n, sku=s, reason_code="DEPENDENCY_INELIGIBLE",
                                            reason_text=f"{products[s].name} lost its required base product."))

    base_why = [f"segment:{seg.value}", f"employees:{profile.employees}", f"locations:{profile.locations}",
                f"tier:{profile.city_tier}"]
    lines: list[Line] = []
    addons: list[Line] = []
    default_on: list[str] = []
    for need_name, (need, sku) in picks.items():
        ln = Line(sku=sku, need=need_name, qty=qty_for(need["qty"], profile), required=need["required"],
                  why=[f"need:{need_name}"] + base_why)
        if need["required"]:
            lines.append(ln)
        else:
            addons.append(ln)
            if need.get("default_on") or need_name in profile.wants:
                default_on.append(sku)
    core = {l.sku for l in lines}
    for dep, dependent in pulled.items():
        if dep not in core:
            lines.append(Line(sku=dep, need="dependency", qty=dep_qty(dep, profile), required=True, via_dependency=True,
                              why=[f"needed_by:{dependent}"] + base_why))
    assisted, reason = is_assisted(seg, profile)
    if assisted:
        assumptions.append(Note(key="assisted", params={"hours": ASSISTED_CALLBACK_HOURS},
                                text=f"This is an indicative price. An expert will call within {ASSISTED_CALLBACK_HOURS} hours to survey your site."))
    return Recommendation(segment=seg, bundle_name=tpl["name"], lines=lines, addons=addons, default_on=default_on,
                          exclusions=exclusions, unmet_needs=unmet_needs, assumptions=assumptions,
                          assisted=assisted, assisted_reason=reason)
