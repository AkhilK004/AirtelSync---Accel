"""Deterministic rule-based NLU for the advisor slots (en / Hinglish / hi / mr).

Used by FakeLLM (offline tests, scenarios) and as the fallback when the live LLM call fails or times out.
It extracts ONLY facts that are literally present in the text; it never guesses.
"""
from __future__ import annotations

import re

from app.advisor.slots import CITY_ALIASES, SlotUpdate, band_value, city_tiers

NUMW = {"one": 1, "single": 1, "ek": 1, "एक": 1, "two": 2, "do": 2, "दो": 2, "दोन": 2, "three": 3, "teen": 3, "तीन": 3,
        "four": 4, "char": 4, "चार": 4, "five": 5, "paanch": 5, "पाँच": 5, "पांच": 5, "पाच": 5}
_NUM = r"(\d+|" + "|".join(sorted(NUMW, key=len, reverse=True)) + r")"
EMP_UNITS = r"(?:log|lok|people|teachers?|doctors?|lawyers?|engineers?|persons?|staff|employees?|workers?|members?|karmachari|karamchari|कर्मचारी|कामगार|लोगों|लोग|लोक|जण|माणसे|स्टाफ|वर्कर्स)"
LOC_UNITS = (r"(?:outlets?|stores?|shops?|branch(?:es)?|locations?|sites?|offices?|centres?|centers?|plants?|clinics?|क्लिनिक|क्लीनिक|factory|factories|showrooms?|"
             r"dukaan|dukan|दुकानें|दुकाने|दुकान|शाखाएं|शाखा|आउटलेट|ठिकाणे|ठिकाण|जगह|ऑफिस|कार्यालय)")

BT_RULES: list[tuple[str, str]] = [
    (r"pharmacy chain", "Pharmacy chain"), (r"bakery chain", "Bakery chain"), (r"restaurant chain", "Restaurant chain"),
    (r"mobile repair", "Mobile repair shop"), (r"physio", "Physiotherapy clinic"), (r"dental|dentist|दंत", "Dental clinic"),
    (r"pharm?acy|pharmcy|farmacy|medical store|chemist|फार्मेसी|फार्मसी|मेडिकल", "Pharmacy"), (r"kirana|grocery|provision|किराणा|किराना|general store", "Kirana store"),
    (r"salon|parlou?r|सैलून|सलून|ब्यूटी", "Salon"), (r"\bca\b|chartered|accountant|ca firm|सीए", "CA firm"),
    (r"coaching|tuition|classes|कोचिंग|ट्यूशन", "Coaching centre"), (r"law office|lawyer|advocate|वकील|वकिल", "Law office"),
    (r"travel", "Travel agency"), (r"architect", "Architecture studio"), (r"real estate|property dealer|प्रॉपर्टी", "Real estate agency"),
    (r"insurance|बीमा|विमा", "Insurance agency"), (r"\bgym\b|fitness|जिम", "Gym chain"), (r"diagnostic|pathology|\blab\b", "Diagnostic lab"),
    (r"optician|चश्मा", "Optician"), (r"boutique|tailor|बुटीक", "Boutique"), (r"bakery|बेकरी", "Bakery"), (r"sweet shop|mithai|मिठाई", "Sweet shop"),
    (r"stationery", "Stationery shop"), (r"hardware", "Hardware store"), (r"textile|कपड़ा मिल", "Textile unit"),
    (r"auto[- ]?parts", "Auto-parts unit"), (r"packaging", "Packaging unit"), (r"plastic", "Plastic moulding unit"),
    (r"printing", "Printing press"), (r"furniture", "Furniture workshop"), (r"food processing", "Food processing unit"),
    (r"manufactur|factory|\bplant\b|workshop|कारखान|उत्पादन|फैक्ट्री|फॅक्टरी", "Manufacturing unit"),
    (r"clinic|doctor|क्लिनिक|दवाखाना", "Clinic"), (r"restaurant|dhaba|cafe|रेस्टोरेंट|रेस्टॉरंट|होटल", "Restaurant"),
    (r"retail|retailer|showroom", "Retail"), (r"\bshop\b|dukaan|dukan|दुकान", "Kirana store"),
]
TOOL_RULES: list[tuple[str, str, str | None]] = [  # (pattern, tool, implied want)
    (r"hotspot|हॉटस्पॉट", "Mobile hotspot", None), (r"home broadband|home wifi|ghar ka|घर का|घरचा", "Home broadband", None),
    (r"upi|qr|paytm|phonepe", "UPI QR", "billing_pos"), (r"\bpos\b|card machine|swipe", "POS machine", "billing_pos"),
    (r"cctv|camera|कैमरा|कॅमेरा", "CCTV", "cctv"), (r"gmail|personal email|yahoo|पर्सनल", "Personal Gmail", None),
    (r"whatsapp business", "WhatsApp Business", None),
    # already an Accel customer -> propensity feature (A58). Not bare "accel": owners name the company when asking for its products.
    (r"\baccel\s+(mobile|sim|number|postpaid|prepaid|connection)|(already|currently)\s+(with|on|using|use)\s+accel\b|(accel|एक्सेल|ॲक्सेल)\s*(मोबाइल|सिम)", "Accel mobile", None),
]
WANT_RULES: list[tuple[str, str]] = [
    (r"failover|fail-over|backup (internet|link|connection)|internet (band|down|chala)|internet na ho|इंटरनेट बंद", "failover"),
    (r"website|वेबसाइट", "website"), (r"firewall|फ़ायरवॉल|फायरवॉल", "firewall"), (r"toll[- ]?free|1800", "toll_free"),
    (r"\biot\b|machine monitoring|sensor", "machine_monitoring"), (r"\bgps\b|fleet|vehicle tracker|gaadi track", "fleet_tracking"),
    (r"data backup|cloud backup|backup of (my )?(files|data)", "backup"), (r"static ip", "static_ip"), (r"guest wi-?fi", "guest_wifi"),
    (r"sd-?wan|one bill|ek bill|central(ly)? manage", "central_management"), (r"business phone|cloud telephony|ivr", "business_phone"),
]
UNAVAILABLE = r"laptops?|computers?|desktops?|printers?|tablets?|handsets?|smartphones?|mobile phones?|tvs?|television|ac\b|air conditioner"
INJECTION = (r"ignore (all |your |previous |the |these )?(rules|instructions|prompt)|system prompt|you are now|pretend|jailbreak|disregard|developer mode|"
             r"discount|\d+\s*%|free of cost|muft|मुफ्त|मोफत|छूट|सवलत|reduce the price|lower the price|sasta kar|price kam")
