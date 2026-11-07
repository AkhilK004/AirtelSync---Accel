"""User-visible strings (en/hi/mr). Used as the deterministic fallback reply AND as the offline (FakeLLM) NLG."""
from __future__ import annotations

LANGS = ("en", "hi", "mr")

GREETING = {
    "en": "Hi! I'm the Accel Business advisor. A few quick questions and I'll suggest the right plan for you.",
    "hi": "नमस्ते! मैं Accel Business सलाहकार हूँ। कुछ छोटे सवालों के बाद मैं आपके लिए सही प्लान बताऊँगा।",
    "mr": "नमस्कार! मी Accel Business सल्लागार आहे. काही छोटे प्रश्न विचारून मी तुमच्यासाठी योग्य प्लॅन सुचवतो.",
}
QUESTION = {
    "business_type": {"en": "What kind of business do you run?", "hi": "आप किस तरह का बिज़नेस चलाते हैं?", "mr": "तुमचा कोणत्या प्रकारचा व्यवसाय आहे?"},
    "employees": {"en": "How many people work in your business, including you?", "hi": "आपको मिलाकर आपके बिज़नेस में कितने लोग काम करते हैं?", "mr": "तुमच्यासह तुमच्या व्यवसायात किती लोक काम करतात?"},
    "locations": {"en": "How many shops, offices or outlets do you have?", "hi": "आपकी कितनी दुकानें, ऑफिस या आउटलेट हैं?", "mr": "तुमची किती दुकाने, कार्यालये किंवा आउटलेट आहेत?"},
    "city": {"en": "Which city is your business in?", "hi": "आपका बिज़नेस किस शहर में है?", "mr": "तुमचा व्यवसाय कोणत्या शहरात आहे?"},
    "has_gstin": {"en": "Do you have a GSTIN?", "hi": "क्या आपके पास GSTIN है?", "mr": "तुमच्याकडे GSTIN आहे का?"},
    "current_tools": {"en": "What do you use today? (internet, UPI QR, POS machine, CCTV, personal Gmail...)",
                      "hi": "अभी आप क्या इस्तेमाल करते हैं? (इंटरनेट, UPI QR, POS मशीन, CCTV, पर्सनल Gmail...)",
                      "mr": "सध्या तुम्ही काय वापरता? (इंटरनेट, UPI QR, POS मशीन, CCTV, वैयक्तिक Gmail...)"},
}
CLARIFY = {"en": "Sorry, I didn't catch that. ", "hi": "माफ़ कीजिए, मैं समझ नहीं पाया। ", "mr": "माफ करा, मला समजले नाही. "}

# chips: (label, value). Value is plain text that the NLU (and the rule parser) understands in any language.
_BT = [("Kirana / Shop", "Kirana store"), ("Salon", "Salon"), ("Pharmacy", "Pharmacy"), ("Clinic", "Clinic"), ("CA / Office", "CA firm"),
       ("Coaching", "Coaching centre"), ("Restaurant", "Restaurant"), ("Manufacturing", "Manufacturing unit")]
