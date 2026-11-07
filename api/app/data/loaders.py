"""ONLY module that reads the raw CSVs / KYC image folder (PLAN section 2 rule 3)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from app.config import settings
from app.models.domain import GstinRecord, KycFile, Product, UdyamRecord

_KYC_RE = re.compile(r"^(K\d{2})_([a-z_]+)\.(png|jpg|jpeg|pdf)$", re.I)


def _paise(inr) -> int:
    return int(round(float(inr) * 100))


def _split(s, sep: str) -> list[str]:
    return [] if pd.isna(s) or str(s).strip() == "" else [x.strip() for x in str(s).split(sep)]


def load_catalogue(data_dir: Path | None = None) -> list[Product]:
    df = pd.read_csv((data_dir or settings.data_path) / "product_catalogue.csv")
    out = []
    for r in df.itertuples(index=False):
        out.append(
            Product(
                sku=r.product_id,
                name=r.product_name,
                category=r.category,
                description=r.description,
                unit=r.unit,
                monthly_price_min_paise=_paise(r.price_min_inr_per_month),
                monthly_price_max_paise=_paise(r.price_max_inr_per_month),
                setup_fee_paise=_paise(r.one_time_setup_inr),
                contract_months=int(r.min_contract_months),
                eligible_city_tiers=frozenset(int(t) for t in _split(r.available_city_tiers, ";")),
                min_employees=int(r.min_employees),
                min_sites=int(r.min_sites),
                requires_gstin=str(r.requires_gstin).upper() == "Y",
                requires_one_of=tuple(_split(r.requires_one_of, "|")),
                install_days=int(r.typical_install_days),
                target_segments=tuple(_split(r.target_segments, ";")),
            )
        )
    return out


def load_leads(data_dir: Path | None = None) -> pd.DataFrame:
    date_cols = [
        "created_date", "contacted_date", "needs_assessed_date",
        "quote_accepted_date", "kyc_complete_date", "activated_date",
    ]
    df = pd.read_csv((data_dir or settings.data_path) / "smb_leads.csv", parse_dates=date_cols)
    for c in ("has_gstin", "has_udyam"):
        df[c] = df[c].eq("Y")
    df["activated"] = df["outcome"].eq("Activated")
    df["churned_within_6_months"] = df["churned_within_6_months"].map({"Y": True, "N": False})
    return df


def load_gstin_registry(data_dir: Path | None = None) -> dict[str, GstinRecord]:
    df = pd.read_csv((data_dir or settings.data_path) / "mock_gstin_registry.csv", parse_dates=["registration_date"])
    return {
        r.gstin: GstinRecord(
            gstin=r.gstin, legal_name=r.legal_name, trade_name=r.trade_name,
            constitution=r.constitution, address=r.principal_place_of_business,
            state=r.state, registration_date=r.registration_date.date(), status=r.status,
        )
        for r in df.itertuples(index=False)
    }


def load_udyam_registry(data_dir: Path | None = None) -> dict[str, UdyamRecord]:
    df = pd.read_csv((data_dir or settings.data_path) / "mock_udyam_registry.csv", parse_dates=["date_of_registration"])
    return {
        r.udyam_number: UdyamRecord(
            udyam_number=r.udyam_number, enterprise_name=r.enterprise_name,
            enterprise_type=r.enterprise_type, major_activity=r.major_activity,
            nic_description=r.nic_description, state=r.state, city=r.city,
            date_of_registration=r.date_of_registration.date(),
        )
        for r in df.itertuples(index=False)
    }


def list_kyc_applicants(data_dir: Path | None = None) -> dict[str, list[KycFile]]:
    folder = (data_dir or settings.data_path) / "kyc_documents"
    out: dict[str, list[KycFile]] = {}
    for f in sorted(folder.iterdir()):
        m = _KYC_RE.match(f.name)
        if m:
            out.setdefault(m.group(1), []).append(KycFile(applicant_id=m.group(1), doc_type=m.group(2), path=str(f)))
    return out


@dataclass
class AppData:
    catalogue: list[Product] = field(default_factory=list)
    leads: pd.DataFrame = field(default_factory=pd.DataFrame)
    gstin: dict[str, GstinRecord] = field(default_factory=dict)
    udyam: dict[str, UdyamRecord] = field(default_factory=dict)
    kyc: dict[str, list[KycFile]] = field(default_factory=dict)

    @property
    def products(self) -> dict[str, Product]:
        return {p.sku: p for p in self.catalogue}

    def business_type_segments(self) -> dict[str, str]:
        """business_type -> dominant lead segment (derived from leads data)."""
        g = self.leads.groupby("business_type")["segment"].agg(lambda x: x.value_counts().index[0])
        return g.to_dict()

    def city_states(self) -> dict[str, str]:
        return self.leads.groupby("city")["state"].first().to_dict()

    def segment_median_spend(self) -> dict[str, int]:
        return self.leads.groupby("segment")["monthly_telecom_spend_inr"].median().astype(int).to_dict()

    def counts(self) -> dict[str, int]:
        return {
            "products": len(self.catalogue), "leads": len(self.leads),
            "gstin": len(self.gstin), "udyam": len(self.udyam),
            "kyc_applicants": len(self.kyc), "kyc_images": sum(len(v) for v in self.kyc.values()),
        }


_data: AppData | None = None


def get_data() -> AppData:
    """Load once, reuse (singleton)."""
    global _data
    if _data is None:
        _data = AppData(
            catalogue=load_catalogue(), leads=load_leads(),
            gstin=load_gstin_registry(), udyam=load_udyam_registry(),
            kyc=list_kyc_applicants(),
        )
    return _data