DONT_KNOW = (r"pata nahi|pata nahin|nahi pata|don'?t know|dont know|not sure|no idea|\bidk\b|maloom nahi|पता नहीं|नहीं पता|माहित नाही|माहीत नाही|"
             r"मालूम नहीं|ठाऊक नाही|कल्पना नाही")
MR_MARKERS = ["आहे", "आहेत", "माझे", "माझा", "माझी", "मध्ये", "आम्ही", "होय", "नाही", "करतात", "पुण्यात", "पाहिजे", "तुमचा", "तुमचे", "मला", "लोक"]
HI_ROMAN = {"hai", "hain", "mein", "meri", "mera", "mere", "karte", "karta", "chahiye", "nahi", "nahin", "pata", "kya", "kitna", "kyun", "kyu",
            "haan", "zyada", "jyada", "liye", "hoon", "mujhe", "hum", "wala", "dukaan", "dukan", "log", "kaam", "aur", "bataiye", "batao"}
MR_ROMAN = {"aahe", "ahe", "ahet", "majhi", "majha", "mazi", "madhe", "pahije", "kaay", "kiti"}
EN_WORDS = {"i", "have", "my", "the", "is", "and", "with", "want", "need", "staff", "people", "in", "a", "we", "our", "do", "you", "sell", "for", "to"}


def _num(tok: str) -> int:
    return int(tok) if tok.isdigit() else NUMW[tok]


def detect_language(text: str) -> str | None:
    t = text.lower()
    if re.search(r"in english|english (mein|me|madhe)", t):
        return "en"
    if re.search(r"hindi (mein|me)|in hindi|हिंदी में|हिन्दी में", t):
        return "hi"
    if re.search(r"in marathi|marathi (madhe|mein)|मराठीत|मराठी मध्ये", t):
        return "mr"
    if re.search(r"[ऀ-ॿ]", text):
        return "mr" if any(m in text for m in MR_MARKERS) else "hi"
    words = set(re.findall(r"[a-z]+", t))
    if words & MR_ROMAN:
        return "mr"
    if words & HI_ROMAN - {"log"} or ("log" in words and words & HI_ROMAN - {"log", "kaam"}):
        return "hi"
    if len(words & EN_WORDS) >= 2:
        return "en"
    return None