_BT_HI = ["किराना / दुकान", "सैलून", "फार्मेसी", "क्लिनिक", "CA / ऑफिस", "कोचिंग", "रेस्टोरेंट", "मैन्युफैक्चरिंग"]
_BT_MR = ["किराणा / दुकान", "सलून", "फार्मसी", "क्लिनिक", "CA / ऑफिस", "कोचिंग", "रेस्टॉरंट", "उत्पादन"]
CHIPS = {
    "business_type": {"en": [(l, v) for l, v in _BT], "hi": [(a, v) for a, (_, v) in zip(_BT_HI, _BT)], "mr": [(a, v) for a, (_, v) in zip(_BT_MR, _BT)]},
    "employees": {l: [("1–2", "1-2"), ("3–5", "3-5"), ("6–10", "6-10"), ("11–25", "11-25"), ("25+", "25+")] for l in LANGS},
    "locations": {l: [("1", "1"), ("2", "2"), ("3–5", "3-5"), ("6–10", "6-10"), ("10+", "10+")] for l in LANGS},
    "city": {l: [] for l in LANGS},
    "has_gstin": {"en": [("Yes", "yes"), ("No", "no"), ("Applied", "applied")], "hi": [("हाँ", "yes"), ("नहीं", "no"), ("अप्लाई किया है", "applied")],
                  "mr": [("होय", "yes"), ("नाही", "no"), ("अर्ज केला आहे", "applied")]},
    "current_tools": {"en": [("Mobile hotspot", "mobile hotspot"), ("Home broadband", "home broadband"), ("UPI QR", "UPI QR"), ("POS machine", "POS machine"),
                             ("CCTV", "CCTV"), ("Personal Gmail", "personal gmail"), ("Leased line", "leased line"), ("WhatsApp Business", "whatsapp business"), ("Accel mobile", "accel mobile"), ("Skip", "skip")],
                      "hi": [("मोबाइल हॉटस्पॉट", "mobile hotspot"), ("घर का ब्रॉडबैंड", "home broadband"), ("UPI QR", "UPI QR"), ("POS मशीन", "POS machine"),
                             ("CCTV", "CCTV"), ("पर्सनल Gmail", "personal gmail"), ("लीज़्ड लाइन", "leased line"), ("WhatsApp Business", "whatsapp business"), ("Accel मोबाइल", "accel mobile"), ("छोड़ें", "skip")],
                      "mr": [("मोबाइल हॉटस्पॉट", "mobile hotspot"), ("घरचा ब्रॉडबँड", "home broadband"), ("UPI QR", "UPI QR"), ("POS मशीन", "POS machine"),
                             ("CCTV", "CCTV"), ("वैयक्तिक Gmail", "personal gmail"), ("लीज्ड लाइन", "leased line"), ("WhatsApp Business", "whatsapp business"), ("Accel मोबाइल", "accel mobile"), ("वगळा", "skip")]},
}
POST_REC_CHIPS = {
    "en": [("See full price", "see price"), ("Why this plan?", "why this plan?"), ("Tell you what I use today", "tools"), ("Talk to a person", "talk to a person")],
    "hi": [("पूरी कीमत देखें", "see price"), ("यह प्लान क्यों?", "why this plan?"), ("मैं अभी क्या इस्तेमाल करता हूँ", "tools"), ("किसी इंसान से बात करें", "talk to a person")],
    "mr": [("पूर्ण किंमत पहा", "see price"), ("हा प्लॅन का?", "why this plan?"), ("मी सध्या काय वापरतो", "tools"), ("माणसाशी बोला", "talk to a person")],
}

