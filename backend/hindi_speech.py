"""Make Hindi replies easier for a text-to-speech voice to read well.

A Hindi TTS voice mispronounces what it has to guess: digits ("480"), "₹", clock times, long phone numbers and English words
written in Latin letters. This module rewrites those into the words a person would say, in Devanagari. It changes only what
is sent to the voice; the transcript the owner reads keeps the original text.
"""
from __future__ import annotations

import re

_W = ("शून्य एक दो तीन चार पाँच छह सात आठ नौ दस ग्यारह बारह तेरह चौदह पंद्रह सोलह सत्रह अठारह उन्नीस बीस इक्कीस बाईस तेईस चौबीस पच्चीस छब्बीस सत्ताईस अट्ठाईस उनतीस तीस "
      "इकतीस बत्तीस तैंतीस चौंतीस पैंतीस छत्तीस सैंतीस अड़तीस उनतालीस चालीस इकतालीस बयालीस तैंतालीस चौवालीस पैंतालीस छियालीस सैंतालीस अड़तालीस उनचास पचास "
      "इक्यावन बावन तिरपन चौवन पचपन छप्पन सत्तावन अट्ठावन उनसठ साठ इकसठ बासठ तिरसठ चौंसठ पैंसठ छियासठ सड़सठ अड़सठ उनहत्तर सत्तर इकहत्तर बहत्तर तिहत्तर चौहत्तर पचहत्तर "
      "छिहत्तर सतहत्तर अठहत्तर उनासी अस्सी इक्यासी बयासी तिरासी चौरासी पचासी छियासी सत्तासी अट्ठासी नवासी नब्बे इक्यानवे बानवे तिरानवे चौरानवे पंचानवे छियानवे सत्तानवे अट्ठानवे निन्यानवे").split()
assert len(_W) == 100

DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def has_devanagari(text: str) -> bool:
    return bool(DEVANAGARI.search(text or ""))


def number_words(n: int) -> str:
    """0 to 99,99,99,999 in Hindi words, Indian grouping: 2480 -> दो हज़ार चार सौ अस्सी."""
    if n < 100:
        return _W[n]
    parts = []
    for div, name in ((10**7, "करोड़"), (10**5, "लाख"), (1000, "हज़ार"), (100, "सौ")):
        q, n = divmod(n, div)
        if q:
            parts.append(f"{number_words(q)} {name}")
    if n:
        parts.append(_W[n])
    return " ".join(parts)


def digits_words(digits: str) -> str:
    return " ".join(_W[int(d)] for d in digits if d.isdigit())


def _int(text: str) -> int:
    return int(text.replace(",", ""))


def _num(text: str) -> str:
    text = text.replace(",", "")
    if "." in text:
        whole, frac = text.split(".", 1)
        return f"{number_words(int(whole or 0))} दशमलव {digits_words(frac)}"
    return number_words(int(text))


_PERIOD = [(range(0, 4), "रात"), (range(4, 12), "सुबह"), (range(12, 16), "दोपहर"), (range(16, 20), "शाम"), (range(20, 24), "रात")]


def _period(h24: int) -> str:
    return next(name for rng, name in _PERIOD if h24 in rng)


def _clock(hour12: int, minute: int, h24: int | None = None) -> str:
    hour = hour12 % 12 or 12
    nxt = (hour % 12) + 1
    if minute == 0:
        say = f"{number_words(hour)} बजे"
    elif minute == 15:
        say = f"सवा {number_words(hour)} बजे"
    elif minute == 30:
        say = "साढ़े " + number_words(hour) + " बजे"
    elif minute == 45:
        say = f"पौने {number_words(nxt)} बजे"
    else:
        say = f"{number_words(hour)} बजकर {number_words(minute)} मिनट"
    return f"{_period(h24)} {say}" if h24 is not None else say


def _time_ampm(m: re.Match) -> str:
    hour, minute, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3).lower() + "m"
    if not 1 <= hour <= 12 or minute > 59:
        return m.group(0)
    h24 = (hour % 12) + (12 if ap == "pm" else 0)
    return _clock(hour, minute, h24)


def _time_colon(m: re.Match) -> str:
    hour, minute = int(m.group(1)), int(m.group(2))
    if hour > 23 or minute > 59:
        return m.group(0)
    return _clock(hour, minute, hour if hour == 0 or hour > 12 else None)  # 1:15 alone could be night or day, so say no period


def _phone(m: re.Match) -> str:
    digits = re.sub(r"\D", "", m.group(0))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    return digits_words(digits)


def _rupees(amount: str) -> str:
    return f"{_num(amount)} {'रुपया' if amount.replace(',', '') == '1' else 'रुपये'}"


