"""Local words and how to say them.

The owner or the platform lists words callers use (items, titles, places, units) and how the voice should say each one.
The list is used three ways, so the AI is prepared before the call:
  * the voice (text to speech) says each word the way it is written in the "say it as" column;
  * the speech recogniser gets the words as a hint, so it hears "काजू कतली" and not nonsense;
  * words with a meaning are listed in the AI's prompt ({{local_words}}), so it understands slang like "udhar".
A built-in starter list covers everyday Hindi shop words; the platform list and each business's own list add to it and win on a clash.
"""
from __future__ import annotations

import re
import time

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from lab import settings_store
from lab.runner import run_db
from lab.service import ServiceError

from . import tenant

KEY = "assistant.lexicon"
MAX_ENTRIES = 400
_CACHE: dict[str, tuple[float, list[dict]]] = {}
LISTENERS: list = []  # called after a save, so caches elsewhere can be dropped
_TTL = 60.0

# (written forms, say it as, meaning for the AI). Meanings are kept only where a word may be unclear.
_S = [
    ("kaju katli, kaju kathli", "काजू कतली", "cashew fudge sweet"), ("barfi, burfi", "बरफ़ी", "milk fudge sweet"), ("gulab jamun", "गुलाब जामुन", ""), ("ladoo, laddu", "लड्डू", ""),
    ("motichoor", "मोतीचूर", "motichoor laddu"), ("jalebi", "जलेबी", ""), ("rasgulla", "रसगुल्ला", ""), ("rasmalai", "रसमलाई", ""), ("samosa", "समोसा", ""), ("kachori", "कचौरी", ""),
    ("namkeen", "नमकीन", "savoury snacks"), ("paneer", "पनीर", ""), ("dahi", "दही", "curd"), ("ghee", "घी", ""), ("atta", "आटा", "wheat flour"), ("maida", "मैदा", ""), ("besan", "बेसन", "gram flour"),
    ("chawal", "चावल", "rice"), ("basmati", "बासमती", ""), ("dal", "दाल", "lentils"), ("toor dal, tur dal", "तूर दाल", ""), ("moong", "मूँग", ""), ("chana", "चना", ""), ("rajma", "राजमा", ""),
    ("cheeni, chini", "चीनी", "sugar"), ("namak", "नमक", "salt"), ("tel", "तेल", "oil"), ("haldi", "हल्दी", ""), ("mirch", "मिर्च", ""), ("jeera", "जीरा", ""), ("thali", "थाली", "plate meal"),
    ("biryani", "बिरयानी", ""), ("chai", "चाय", ""), ("lassi", "लस्सी", ""),
    ("bhaiya", "भैया", "a polite way to address a man, like brother"), ("didi", "दीदी", "polite way to address a woman, like sister"), ("sahab, sahib", "साहब", "sir"), ("madam", "मैडम", ""),
    ("uncle", "अंकल", ""), ("aunty", "आंटी", ""), ("bhai", "भाई", ""),
    ("paav, pav", "पाव", "quarter kilo, 250 grams"), ("adha kilo, aadha kilo", "आधा किलो", "half a kilo"), ("dhai, dhaai", "ढाई", "two and a half"), ("derh, dedh", "डेढ़", "one and a half"),
    ("saadhe", "साढ़े", "plus a half"), ("sawa", "सवा", "plus a quarter"), ("dozen", "दर्जन", "12 pieces"), ("peti", "पेटी", "carton or box"), ("dabba", "डिब्बा", "box or tin"),
    ("kal", "कल", "tomorrow or yesterday, from context"), ("parso", "परसों", "day after tomorrow"), ("aaj", "आज", "today"), ("subah", "सुबह", "morning"), ("dopahar", "दोपहर", "afternoon"),
    ("shaam", "शाम", "evening"), ("raat", "रात", "night"), ("jaldi", "जल्दी", "soon, in a hurry"), ("abhi", "अभी", "now"),
    ("udhar", "उधार", "on credit, pay later"), ("hisaab, hisab", "हिसाब", "account or bill"), ("rupaye, rupee", "रुपये", ""), ("paise", "पैसे", "money"),
    ("nagar", "नगर", ""), ("marg", "मार्ग", "road"), ("chowk", "चौक", "crossroad"), ("gali", "गली", "lane"), ("mohalla", "मोहल्ला", "neighbourhood"), ("bazaar, bazar", "बाज़ार", ""),
    ("mandi", "मंडी", "wholesale market"), ("chauraha", "चौराहा", "four-way crossing"), ("dukaan, dukan", "दुकान", "shop"),
]
STARTER = [{"word": w, "say": s, "meaning": m, "source": "built-in"} for w, s, m in _S]


class EntryIn(BaseModel):
    word: str = Field(min_length=1, max_length=200)
    say: str = Field(min_length=1, max_length=80)
    meaning: str = Field(default="", max_length=160)
    model_config = {"extra": "forbid"}

    @field_validator("word", "say", "meaning")
    @classmethod
    def _strip(cls, v: str) -> str:
        return re.sub(r"\s+", " ", v or "").strip()