# why a product is in the bundle, by need (formatted with employees / locations)
NEED_REASON = {
    "connectivity": {"en": "fast internet for your {employees} people", "hi": "आपके {employees} लोगों के लिए तेज़ इंटरनेट", "mr": "तुमच्या {employees} लोकांसाठी वेगवान इंटरनेट"},
    "business_sim": {"en": "business mobile lines for calls and data", "hi": "कॉल और डेटा के लिए बिज़नेस मोबाइल लाइन", "mr": "कॉल आणि डेटासाठी बिझनेस मोबाइल लाइन"},
    "cloud_email": {"en": "email on your own business name instead of personal Gmail", "hi": "पर्सनल Gmail की जगह आपके बिज़नेस के नाम पर ईमेल", "mr": "वैयक्तिक Gmail ऐवजी तुमच्या व्यवसायाच्या नावाने ईमेल"},
    "security": {"en": "keeps every computer and phone safe from viruses and ransomware, so your data stays secure",
                 "hi": "हर कंप्यूटर और फ़ोन को वायरस और रैनसमवेयर से बचाता है, ताकि आपका डेटा सुरक्षित रहे",
                 "mr": "प्रत्येक संगणक व फोनला व्हायरस आणि रॅन्समवेअरपासून वाचवते, त्यामुळे तुमचा डेटा सुरक्षित राहतो"},
    "failover": {"en": "keeps you online when the main internet goes down", "hi": "मुख्य इंटरनेट बंद होने पर भी आपको ऑनलाइन रखता है", "mr": "मुख्य इंटरनेट बंद पडल्यास तुम्हाला ऑनलाइन ठेवते"},
    "backup": {"en": "automatic backup of your files", "hi": "आपकी फ़ाइलों का ऑटोमैटिक बैकअप", "mr": "तुमच्या फाइल्सचा आपोआप बॅकअप"},
    "static_ip": {"en": "a fixed address for CCTV or remote access", "hi": "CCTV या रिमोट एक्सेस के लिए फिक्स्ड एड्रेस", "mr": "CCTV किंवा रिमोट अ‍ॅक्सेससाठी फिक्स्ड पत्ता"},
    "business_phone": {"en": "business phone lines over internet with call recording", "hi": "कॉल रिकॉर्डिंग के साथ इंटरनेट पर बिज़नेस फ़ोन लाइन", "mr": "कॉल रेकॉर्डिंगसह इंटरनेटवर बिझनेस फोन लाईन"},
    "cctv": {"en": "cameras you can watch on your phone, with 30-day recording", "hi": "फ़ोन पर देखने वाले कैमरे, 30 दिन की रिकॉर्डिंग के साथ", "mr": "फोनवर पाहता येणारे कॅमेरे, 30 दिवसांच्या रेकॉर्डिंगसह"},
    "guest_wifi": {"en": "separate safe Wi-Fi for your customers", "hi": "आपके ग्राहकों के लिए अलग सुरक्षित वाई-फ़ाई", "mr": "तुमच्या ग्राहकांसाठी वेगळे सुरक्षित वाय-फाय"},
    "billing_pos": {"en": "GST-ready billing with UPI and card payments", "hi": "UPI और कार्ड पेमेंट के साथ GST-रेडी बिलिंग", "mr": "UPI आणि कार्ड पेमेंटसह GST-रेडी बिलिंग"},
    "customer_messaging": {"en": "send updates to customers on WhatsApp", "hi": "ग्राहकों को WhatsApp पर अपडेट भेजें", "mr": "ग्राहकांना WhatsApp वर अपडेट पाठवा"},
    "website": {"en": "a simple website and domain for your business", "hi": "आपके बिज़नेस के लिए सरल वेबसाइट और डोमेन", "mr": "तुमच्या व्यवसायासाठी साधी वेबसाइट आणि डोमेन"},
    "central_management": {"en": "manage all your locations from one place", "hi": "सभी लोकेशन एक ही जगह से मैनेज करें", "mr": "सर्व ठिकाणे एकाच जागेवरून व्यवस्थापित करा"},
    "firewall": {"en": "a managed firewall that guards your network", "hi": "आपके नेटवर्क की रक्षा करने वाला मैनेज्ड फ़ायरवॉल", "mr": "तुमच्या नेटवर्कचे रक्षण करणारा मॅनेज्ड फायरवॉल"},
    "toll_free": {"en": "a toll-free number for your customers", "hi": "आपके ग्राहकों के लिए टोल-फ्री नंबर", "mr": "तुमच्या ग्राहकांसाठी टोल-फ्री क्रमांक"},
    "machine_monitoring": {"en": "see machine uptime and energy use live", "hi": "मशीन का अपटाइम और बिजली खपत लाइव देखें", "mr": "मशीनचा अपटाइम आणि वीज वापर लाइव्ह पहा"},
    "fleet_tracking": {"en": "live GPS tracking for your vehicles", "hi": "आपके वाहनों की लाइव GPS ट्रैकिंग", "mr": "तुमच्या वाहनांचे लाइव्ह GPS ट्रॅकिंग"},
    "dependency": {"en": "needed to make the other items work", "hi": "बाकी सेवाएँ चलाने के लिए ज़रूरी", "mr": "इतर सेवा चालण्यासाठी आवश्यक"},
}

# assumption / note keys -> text. Engine notes keep their English text as fallback.
NOTE = {
    "employees_default": {"en": "We assumed 1–2 employees.", "hi": "हमने मान लिया कि 1–2 कर्मचारी हैं।", "mr": "आम्ही 1–2 कर्मचारी गृहीत धरले."},
    "locations_default": {"en": "We assumed 1 location.", "hi": "हमने मान लिया कि 1 लोकेशन है।", "mr": "आम्ही 1 ठिकाण गृहीत धरले."},
    "city_default": {"en": "We assumed a tier-2 city.", "hi": "हमने टियर-2 शहर मान लिया।", "mr": "आम्ही टियर-2 शहर गृहीत धरले."},
    "city_unknown": {"en": "We don't have your city on our list, so we assumed a tier-2 city.", "hi": "आपका शहर हमारी सूची में नहीं है, इसलिए हमने टियर-2 मान लिया।", "mr": "तुमचे शहर आमच्या यादीत नाही, म्हणून टियर-2 गृहीत धरले."},
    "gstin_default": {"en": "We assumed you don't have a GSTIN yet.", "hi": "हमने मान लिया कि अभी आपके पास GSTIN नहीं है।", "mr": "आम्ही गृहीत धरले की तुमच्याकडे अजून GSTIN नाही."},
    "business_type_default": {"en": "We could not tell your business type, so we sized the plan by team size.", "hi": "आपके बिज़नेस का प्रकार समझ नहीं आया, इसलिए प्लान टीम के आकार के हिसाब से बनाया।", "mr": "तुमचा व्यवसाय प्रकार समजला नाही, म्हणून प्लॅन टीमच्या आकारानुसार बनवला."},
    "business_type_unknown": {"en": "We could not match your business type, so we sized the plan by team size.", "hi": "आपके बिज़नेस का प्रकार नहीं मिला, इसलिए प्लान टीम के आकार के हिसाब से बनाया।", "mr": "तुमचा व्यवसाय प्रकार जुळला नाही, म्हणून प्लॅन टीमच्या आकारानुसार बनवला."},
    "tier_clamped": {"en": "We treated your city as tier-2.", "hi": "हमने आपके शहर को टियर-2 माना।", "mr": "आम्ही तुमचे शहर टियर-2 मानले."},
    "assisted": {"en": "This is an indicative price. An expert will call you within {hours} hours to survey your site.",
                 "hi": "यह अनुमानित कीमत है। हमारा विशेषज्ञ {hours} घंटे के भीतर साइट सर्वे के लिए आपको कॉल करेगा।",
                 "mr": "ही अंदाजे किंमत आहे. आमचे तज्ञ {hours} तासांत साइट सर्वेसाठी तुम्हाला कॉल करतील."},
    "dep_added": {"en": "Also added {name} because {because} needs it.", "hi": "{name} भी जोड़ा गया क्योंकि {because} को इसकी ज़रूरत है।", "mr": "{name} देखील जोडले कारण {because} ला त्याची गरज आहे."},
    "dep_removed": {"en": "Removed {name} because it needs {because}.", "hi": "{name} हटाया गया क्योंकि उसे {because} चाहिए।", "mr": "{name} काढले कारण त्याला {because} हवे."},
    "gst_extra": {"en": "Prices exclude GST; {rate}% GST is added in the total.", "hi": "कीमतों में GST शामिल नहीं है; कुल में {rate}% GST जोड़ा गया है।", "mr": "किमतीत GST समाविष्ट नाही; एकूणमध्ये {rate}% GST जोडला आहे."},
}