def _city(text: str) -> str | None:
    low = text.lower()
    for name in city_tiers():
        if re.search(rf"(?<![a-z]){re.escape(name.lower())}(?![a-z])", low):
            return name
    for alias, name in CITY_ALIASES.items():
        if alias in text:
            return name
    for alt, name in (("bangalore", "Bengaluru"), ("mysore", "Mysuru"), ("bombay", "Mumbai")):
        if alt in low:
            return name
    return None


def _gstin(text: str) -> str | None:
    t = text.lower()
    if re.search(r"\b\d{2}[a-z]{5}\d{4}[a-z][1-9a-z]z[0-9a-z]\b", t):
        return "yes"
    g = r"(?:g\.?s\.?t(?:in)?|जीएसटी|जी\.एस\.टी)"
    if re.search(rf"(?:no|without|nahi|nahin|don'?t have|dont have|na|बिना|नहीं|नाही)\s+(?:\w+\s+){{0,2}}{g}|{g}\s*(?:\w+\s+){{0,2}}(?:nahi|nahin|no\b|नहीं|नाही|नसेल)", t):
        return "no"
    if re.search(rf"(?:\bnot|n't|isn't|without)\s+(?:\w+\s+){{0,3}}{g}|{g}\s*(?:\w+\s+){{0,3}}(?:not\b|invalid|inactive|cancelled|suspended)", t):
        return "no"  # "GST not registered", "not registered for GST", "GST invalid" (negation must beat the 'registered/active' yes-words)
    if re.search(rf"{g}.{{0,20}}(?:applied|apply|process|pending|laga|अप्लाई|अर्ज)|(?:applied|apply|अप्लाई|अर्ज).{{0,20}}{g}", t):
        return "applied"
    if re.search(rf"{g}", t) and re.search(r"hai|haan|yes|have|है|आहे|होय|हां|हाँ|ho\b|with|number|there|registered|active|valid|aahe|आहे", t):
        return "yes"
    if re.search(rf"(?:with|have|has)\s+{g}", t):
        return "yes"
    return None


def _budget(text: str) -> int | None:
    m = re.search(r"(?:₹|rs\.?|inr)\s*([\d,]+)\s*(k)?", text, re.I) or re.search(r"([\d,]+)\s*(k)?\s*(?:rupees|rs\b|₹|रुपये|रुपए|se zyada|se jyada|से ज़्यादा|से ज्यादा)", text, re.I)
    if not m and re.search(r"budget|बजट|बजेट", text, re.I):
        m = re.search(r"([\d,]+)\s*(k)?", text)
    if not m:
        return None
    v = int(m.group(1).replace(",", "") or 0)
    return v * 1000 if m.group(2) else v


