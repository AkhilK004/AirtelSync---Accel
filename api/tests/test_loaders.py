import re

from fastapi.testclient import TestClient

from app.data.loaders import get_data
from app.main import app

D = get_data()


def test_counts():
    assert D.counts() == {"products": 25, "leads": 5000, "gstin": 3534, "udyam": 2723,
                          "kyc_applicants": 12, "kyc_images": 47}


def test_dependencies_reference_existing_products():
    skus = set(D.products)
    for p in D.catalogue:
        assert set(p.requires_one_of) <= skus, p.sku


def test_no_duplicate_keys():
    assert len(D.products) == len(D.catalogue)
    assert D.leads.lead_id.is_unique
    assert D.leads.gstin.dropna().is_unique


def test_money_is_int_paise():
    p = D.products["P01"]
    assert (p.monthly_price_min_paise, p.monthly_price_max_paise) == (99900, 119900)
    assert all(isinstance(x.setup_fee_paise, int) for x in D.catalogue)


def test_lead_registry_links_and_funnel():
    L = D.leads
    assert L.gstin.dropna().isin(D.gstin.keys()).all()
    assert L.udyam_number.dropna().isin(D.udyam.keys()).all()
    assert L.activated.sum() == 368
    assert round(L.days_lead_to_activation.mean(), 1) == 17.6


def test_kyc_file_mapping():
    assert len(D.kyc["K05"]) == 3  # K05 has no Udyam certificate
    assert all(re.fullmatch(r"K\d\d", k) for k in D.kyc)


def test_health():
    with TestClient(app) as c:
        r = c.get("/health")
    assert r.status_code == 200 and r.json()["counts"]["products"] == 25
    assert r.json()["model"]["version"] == "propensity-v3"