M = {
    "ack_refusal": {"en": "Our prices come from the catalogue and I can't change them or give discounts. ",
                    "hi": "हमारी कीमतें कैटलॉग से तय होती हैं, मैं उन्हें बदल या डिस्काउंट नहीं दे सकता। ",
                    "mr": "आमच्या किमती कॅटलॉगनुसार ठरतात, मी त्या बदलू किंवा सवलत देऊ शकत नाही. "},
    "ack_unavailable": {"en": "Sorry, we don't offer {item}. We can help with internet, mobile lines, security, CCTV and more. ",
                        "hi": "माफ़ कीजिए, हम {item} नहीं देते। हम इंटरनेट, मोबाइल लाइन, सिक्योरिटी, CCTV आदि में मदद कर सकते हैं। ",
                        "mr": "माफ करा, आम्ही {item} देत नाही. आम्ही इंटरनेट, मोबाइल लाईन, सिक्युरिटी, CCTV इत्यादींमध्ये मदत करू शकतो. "},
    "leased_unavailable": {"en": "A leased line is not available for you right now ({reason}). ",
                           "hi": "अभी आपके लिए लीज़्ड लाइन उपलब्ध नहीं है ({reason})। ",
                           "mr": "सध्या तुमच्यासाठी लीज्ड लाइन उपलब्ध नाही ({reason}). "},
    "leased_alt": {"en": "Fibre or 5G AirFiber below is the closest fit. ", "hi": "नीचे दिया फाइबर या 5G एयरफाइबर सबसे नज़दीकी विकल्प है। ", "mr": "खालील फायबर किंवा 5G एअरफायबर हा सर्वात जवळचा पर्याय आहे. "},
    "leased_survey": {"en": "A leased line needs a site survey; an expert will confirm it. ", "hi": "लीज़्ड लाइन के लिए साइट सर्वे चाहिए; हमारा विशेषज्ञ पुष्टि करेगा। ", "mr": "लीज्ड लाइनसाठी साइट सर्वे आवश्यक आहे; तज्ञ खात्री करतील. "},
    "plan_intro": {"en": "Here is your plan: {bundle}.", "hi": "आपका प्लान: {bundle}।", "mr": "तुमचा प्लॅन: {bundle}."},
    "total": {"en": "Total: {total} per month including GST", "hi": "कुल: {total} प्रति माह (GST सहित)", "mr": "एकूण: {total} प्रति महिना (GST सह)"},
    "setup": {"en": ", plus {setup} one-time setup", "hi": ", और {setup} एक बार का सेटअप", "mr": ", आणि {setup} एकदाचे सेटअप"},
    "contract": {"en": " ({months}-month contract).", "hi": " ({months} महीने का अनुबंध)।", "mr": " ({months} महिन्यांचा करार)."},
    "addons_hint": {"en": "You can add or remove extras like {names} on the price page.", "hi": "कीमत वाले पेज पर आप {names} जैसे एक्स्ट्रा जोड़ या हटा सकते हैं।", "mr": "किंमत पानावर तुम्ही {names} सारखे एक्स्ट्रा जोडू किंवा काढू शकता."},
    "no_gstin_hint": {"en": "Without a GSTIN some products are not available; you can register on Udyam to get started.", "hi": "GSTIN के बिना कुछ प्रोडक्ट उपलब्ध नहीं हैं; शुरू करने के लिए आप Udyam पर रजिस्टर कर सकते हैं।", "mr": "GSTIN शिवाय काही उत्पादने उपलब्ध नाहीत; सुरू करण्यासाठी तुम्ही Udyam वर नोंदणी करू शकता."},
    "skipped": {"en": "Not available for you: {names}.", "hi": "आपके लिए उपलब्ध नहीं: {names}।", "mr": "तुमच्यासाठी उपलब्ध नाही: {names}."},
    "budget_over": {"en": "Your budget is {budget}, but the cheapest plan that works for you is {cheapest} per month incl. GST — {gap} more. I can't lower the price; you can keep only the core items.",
                    "hi": "आपका बजट {budget} है, पर आपके लिए सबसे सस्ता काम करने वाला प्लान {cheapest} प्रति माह (GST सहित) है — यानी {gap} ज़्यादा। मैं कीमत कम नहीं कर सकता; आप सिर्फ़ ज़रूरी चीज़ें रख सकते हैं।",
                    "mr": "तुमचे बजेट {budget} आहे, पण तुमच्यासाठी सर्वात स्वस्त प्लॅन {cheapest} प्रति महिना (GST सह) आहे — म्हणजे {gap} जास्त. मी किंमत कमी करू शकत नाही; तुम्ही फक्त मुख्य गोष्टी ठेवू शकता."},
    "budget_trim": {"en": "This is above your budget of {budget}. Drop optional extras ({names}) to fit: core plan is {cheapest} per month incl. GST.",
                    "hi": "यह आपके {budget} के बजट से ज़्यादा है। वैकल्पिक एक्स्ट्रा ({names}) हटाएँ: मुख्य प्लान {cheapest} प्रति माह (GST सहित) है।",
                    "mr": "हे तुमच्या {budget} बजेटपेक्षा जास्त आहे. पर्यायी एक्स्ट्रा ({names}) काढा: मुख्य प्लॅन {cheapest} प्रति महिना (GST सह) आहे."},
    "explain_intro": {"en": "You told me: {summary}. So I picked:", "hi": "आपने बताया: {summary}। इसलिए मैंने चुना:", "mr": "तुम्ही सांगितले: {summary}. म्हणून मी निवडले:"},
    "summary": {"en": "{bt} in {city}, {employees} people, {locations} location(s)", "hi": "{bt}, {city} में, {employees} लोग, {locations} लोकेशन", "mr": "{bt}, {city} मध्ये, {employees} लोक, {locations} ठिकाण(े)"},
    "handoff": {"en": "Sure — a person from our team will call you within {hours} hours. Please share your phone number in the form below.",
                "hi": "ज़रूर — हमारी टीम का कोई व्यक्ति {hours} घंटे में आपको कॉल करेगा। कृपया नीचे फ़ॉर्म में अपना फ़ोन नंबर दें।",
                "mr": "नक्कीच — आमच्या टीममधील व्यक्ती {hours} तासांत तुम्हाला कॉल करेल. कृपया खालील फॉर्ममध्ये तुमचा फोन नंबर द्या."},
    "assisted_called": {"en": "An expert will call you within {hours} hours.", "hi": "हमारा विशेषज्ञ {hours} घंटे में आपको कॉल करेगा।", "mr": "आमचे तज्ञ {hours} तासांत तुम्हाला कॉल करतील."},
    "refine": {"en": "Tell me what you use today and I will refine it.", "hi": "बताइए आप अभी क्या इस्तेमाल करते हैं, मैं प्लान सुधार दूँगा।", "mr": "तुम्ही सध्या काय वापरता ते सांगा, मी प्लॅन सुधारतो."},
    "unknown_bt": {"en": "your business", "hi": "आपका बिज़नेस", "mr": "तुमचा व्यवसाय"},
}


def tr(table: dict, lang: str, **kw) -> str:
    s = table.get(lang) or table["en"]
    return s.format(**kw) if kw else s


def note_text(key: str, lang: str, params: dict, fallback: str) -> str:
    t = NOTE.get(key)
    return tr(t, lang, **params) if t else fallback