def parse(text: str, pending: str | None = None) -> SlotUpdate:
    raw = text.strip()
    t = raw.lower()
    u = SlotUpdate()
    u.language = detect_language(raw)
    u.injection_attempt = bool(re.search(INJECTION, t))
    m = re.search(rf"\b({UNAVAILABLE})", t)
    if m:
        u.requested_unavailable_item = m.group(1)
    if re.search(DONT_KNOW, t):
        u.dont_know = [pending] if pending else []

    # intent
    if re.search(r"talk to (a )?(person|human|someone|agent)|real person|human|call me|callback|baat karni|baat karo|insaan|representative|\bagent\b|expert se|माणूस|माणसाशी|इंसान|किसी से बात|बोलायचे आहे", t):
        u.intent = "request_human"
    elif re.search(r"\bwhy\b|kyun|\bkyu\b|kyon|क्यों|explain|samjha|समझा|(plan|प्लान|प्लॅन)\s*(का|क्यों)|का हा|हा प्लॅन का|ka plan kyun", t):
        u.intent = "ask_why"
    elif re.search(r"\bprice\b|kitna|kitne|\bcost\b|how much|कीमत|किंमत|कितना|किती|charges?|see price|full price", t) and not u.injection_attempt:
        u.intent = "ask_price"
    elif re.search(r"actually|instead|rather|make it|change|badal|बदल|ऐवजी|अब |now we", t):
        u.intent = "change_answer"
    elif re.fullmatch(r"(hi|hello|hey|namaste|namaskar|नमस्ते|नमस्कार|thanks|thank you|dhanyavad|ok|okay)[!. ]*", t):
        u.intent = "smalltalk"

    # business type
    for pat, canon in BT_RULES:
        if re.search(pat, t) or re.search(pat, raw):
            u.business_type = canon
            break

    # employees
    m = re.search(rf"(\d+)\s*(?:{EMP_UNITS})", t) or re.search(r"(?:team|staff|employees?)\s*(?:of|is|are|:)?\s*(\d+)", t)
    if m:
        u.employees = int(m.group(1))
    # locations
    m = re.search(rf"(?<![a-z]){_NUM}\s*(?:hi\s+|only\s+)?(?:{LOC_UNITS})", t)
    if m:
        u.locations = _num(m.group(1))
    if u.locations is None:  # "15 retail stores", "4 small shops": an adjective between the number and a plural unit
        m = re.search(r"(?<![a-z])(\d+)\s+(?:\w+\s+){1,2}?(?:outlets|stores|shops|branches|showrooms|locations|sites|offices|clinics)\b", t)
        if m and not re.search(rf"{m.group(1)}\s+(?:{EMP_UNITS})", t):
            u.locations = int(m.group(1))
    # city / gstin / budget
    c = _city(raw)
    if c:
        u.city = c
    g = _gstin(raw)
    if g:
        u.has_gstin = g
    b = _budget(raw)
    if b:
        u.budget_monthly = b
    if re.search(r"fib(?:re|er)\s+(?:is\s+)?(?:not|nahi|nahin|isn'?t)|(?:no|not|nahi|nahin|without)\s+(?:\w+\s+){0,2}fib(?:re|er)|फाइबर\s*(?:नहीं|नाही)", t):
        u.fibre_available = False

    # tools & wants
    tools: list[str] = []
    wants: list[str] = []
    for pat, tool, want in TOOL_RULES:
        if re.search(pat, t) or re.search(pat, raw):
            tools.append(tool)
            if want and want not in wants:
                wants.append(want)
    if re.search(r"leased line|लीज़्ड|लीज्ड", t):
        if pending == "current_tools":
            tools.append("Leased line")
        else:
            wants.append("leased_line")
    for pat, w in WANT_RULES:
        if re.search(pat, t) and w not in wants:
            wants.append(w)
    u.current_tools = tools
    u.wants = wants

    # bare answers to the pending question
    bare = re.fullmatch(r"[\d\s,+\-–—]+", raw)
    if pending in ("employees", "locations") and bare:
        v = band_value(raw, pending) or (int(re.sub(r"\D", "", raw)) if re.sub(r"\D", "", raw) else None)
        if v:
            setattr(u, pending, v)
    if pending == "has_gstin" and not u.has_gstin:
        if re.fullmatch(r"(yes|y|haan|han|ha|haa|ji|ji haan|hai|ho|हाँ|हां|हा|होय|हो|है)[!. ]*", t):
            u.has_gstin = "yes"
        elif re.fullmatch(r"(no|n|nahi|nahin|na|नहीं|नाही|नही)[!. ]*", t):
            u.has_gstin = "no"
        elif "applied" in t or "apply" in t:
            u.has_gstin = "applied"
    if pending == "city" and not u.city and not u.dont_know and "?" not in raw and not u.injection_attempt and re.fullmatch(r"[A-Za-zऀ-ॿ .'-]{2,30}", raw) and u.intent == "answer":
        u.city = raw.strip().title()
    if (pending == "business_type" and not u.business_type and not u.dont_know and u.intent == "answer" and 2 <= len(raw) <= 40 and not bare
            and "?" not in raw and not u.requested_unavailable_item and not u.injection_attempt):
        u.business_type = raw.strip()
    if pending == "current_tools" and re.fullmatch(r"(skip|none|nothing|कुछ नहीं|वगळा|छोड़ें)[!. ]*", t):
        u.current_tools = []
    return u