def forms(word: str) -> list[str]:
    """'kaju katli, kaju kathli | काजू कतली' -> the written forms, longest first."""
    return sorted({f.strip() for f in re.split(r"[,|]", word or "") if f.strip()}, key=len, reverse=True)[:8]


def _custom(session: Session, scope: str) -> list[dict]:
    data = (settings_store.get(session, KEY, {}) if scope == "platform" else tenant.get(session, "lexicon", {})) or {}
    return [dict(e) for e in data.get("entries", [])]


def _check(scope: str) -> None:
    if scope not in ("platform", "business"):
        raise ServiceError("Unknown scope.", 422)
    if scope == "business" and not tenant.active_id():
        raise ServiceError("Choose a business first.", 422)


def view(session: Session, scope: str) -> dict:
    _check(scope)
    return {"scope": scope, "entries": _custom(session, scope), "builtin": STARTER,
            "inherited": _custom(session, "platform") if scope == "business" else []}


def save(session: Session, scope: str, entries: list[EntryIn]) -> dict:
    _check(scope)
    if len(entries) > MAX_ENTRIES:
        raise ServiceError(f"At most {MAX_ENTRIES} words.", 422)
    clean, seen = [], set()
    for e in entries:
        fs = forms(e.word)
        if not fs or not e.say:
            raise ServiceError("Each word needs a spelling and a way to say it.", 422)
        key = fs[0].lower()
        if key in seen:
            continue
        seen.add(key)
        clean.append({"word": ", ".join(fs), "say": e.say, "meaning": e.meaning})
    payload = {"entries": clean}
    if scope == "platform":
        settings_store.put(session, KEY, payload)
    else:
        tenant.put(session, "lexicon", payload)
    _CACHE.clear()
    for fn in LISTENERS:
        fn()
    from . import config
    config.audit(session, "pronunciation", f"{'Platform' if scope == 'platform' else 'Business'} local words saved ({len(clean)})", business_id=None if scope == "platform" else "current")
    return view(session, scope)


def effective(session: Session) -> list[dict]:
    """Built-in, then platform, then this business: later lists win when they share a written form."""
    by_form: dict[str, dict] = {}
    for source, items in (("built-in", STARTER), ("platform", _custom(session, "platform")), ("business", _custom(session, "business") if tenant.active_id() else [])):
        for e in items:
            entry = {"forms": forms(e["word"]), "say": e["say"], "meaning": e.get("meaning", ""), "source": source}
            for f in entry["forms"]:
                by_form[f.lower()] = entry
    return list({id(e): e for e in by_form.values()}.values())


async def current() -> list[dict]:
    """The effective list for the business of this call, kept in memory for a minute so a call turn does not wait for the database."""
    bid = tenant.active_id() or ""
    hit = _CACHE.get(bid)
    if hit and time.monotonic() - hit[0] < _TTL:
        return hit[1]
    entries = await run_db(effective)
    _CACHE[bid] = (time.monotonic(), entries)
    return entries


def _pattern(entries: list[dict]):
    table, words = {}, []
    for e in entries:
        for f in e["forms"]:
            table[f.lower()] = e["say"]
            words.append(f)
    if not words:
        return None, table
    alt = "|".join(re.escape(w) for w in sorted(set(words), key=len, reverse=True))
    return re.compile(rf"(?<![A-Za-z0-9ऀ-ॿ])(?:{alt})(?![A-Za-z0-9ऀ-ॿ])", re.IGNORECASE), table


def apply(text: str, entries: list[dict]) -> str:
    """Replace each listed word with the way it should be said (used before text to speech)."""
    if not text or not entries:
        return text
    pat, table = _pattern(entries)
    return pat.sub(lambda m: table.get(m.group(0).lower(), m.group(0)), text) if pat else text


def stt_prompt(entries: list[dict], profile: dict | None = None, limit: int = 420) -> str:
    """A short list of words for the speech recogniser, so names and local words are heard right."""
    names = [profile.get(k, "") for k in ("business_name", "owner_name")] if profile else []
    custom = [e["say"] for e in entries if e["source"] != "built-in"]
    starter = [e["say"] for e in entries if e["source"] == "built-in"]
    out, size = [], 0
    for w in [n for n in names if n] + custom + starter:
        if w in out:
            continue
        if size + len(w) + 2 > limit:
            break
        out.append(w)
        size += len(w) + 2
    return ", ".join(out)


def local_words_block(entries: list[dict], limit: int = 30) -> str:
    """Words the platform or the owner explained, for the AI's prompt. The starter list is left out to keep the prompt short."""
    lines = [f"{e['forms'][0]} = {e['meaning']}" for e in entries if e["source"] != "built-in" and e["meaning"]][:limit]
    return "\n".join(lines) if lines else "(none listed)"