UNITS = {"kg": "किलो", "kgs": "किलो", "gm": "ग्राम", "gms": "ग्राम", "g": "ग्राम", "ml": "मिलीलीटर", "l": "लीटर", "ltr": "लीटर", "litre": "लीटर", "litres": "लीटर", "pcs": "पीस", "pc": "पीस"}
# Words callers and owners use every day in Hindi calls. Latin spelling is read badly by a Hindi voice.
LOANWORDS = {
    "order": "ऑर्डर", "orders": "ऑर्डर", "call": "कॉल", "calls": "कॉल", "callback": "कॉलबैक", "back": "बैक", "whatsapp": "व्हाट्सऐप", "discount": "डिस्काउंट",
    "delivery": "डिलीवरी", "address": "एड्रेस", "assistant": "असिस्टेंट", "number": "नंबर", "pickup": "पिकअप", "packet": "पैकेट", "packets": "पैकेट",
    "ok": "ओके", "okay": "ओके", "sir": "सर", "madam": "मैडम", "sorry": "सॉरी", "thanks": "थैंक्स", "thank": "थैंक", "you": "यू", "appointment": "अपॉइंटमेंट",
    "booking": "बुकिंग", "time": "टाइम", "shop": "शॉप", "store": "स्टोर", "bill": "बिल", "rate": "रेट", "stock": "स्टॉक", "payment": "पेमेंट", "online": "ऑनलाइन",
    "cash": "कैश", "card": "कार्ड", "hello": "हैलो", "hi": "हाय", "message": "मैसेज", "menu": "मेन्यू", "party": "पार्टी", "advance": "एडवांस", "confirm": "कन्फ़र्म",
    "quotation": "कोटेशन", "sample": "सैंपल", "free": "फ्री", "home": "होम", "office": "ऑफ़िस", "lunch": "लंच", "dinner": "डिनर", "ready": "रेडी", "busy": "बिज़ी",
    "ai": "ए आई", "cod": "कैश ऑन डिलीवरी", "upi": "यू पी आई", "otp": "ओ टी पी", "gst": "जी एस टी", "mrp": "एम आर पी", "pin": "पिन",
}
_CASE_SENSITIVE = {"AI", "COD", "UPI", "OTP", "GST", "MRP"}
_LOAN_RE = re.compile(r"\b(" + "|".join(sorted((re.escape(k) for k in LOANWORDS), key=len, reverse=True)) + r")\b", re.IGNORECASE)


def _loan(m: re.Match) -> str:
    word = m.group(1)
    if word.lower() in {w.lower() for w in _CASE_SENSITIVE} and word not in _CASE_SENSITIVE and word.upper() != word:
        return word  # "ai" or "cod" inside normal lowercase text is not the abbreviation
    return LOANWORDS[word.lower()]


def normalize(text: str) -> str:
    """Rewrite digits, money, times, phone numbers and common English words so a Hindi voice says them naturally."""
    s = text or ""
    s = re.sub(r"(?<![\d.])(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)", _phone, s)
    s = re.sub(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\b\.?", _time_ampm, s, flags=re.I)
    s = re.sub(r"(?<![\d:])(\d{1,2}):(\d{2})(?![\d:])", _time_colon, s)
    s = re.sub(r"(?:₹|\bRs\.?|\bINR)\s*(\d[\d,]*(?:\.\d+)?)", lambda m: _rupees(m.group(1)), s, flags=re.I)
    s = re.sub(r"(\d[\d,]*(?:\.\d+)?)\s*(?:rupees|rupaye|रुपये|रुपए|रु\.?)", lambda m: _rupees(m.group(1)), s, flags=re.I)
    s = re.sub(r"(\d[\d,]*(?:\.\d+)?)\s*(kgs?|gms?|g|ml|ltr|litres?|l|pcs?)\b", lambda m: f"{_num(m.group(1))} {UNITS[m.group(2).lower()]}", s, flags=re.I)
    s = re.sub(r"(\d[\d,]*(?:\.\d+)?)\s*%", lambda m: f"{_num(m.group(1))} प्रतिशत", s)
    s = re.sub(r"\d[\d,]*(?:\.\d+)?", lambda m: _num(m.group(0).rstrip(",")), s)
    s = _LOAN_RE.sub(_loan, s)
    s = s.replace("&", " और ")
    s = re.sub(r"(?<=[ऀ-ॿ])\.(?=\s|$)", "।", s)  # a Devanagari sentence ends with danda: gives the voice a proper pause
    return re.sub(r"\s+", " ", s).strip()
