"""Rules every conversation must pass. The same file is used by build.py and by backend/tests/test_corpus.py.

A conversation is a dict with: id, lang (hi|hing|en), pack, family, importance, category, must, end, kb, turns [{role, text}].
"""
import json
import re
import sys

MAX_WORDS = 34
LATIN_OK_IN_HINDI = {"Munshi", "AI", "OTP", "PIN", "UPI", "GST", "WhatsApp", "SMS"}
BANNED = [
    r"\bpromise\b", r"\bguarantee", r"\bdefinitely\b", r"\bfor sure\b", r"\bwill refund\b", r"\bcompensat", r"\bour fault\b", r"\bmy fault\b", r"\bwe are sorry for our\b",
    r"वादा", r"गारंटी", r"पक्का मिल", r"ज़रूर मिल", r"हमारी ग़लती", r"हमारी गलती", r"मुआवज़", r"रिफंड हो जाएगा", r"पैसे वापस हो जाएँगे",
    r"\bvaada\b", r"\bgaranti\b", r"\bpakka mil", r"\bzaroor mil", r"hamari galti", r"\bmuaavaza",
    r"\b(gpt|openai|anthropic|claude|groq|llama|gemini|sarvam|chatbot|language model|chatgpt)\b",
]
ASK_PHONE = re.compile(
    r"(आपका|अपना)\s*(मोबाइल|फ़ोन|फोन)?\s*नंबर|(aapka|apna)\s*(mobile|phone)?\s*number|your\s*(phone|mobile)?\s*number|(मोबाइल|फ़ोन|फोन)\s*नंबर\s*(बताइए|दीजिए|दे दीजिए)|(mobile|phone)\s*number\s*(bataiye|dijiye|de dijiye|please)",
    re.I,
)
CLOSING = re.compile(r"धन्यवाद|नमस्ते|शुक्रिया|dhanyavaad|dhanyawad|namaste|shukriya|thank you|goodbye|good bye|bye", re.I)
NAME_ASK = re.compile(r"नाम|naam|name", re.I)
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
LATIN = re.compile(r"[A-Za-z]+")
SENTENCE = re.compile(r"[^।?.!]+[।?.!]?")
NUMBER = re.compile(r"\d+")
ALWAYS_OK_NUMBERS = {112}


def kb_numbers(kb):
    text = " ".join(str(v) for k, v in kb.items() if k != "items") + " " + " ".join(f"{i['name']} {i['price']}" for i in kb.get("items", []))
    return {int(n) for n in NUMBER.findall(text)}


def sentences(text):
    return [s for s in SENTENCE.findall(text) if s.strip()]


def validate(c):
    """Return a list of problems (empty = good)."""
    errs = []
    add = errs.append
    lang, turns = c.get("lang"), c.get("turns") or []
    if lang not in ("hi", "hing", "en"):
        add("bad lang")
    if c.get("importance") not in ("action", "fyi", "ignore"):
        add("bad importance")
    if len(turns) < 3:
        add("too short")
        return errs
    if turns[0]["role"] != "assistant":
        add("must open with the greeting")
    for a, b in zip(turns, turns[1:]):
        if a["role"] == b["role"]:
            add("turns must alternate")
            break
    if c.get("end") and turns[-1]["role"] != "assistant":
        add("an ending call must end on the assistant")
    if c.get("end") and not CLOSING.search(turns[-1]["text"]):
        add("last line has no closing word")
    allowed = kb_numbers(c["kb"]) | ALWAYS_OK_NUMBERS
    said = ""
    for i, t in enumerate(turns):
        text = t["text"]
        if not text.strip() or "{" in text or "}" in text:
            add(f"turn {i}: empty or unfilled slot")
        if lang == "hi":
            extra = {w for w in LATIN.findall(text)} - LATIN_OK_IN_HINDI
            if extra:
                add(f"turn {i}: Latin words in Hindi: {sorted(extra)}")
        elif DEVANAGARI.search(text):
            add(f"turn {i}: Devanagari in a {lang} conversation")
        if t["role"] == "caller":
            said += " " + text
            continue
        if len(text.split()) > MAX_WORDS:
            add(f"turn {i}: {len(text.split())} words, limit {MAX_WORDS}")
        for pat in BANNED:
            if re.search(pat, text, re.I):
                add(f"turn {i}: banned phrase /{pat}/")
        if ASK_PHONE.search(text):
            add(f"turn {i}: asks for the caller's number (we already have it)")
        heard = {int(n) for n in NUMBER.findall(said)}
        for n in NUMBER.findall(text):
            if int(n) not in allowed and int(n) not in heard:
                add(f"turn {i}: number {n} is not in the shop information or the caller's words")
    # tag checks: what a good reply does
    mine = [t["text"] for t in turns if t["role"] == "assistant"]
    body = mine[1:]
    allm = " ".join(mine)
    for tag in c.get("must", []):
        ok = True
        if tag == "asks_name":
            ok = any(NAME_ASK.search(x) for x in body)
        elif tag == "is_ai":
            ok = bool(re.search(r"\bAI\b", " ".join(body)))
        elif tag == "tells_112":
            ok = "112" in allm
        elif tag == "refuses_otp":
            ok = "OTP" in allm
        elif tag == "owner_will_confirm":
            ok = c["kb"]["owner"] in " ".join(body)
        elif tag == "ends_call":
            ok = bool(c.get("end"))
        elif tag == "short":
            ok = all(len(sentences(x)) <= 3 for x in body)
        elif tag == "states_kb":
            ok = any(str(n) in " ".join(body) for n in allowed - ALWAYS_OK_NUMBERS) or any(
                str(v) in " ".join(body) for k, v in c["kb"].items() if k in ("hours", "addr", "delivery", "rule", "extra") and v
            )
        if not ok:
            add(f"tag not satisfied: {tag}")
    return errs


def main(path):
    bad = 0
    seen = set()
    for n, line in enumerate(open(path, encoding="utf-8"), 1):
        c = json.loads(line)
        errs = validate(c)
        key = tuple(t["text"] for t in c["turns"])
        if key in seen:
            errs.append("duplicate conversation")
        seen.add(key)
        if errs:
            bad += 1
            print(f"{c['id']}: " + "; ".join(errs))
    print("checked", n, "conversations;", bad, "with problems")
    return bad


if __name__ == "__main__":
    sys.exit(1 if main(sys.argv[1] if len(sys.argv) > 1 else "conversations.jsonl") else 0)
