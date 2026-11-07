"""Builds data/derived/kyc_fixture.json: a HUMAN-READ transcription of the 47 specimen images, keyed by file sha256.

Why: no Gemini credentials were available while building. FakeLLM returns these transcriptions so the whole KYC pipeline
(validators -> decision) can be tested offline. It proves the validators, NOT the live OCR accuracy.
The transcription is exactly what is printed on each image (including the planted problems); nothing is corrected.
Run: cd api && python -m uv run python ../scripts/build_kyc_fixture.py
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
from app.config import settings  # noqa: E402

D = settings.data_path / "kyc_documents"
OUT = Path("../data/derived/kyc_fixture.json")

# applicant: (gstin, legal, trade, constitution, address, gst_date, udyam_no, udyam_name, activity, city, state, udyam_date,
#             id_name, designation, id_no, valid_till, bill_no, bill_date)
A = {
    "K01": ("37IHKXV5167L1ZS", "Neha Kaur (Prop. Vindhya Tours & Travels)", "Vindhya Tours & Travels", "Proprietorship", "Shop/Unit 1, Tech Park Road, Visakhapatnam, Andhra Pradesh - 118383", "2025-06-07", None, "Vindhya Tours & Travels", "Services", "Visakhapatnam", "Andhra Pradesh", "2024-03-24", "Neha Kaur", "Office admin", "SYN-ID-346190", "2028-03-26", "9485717625", "2026-06-26"),
    "K02": ("19EOGXH4115Y1ZL", "Joseph Shah (Prop. Harmony Dental Care)", "Harmony Dental Care", "Proprietorship", "Shop/Unit 199, Station Road, Kolkata, West Bengal - 347550", "2022-04-17", "UDYAM-WB-00-5053330", "Harmony Dental Care", "Services", "Kolkata", "West Bengal", "2023-01-11", "Joseph Shah", "Manager", "SYN-ID-816907", "2028-09-10", "9790713533", "2026-05-22"),
    "K03": ("27XUIXG0767D1ZP", "Joseph Singh (Prop. Ganesh Woodcraft)", "Ganesh Woodcraft", "Proprietorship", "Shop/Unit 80, Civil Lines, Nagpur, Maharashtra - 411231", "2020-02-10", "UDYAM-MH-00-9516696", "Ganesh Woodcraft", "Manufacturing", "Nagpur", "Maharashtra", "2024-11-21", "Joseph Singh", "Owner", "SYN-ID-447889", "2028-07-04", "3438517928", "2026-05-30"),
    "K04": (None, None, None, None, None, None, "UDYAM-MH-00-6131836", "Saffron Dental Care LLP", "Services", "Nagpur", "Maharashtra", "2025-05-17", "Fatima Pillai", "Partner", "SYN-ID-609396", "2028-08-03", "7397844759", "2026-05-28"),
    "K05": ("32TZAXB5481U1Z1", "Balaji Realty LLP", "Balaji Realty LLP", "Limited Liability Partnership", "Shop/Unit 38, Civil Lines, Kochi, Kerala - 752083", "2020-07-26", None, None, None, None, None, None, "Anita Shah", "Owner", "SYN-ID-587234", "2029-09-11", "4294969054", "2026-06-11"),
    "K06": ("08YKZXS8189L1ZO", "Pooja Shah (Prop. Saffron Unisex Salon)", "Saffron Unisex Salon", "Proprietorship", "Shop/Unit 71, Market Yard, Jaipur, Rajasthan - 194057", "2019-09-25", "UDYAM-RJ-00-6577157", "Saffron Unisex Salon", "Services", "Jaipur", "Rajasthan", "2023-01-24", "Pooja Shah", "Owner", "SYN-ID-118354", "2028-09-15", "9566781101", "2026-06-11"),
    "K07": ("07CPCXN0398P1ZT", "Neha Banerjee (Prop. Shri Physio Clinic)", "Neelgiri Physio Clinic", "Proprietorship", "Shop/Unit 52, Transport Nagar, Delhi, Delhi - 334596", "2024-01-13", "UDYAM-DL-00-9565547", "Neelgiri Physio Clinic", "Services", "Delhi", "Delhi", "2024-07-14", "Neha Banerjee", "Manager", "SYN-ID-178237", "2030-05-05", "7545812405", "2026-07-05"),
    "K08": ("24XORXG9365M1Z3", "Joseph Rao (Prop. Green Leaf Legal Associates)", "Green Leaf Legal Associates", "Proprietorship", "Shop/Unit 238, Ring Road, Vadodara, Gujarat - 348176", "2018-12-01", "UDYAM-GJ-00-8477445", "Green Leaf Legal Associates", "Services", "Vadodara", "Gujarat", "2022-11-12", "Joseph Rao", "Office admin", "SYN-ID-393148", "2027-09-18", "2568472785", "2026-05-26"),
    "K09": ("37LDYXK0296F1ZB", "Anita Kulkarni (Prop. Kaveri Insurance Advisors)", "Kaveri Insurance Advisors", "Proprietorship", "Shop/Unit 217, Civil Lines, Visakhapatnam, Andhra Pradesh - 405337", "2023-09-20", "UDYAM-AP-00-9751562", "Kaveri Insurance Advisors", "Services", "Visakhapatnam", "Andhra Pradesh", "2023-07-04", "Anita Kulkarni", "Office admin", "SYN-ID-126040", "2027-12-22", "9375012581", "2026-07-10"),
    "K10": ("27QHJXK0658U1ZL", "Kaveri Stays LLP", "Kaveri Stays LLP", "Limited Liability Partnership", "Shop/Unit 21, Sector 14, Mumbai, Maharashtra - 570043", "2022-07-13", "UDYAM-MH-00-7183141", "Kaveri Stays LLP", "Services", "Mumbai", "Maharashtra", "2024-01-09", "Nisha Arora", "Owner", "SYN-ID-247542", "2029-06-01", "6910330901", "2026-06-18"),
    "K11": ("03KGZXT1320R1ZZ", "Trinity Bake House Pvt Ltd", "Trinity Bake House Pvt Ltd", "Private Limited Company", "Shop/Unit 188, Industrial Area Phase 2, Ludhiana, Punjab - 541498", "2019-08-19", "UDYAM-PB-00-9719478", "Trinity Bake House Pvt Ltd", "Services", "Ludhiana", "Punjab", "2025-09-15", "Vikram Pillai", "Owner", "SYN-ID-440312", "2028-12-23", "2710511786", "2025-10-31"),
    "K12": ("37NBLXS1145E1ZU", "Pooja Agarwal (Prop. Star Electronics)", "Star Electronics", "Proprietorship", "Shop/Unit 216, Nehru Nagar, Visakhapatnam, Andhra Pradesh - 762071", "2017-01-08", "UDYAM-AP-00-5186772", "Star Electronics", "Services", "Visakhapatnam", "Andhra Pradesh", "2024-02-03", "Pooja Agarwal", "Owner", "SYN-ID-365512", "2029-03-03", "6982457282", "2026-07-06"),
}
BUSINESS = {  # business name printed on the ID card / bill (== trade name, or Udyam name for K04 whose GST cert is blurred)
    "K04": "Saffron Dental Care LLP",
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


fix: dict[str, dict] = {}
for k, v in A.items():
    (gstin, legal, trade, cons, addr, gdate, uno, uname, act, city, state, udate, idn, desig, idno, valid, bno, bdate) = v
    biz = trade or BUSINESS.get(k) or uname
    if (D / f"{k}_gst_certificate.png").exists():
        if gstin is None:  # K04: blurred image -> a real OCR would be unreadable
            e = dict(doc_type_detected="gst_certificate", gstin=None, legal_name=None, trade_name=None, address=None, state=None,
                     registration_date=None, constitution=None, signatory_names=[], confidence=0.3)
        else:
            e = dict(doc_type_detected="gst_certificate", gstin=gstin, legal_name=legal, trade_name=trade, address=addr, state=state_from if (state_from := addr.split(", ")[-1].split(" - ")[0]) else None,
                     registration_date=gdate, constitution=cons, signatory_names=[], confidence=0.97)
        fix[sha(D / f"{k}_gst_certificate.png")] = {"file": f"{k}_gst_certificate.png", "slot": "gst_certificate", "extract": e}
    if (D / f"{k}_udyam_certificate.png").exists():
        e = dict(doc_type_detected="udyam_certificate", udyam_number=uno, enterprise_name=uname, enterprise_type=None, owner_name=None,
                 address=None, registration_date=udate, pan=None, gstin=None, confidence=0.97)
        fix[sha(D / f"{k}_udyam_certificate.png")] = {"file": f"{k}_udyam_certificate.png", "slot": "udyam_certificate", "extract": e}
    e = dict(doc_type_detected="signatory_id", id_kind="other", id_number=idno, name=idn, dob=None, expiry_date=valid, designation=desig,
             business_name=biz, confidence=0.98)
    fix[sha(D / f"{k}_signatory_id.png")] = {"file": f"{k}_signatory_id.png", "slot": "signatory_id", "extract": e}
    e = dict(doc_type_detected="address_proof", provider="Electricity Board (fictional)", customer_name=biz, address=addr or {"K04": "Shop/Unit 75, Lake View Colony, Nagpur, Maharashtra - 137452"}.get(k),
             bill_date=bdate, consumer_no=bno, confidence=0.97)
    fix[sha(D / f"{k}_address_proof.png")] = {"file": f"{k}_address_proof.png", "slot": "address_proof", "extract": e}

OUT.write_text(json.dumps(fix, indent=1, ensure_ascii=False), encoding="utf-8")
print(len(fix), "images transcribed ->", OUT)
