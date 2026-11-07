"""Consent ledger (DPDP): append-only grants and withdrawals, versioned notice, granular unbundled purposes."""
from __future__ import annotations

from app.advisor.models import now_iso
from app.engine.pricing import new_id
from app.errors import ApiError
from app.repo import get_repo

NOTICE_VERSION = "2026-07-v1"
GRIEVANCE_CONTACT = "grievance@accel-business.example"  # fictional
RETENTION = {"kyc_documents_days_if_review": 1, "extracted_fields_months": 12}

PURPOSES = [  # id, required, default on
    {"id": "kyc_verification", "required": True, "default": False},
    {"id": "service_delivery", "required": True, "default": False},
    {"id": "marketing", "required": False, "default": False},
    {"id": "partner_sharing", "required": False, "default": False},
]
REQUIRED = {p["id"] for p in PURPOSES if p["required"]}
KNOWN = {p["id"] for p in PURPOSES}

NOTICE = {
    "en": {
        "title": "Before we check your documents",
        "summary": ["Who we are: Accel Business (a fictional demo service).",
                    "What we collect: your business and signatory details from the documents you upload, and your phone number.",
                    "Why: to verify your business and deliver, activate and bill your service. Nothing else without your separate OK.",
                    "How long: photos are read in memory and not saved, except if a person must review them (deleted within 1 day). Extracted details are kept 12 months.",
                    "Your rights: see, correct or erase your data, withdraw consent any time, or complain to our grievance officer."],
        "full": "We process your personal data under the Digital Personal Data Protection Act, 2023, only for the purposes you tick below (purpose limitation) and only the data each step needs (data minimisation). Aadhaar numbers, if you upload one, are masked to the last 4 digits immediately. Data is stored and processed in India. You can withdraw any consent as easily as you gave it; withdrawing a required purpose stops that step. Grievance contact: " + GRIEVANCE_CONTACT + ".",
        "purposes": {
            "kyc_verification": "Verify my business and signatory from the documents I upload",
            "service_delivery": "Install, activate, bill and support my service",
            "marketing": "Send me offers on WhatsApp / SMS",
            "partner_sharing": "Share my contact with the local installation partner",
        },
        "required_label": "Required", "optional_label": "Optional", "read_full": "Read full notice", "version": "Notice version",
    },
    "hi": {
        "title": "आपके दस्तावेज़ जाँचने से पहले",
        "summary": ["हम कौन हैं: Accel Business (एक काल्पनिक डेमो सेवा)।",
                    "हम क्या लेते हैं: आपके अपलोड किए दस्तावेज़ों से बिज़नेस और हस्ताक्षरकर्ता की जानकारी, और आपका फ़ोन नंबर।",
                    "क्यों: आपके बिज़नेस की पुष्टि करने और सेवा देने, चालू करने व बिल बनाने के लिए। आपकी अलग सहमति के बिना और कुछ नहीं।",
                    "कब तक: फ़ोटो मेमोरी में पढ़ी जाती हैं और सेव नहीं होतीं, सिवाय तब जब किसी व्यक्ति को जाँचना हो (1 दिन में मिटा दी जाती हैं)। निकाली गई जानकारी 12 महीने रखी जाती है।",
                    "आपके अधिकार: अपना डेटा देखना, सुधारना या मिटवाना, कभी भी सहमति वापस लेना, या शिकायत अधिकारी से शिकायत करना।"],
        "full": "हम आपका निजी डेटा डिजिटल पर्सनल डेटा प्रोटेक्शन एक्ट, 2023 के तहत केवल उन्हीं उद्देश्यों के लिए प्रोसेस करते हैं जिन पर आप नीचे टिक करते हैं (उद्देश्य की सीमा), और हर चरण के लिए ज़रूरी डेटा ही लेते हैं (डेटा न्यूनतमीकरण)। अगर आप आधार अपलोड करते हैं तो उसे तुरंत सिर्फ़ आख़िरी 4 अंकों तक मास्क कर दिया जाता है। डेटा भारत में ही स्टोर और प्रोसेस होता है। जितनी आसानी से सहमति दी, उतनी आसानी से वापस ले सकते हैं; ज़रूरी उद्देश्य की सहमति वापस लेने पर वह चरण रुक जाता है। शिकायत संपर्क: " + GRIEVANCE_CONTACT + "।",
        "purposes": {
            "kyc_verification": "मेरे अपलोड किए दस्तावेज़ों से मेरे बिज़नेस और हस्ताक्षरकर्ता की पुष्टि करें",
            "service_delivery": "मेरी सेवा इंस्टॉल, चालू, बिल और सपोर्ट करें",
            "marketing": "मुझे WhatsApp / SMS पर ऑफ़र भेजें",
            "partner_sharing": "मेरा संपर्क स्थानीय इंस्टॉलेशन पार्टनर से साझा करें",
        },
        "required_label": "ज़रूरी", "optional_label": "वैकल्पिक", "read_full": "पूरा नोटिस पढ़ें", "version": "नोटिस संस्करण",
    },
    "mr": {
        "title": "तुमची कागदपत्रे तपासण्यापूर्वी",
        "summary": ["आम्ही कोण: Accel Business (एक काल्पनिक डेमो सेवा).",
                    "आम्ही काय घेतो: तुम्ही अपलोड केलेल्या कागदपत्रांतील व्यवसाय आणि स्वाक्षरीकर्त्याची माहिती, आणि तुमचा फोन नंबर.",
                    "का: तुमच्या व्यवसायाची पडताळणी करण्यासाठी आणि सेवा देणे, सुरू करणे व बिल करण्यासाठी. तुमच्या वेगळ्या संमतीशिवाय दुसरे काहीही नाही.",
                    "किती काळ: फोटो मेमरीत वाचले जातात आणि जतन केले जात नाहीत, फक्त व्यक्तीला तपासायचे असेल तर (1 दिवसात हटवले जातात). काढलेली माहिती 12 महिने ठेवली जाते.",
                    "तुमचे हक्क: तुमचा डेटा पाहणे, दुरुस्त करणे किंवा पुसणे, केव्हाही संमती मागे घेणे, किंवा तक्रार अधिकाऱ्याकडे तक्रार करणे."],
        "full": "आम्ही तुमचा वैयक्तिक डेटा डिजिटल पर्सनल डेटा प्रोटेक्शन ॲक्ट, 2023 अंतर्गत फक्त तुम्ही खाली टिक केलेल्या उद्देशांसाठी प्रक्रिया करतो (उद्देश मर्यादा) आणि प्रत्येक टप्प्याला आवश्यक तेवढाच डेटा घेतो (डेटा किमानता). तुम्ही आधार अपलोड केल्यास तो लगेच फक्त शेवटच्या 4 अंकांपर्यंत मास्क केला जातो. डेटा भारतातच साठवला व प्रक्रिया केला जातो. संमती देणे जितके सोपे तितकेच मागे घेणे सोपे; आवश्यक उद्देशाची संमती मागे घेतल्यास तो टप्पा थांबतो. तक्रार संपर्क: " + GRIEVANCE_CONTACT + ".",
        "purposes": {
            "kyc_verification": "मी अपलोड केलेल्या कागदपत्रांवरून माझ्या व्यवसायाची आणि स्वाक्षरीकर्त्याची पडताळणी करा",
            "service_delivery": "माझी सेवा इन्स्टॉल, सुरू, बिल आणि सपोर्ट करा",
            "marketing": "मला WhatsApp / SMS वर ऑफर पाठवा",
            "partner_sharing": "माझा संपर्क स्थानिक इन्स्टॉलेशन पार्टनरला द्या",
        },
        "required_label": "आवश्यक", "optional_label": "ऐच्छिक", "read_full": "पूर्ण नोटीस वाचा", "version": "नोटीस आवृत्ती",
    },
}


