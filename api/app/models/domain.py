from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class Product(BaseModel):
    sku: str
    name: str
    category: str
    description: str
    unit: str  # per site | per line | per user | ...
    monthly_price_min_paise: int
    monthly_price_max_paise: int
    setup_fee_paise: int
    contract_months: int
    eligible_city_tiers: frozenset[int]
    min_employees: int
    min_sites: int
    requires_gstin: bool
    requires_one_of: tuple[str, ...]  # at least one of these SKUs must be in the bundle
    install_days: int
    target_segments: tuple[str, ...]  # micro | prof | multi | mfg

    @property
    def per_site(self) -> bool:
        return self.unit == "per site"


class GstinRecord(BaseModel):
    gstin: str
    legal_name: str
    trade_name: str
    constitution: str
    address: str
    state: str
    registration_date: date
    status: str  # Active | Cancelled | Suspended


class UdyamRecord(BaseModel):
    udyam_number: str
    enterprise_name: str
    enterprise_type: str  # Micro | Small | Medium
    major_activity: str
    nic_description: str
    state: str
    city: str
    date_of_registration: date


class KycFile(BaseModel):
    applicant_id: str
    doc_type: str  # gst_certificate | udyam_certificate | signatory_id | address_proof
    path: str
