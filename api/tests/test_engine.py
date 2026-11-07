import pytest

from app.data.loaders import get_data
from app.engine.eligibility import eligible
from app.engine.pricing import EngineError, build_quote, initial_state, toggle
from app.engine.recommender import recommend
from app.engine.segments import classify
from app.models.engine import Profile, Segment

P = get_data().products


def prof(**kw):
    base = dict(business_type="Kirana store", employees=2, locations=1, city_tier=2, gstin_status="active")
    base.update(kw)
    return Profile(**base)


def skus(rec):
    return {l.sku for l in rec.lines} | {a.sku for a in rec.addons}


# ---- one test per segment
def test_segment_micro():
    r = recommend(prof())
    assert r.segment == Segment.MICRO_RETAIL and {l.sku for l in r.lines} == {"P01", "P07"} and not r.assisted


def test_segment_professional():
    r = recommend(prof(business_type="Dental clinic", employees=6, city_tier=1))
    assert r.segment == Segment.PROFESSIONAL
    assert {"P16", "P20"} <= {l.sku for l in r.lines}  # cloud email + security included


def test_segment_multi_site():
    r = recommend(prof(business_type="Restaurant chain", employees=40, locations=4, city_tier=1))
    assert r.segment == Segment.MULTI_SITE and {l.sku: l.qty for l in r.lines}["P01"] == 4 and not r.assisted


def test_segment_manufacturer_assisted():
    r = recommend(prof(business_type="Auto-parts unit", employees=80, city_tier=1))
    assert r.segment == Segment.MANUFACTURER and r.assisted and r.assisted_reason == "needs_site_survey"
    assert "P06" in skus(r)


def test_many_locations_assisted():
    r = recommend(prof(business_type="Apparel retail chain", employees=60, locations=12, city_tier=1))
    assert r.assisted and r.segment == Segment.MULTI_SITE


def test_chain_type_with_one_location_is_not_multi_site():
    seg, _ = classify(prof(business_type="Pharmacy chain", employees=4, locations=1))
    assert seg == Segment.MICRO_RETAIL


def test_unknown_business_type_records_assumption():
    r = recommend(prof(business_type="Zoo", employees=9))
    assert r.segment == Segment.PROFESSIONAL and any(a.key == "business_type_unknown" for a in r.assumptions)


# ---- eligibility
def test_tier_exclusion_reported():
    r = recommend(prof(business_type="CA firm", employees=30, city_tier=2))
    assert "P03" not in skus(r) and "P02" in {l.sku for l in r.lines}
    assert any(e.sku == "P03" and e.reason_code == "CITY_TIER" for e in r.exclusions)


def test_gstin_less_gets_no_gstin_products():
    for bt, emp, loc in [("Kirana store", 2, 1), ("CA firm", 30, 1), ("Restaurant chain", 40, 4), ("Textile unit", 30, 1)]:
        r = recommend(prof(business_type=bt, employees=emp, locations=loc, gstin_status="none"))
        assert not [s for s in skus(r) if P[s].requires_gstin], (bt, skus(r))


@pytest.mark.parametrize("st", ["applied", "inactive", "none"])
def test_non_active_gstin_blocks_gstin_products(st):
    assert eligible(P["P15"], prof(gstin_status=st)).reason_code == "GSTIN_REQUIRED"
    assert eligible(P["P15"], prof(gstin_status="active")).ok


def test_size_and_site_rules():
    assert eligible(P["P05"], prof(employees=5)).reason_code == "SIZE_TOO_SMALL"
    assert eligible(P["P10"], prof(employees=50, locations=2)).reason_code == "TOO_FEW_SITES"


# ---- dependencies
def test_every_recommended_line_has_dependency_satisfied():
    for bt, emp, loc, t in [("Kirana store", 2, 1, 2), ("CA firm", 12, 1, 1), ("Gym chain", 50, 5, 1), ("Textile unit", 40, 1, 1)]:
        r = recommend(prof(business_type=bt, employees=emp, locations=loc, city_tier=t))
        sel = {l.sku for l in r.lines} | set(r.default_on)
        for s in sel:
            assert not P[s].requires_one_of or set(P[s].requires_one_of) & sel, (bt, s)


def test_ineligible_dependency_drops_dependent():
    # no fibre + wants failover: P09 needs P01/02/03/05/06; P05/P06 need GSTIN+size -> none eligible
    r = recommend(prof(business_type="Dental clinic", employees=6, city_tier=1, fibre_available=False, wants=["failover"]))
    assert "P04" in {l.sku for l in r.lines}
    assert "P09" not in skus(r)
    assert any(e.sku == "P09" and e.reason_code == "DEPENDENCY_INELIGIBLE" for e in r.exclusions)


def test_dependency_pulled_when_eligible():
    # leased line (P05) is allowed from 10 people with an active GSTIN, so failover can ride on it
    r = recommend(prof(business_type="Dental clinic", employees=12, city_tier=1, fibre_available=False, wants=["failover"]))
    assert "P09" in set(r.default_on)
    assert any(l.via_dependency and l.sku == "P05" for l in r.lines)


def test_no_fibre_uses_fwa():
    r = recommend(prof(business_type="Salon", employees=3, fibre_available=False))
    assert "P04" in {l.sku for l in r.lines} and "P01" not in skus(r)


def test_determinism():
    p = prof(business_type="CA firm", employees=12, city_tier=1)
    assert recommend(p).model_dump() == recommend(p).model_dump()
    s1, s2 = initial_state(p, "x"), initial_state(p, "x")
    assert build_quote(s1).model_dump() == build_quote(s2).model_dump()


def test_toggle_pulls_dependency_and_removes_dependents():
    st = initial_state(prof(business_type="Dental clinic", employees=6, city_tier=1), "q")
    # simulate a quote whose connectivity was swapped: remove P01 from state, then add CCTV
    sel = {k: v for k, v in st.selected.items() if k != "P01"}
    st = st.model_copy(update={"selected": sel})
    st2, notes = toggle(st, "P23", True)
    assert "P23" in st2.selected and any(n.key == "dep_added" for n in notes)
    assert any(s in st2.selected for s in P["P23"].requires_one_of)
    st3, notes3 = toggle(st2, "P23", False)
    assert "P23" not in st3.selected


def test_required_line_cannot_be_removed():
    st = initial_state(prof(), "q")
    with pytest.raises(EngineError) as e:
        toggle(st, "P01", False)
    assert e.value.status == 409 and e.value.code == "REQUIRED_LINE"
