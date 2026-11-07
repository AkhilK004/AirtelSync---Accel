from app.engine.money import fmt_inr, midpoint_rupee_paise, pct_of
from app.engine.pricing import build_quote, initial_state, toggle
from app.models.engine import Profile


def q_for(**kw):
    base = dict(business_type="Kirana store", employees=2, locations=1, city_tier=2, gstin_status="active")
    base.update(kw)
    st = initial_state(Profile(**base), "t")
    return st, build_quote(st)


def test_money_format():
    assert fmt_inr(149900) == "₹1,499"
    assert fmt_inr(123456700) == "₹12,34,567"
    assert fmt_inr(170864) == "₹1,708.64"
    assert fmt_inr(0) == "₹0"


def test_midpoint_rule():
    assert midpoint_rupee_paise(99900, 119900) == 109900
    assert midpoint_rupee_paise(12500, 15000) == 13800  # 137.5 -> 138 (half up)


def test_bundle_a_micro_hand_computed():
    # P01 mid 1099 x1 + P07 mid 349 x1 = 1448 ; GST 18% = 260.64 ; total 1708.64
    _, q = q_for()
    assert q.monthly_subtotal_paise == 144800 and q.gst_paise == 26064 and q.monthly_total_paise == 170864
    assert q.one_time_paise == 0 and q.contract_months == 12
    assert q.monthly_total_display == "₹1,708.64"


def test_bundle_b_clinic_hand_computed():
    # P01 1099 + P07 349x2 + P16 138x6 + P20 124x6 = 1099+698+828+744 = 3369 ; GST 606.42
    _, q = q_for(business_type="Dental clinic", employees=6, city_tier=1)
    assert q.monthly_subtotal_paise == 336900 and q.gst_paise == 60642 and q.monthly_total_paise == 397542


def test_bundle_c_multisite_with_setup():
    # 4 sites: P01 1099x4 + P08 699x4 + P09 549x4 = 4396+2796+2196 = 9388 ; GST 1689.84 ; setup P09 1500x4 = 6000, GST 1080
    _, q = q_for(business_type="Restaurant chain", employees=40, locations=4, city_tier=1)
    assert q.monthly_subtotal_paise == 938800 and q.monthly_total_paise == 938800 + 168984
    assert q.one_time_paise == 600000 and q.one_time_total_paise == 708000
    assert q.contract_months == 12


def test_toggle_updates_totals_and_matches_recompute():
    st, q0 = q_for(business_type="Restaurant chain", employees=40, locations=4, city_tier=1)
    st2, _ = toggle(st, "P23", True)  # CCTV: 249 x (4 sites x2) = 1992 ; setup 1800 x 8 = 14400
    q1 = build_quote(st2)
    assert q1.monthly_subtotal_paise - q0.monthly_subtotal_paise == 249 * 8 * 100
    assert q1.one_time_paise - q0.one_time_paise == 1800 * 8 * 100
    assert q1.monthly_total_paise == q1.monthly_subtotal_paise + q1.gst_paise
    st3, _ = toggle(st2, "P23", False)
    assert build_quote(st3).model_dump() == q0.model_dump()


def test_contract_is_max_of_lines():
    st, _ = q_for(business_type="Auto-parts unit", employees=80, city_tier=1)
    st2, _ = toggle(st, "P24", True)  # IoT 24 months
    assert build_quote(st2).contract_months == 24


def test_all_money_is_int():
    st, _ = q_for(business_type="Gym chain", employees=50, locations=5, city_tier=1)
    q = build_quote(st)
    for k, v in q.model_dump().items():
        if k.endswith("_paise"):
            assert type(v) is int, k
    for l in q.lines:
        assert type(l.unit_price_paise) is int and type(l.line_monthly_paise) is int and type(l.setup_paise) is int
    assert type(pct_of(12345, 0.18)) is int


def test_gst_rounding_half_up():
    assert pct_of(25, 0.18) == 5      # 4.5 -> 5
    assert pct_of(250, 0.18) == 45