def notice(lang: str, partner_flow: bool) -> dict:
    n = NOTICE.get(lang) or NOTICE["en"]
    purposes = [{"id": p["id"], "required": p["required"], "default": p["default"], "label": n["purposes"][p["id"]]}
                for p in PURPOSES if p["id"] != "partner_sharing" or partner_flow]
    return {"version": NOTICE_VERSION, "language": lang if lang in NOTICE else "en", "title": n["title"], "summary": n["summary"], "full": n["full"],
            "purposes": purposes, "labels": {k: n[k] for k in ("required_label", "optional_label", "read_full", "version")}}


def _order(order_id: str) -> dict:
    o = get_repo().get("orders", order_id)
    if not o:
        raise ApiError(404, "ORDER_NOT_FOUND", "order.not_found")
    return o


def ledger(order_id: str) -> list[dict]:
    return sorted((r for r in get_repo().list("consents") if r["order_id"] == order_id), key=lambda r: r["id"])


def effective(order_id: str) -> set[str]:
    """Replay the ledger: grants add purposes, withdrawals remove them."""
    live: set[str] = set()
    for r in ledger(order_id):
        live = (live | set(r["purposes"])) if r["kind"] == "grant" else (live - set(r["purposes"]))
    return live


def grant(order_id: str, purposes: list[str], language: str, channel: str = "web") -> dict:
    o = _order(order_id)
    unknown = set(purposes) - KNOWN
    if unknown:
        raise ApiError(422, "PURPOSE_UNKNOWN", "consent.purpose_unknown", {"purposes": sorted(unknown)})
    if not REQUIRED <= set(purposes):
        raise ApiError(422, "CONSENT_REQUIRED", "consent.required", {"missing": sorted(REQUIRED - set(purposes))})
    rec = {"id": new_id(), "kind": "grant", "order_id": order_id, "principal_ref": o["principal_ref"], "purposes": sorted(set(purposes)),
           "notice_version": NOTICE_VERSION, "language": language if language in NOTICE else "en", "timestamp": now_iso(), "channel": channel}
    get_repo().append("consents", rec["id"], rec)
    return rec


def withdraw(consent_id: str, purposes: list[str]) -> dict:
    base = get_repo().get("consents", consent_id)
    if not base or base["kind"] != "grant":
        raise ApiError(404, "CONSENT_NOT_FOUND", "consent.not_found")
    bad = set(purposes) - set(base["purposes"])
    if bad or not purposes:
        raise ApiError(422, "PURPOSE_NOT_GRANTED", "consent.purpose_not_granted", {"purposes": sorted(bad)})
    rec = {"id": new_id(), "kind": "withdraw", "ref_id": consent_id, "order_id": base["order_id"], "principal_ref": base["principal_ref"],
           "purposes": sorted(set(purposes)), "notice_version": base["notice_version"], "language": base["language"], "timestamp": now_iso(), "channel": "web"}
    get_repo().append("consents", rec["id"], rec)
    return rec


def require_kyc_consent(order_id: str) -> None:
    _order(order_id)
    if "kyc_verification" not in effective(order_id):
        raise ApiError(403, "CONSENT_MISSING", "consent.kyc_missing")
