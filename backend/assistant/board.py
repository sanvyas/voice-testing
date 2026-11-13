"""Today's board: the only prices and stock levels the assistant is allowed to state.

The owner keeps it current in a few seconds: tap a status, say "kaju katli khatam", or paste a price list.
Everything here is plain text matching. No model is involved, so an update can never be misread.
"""
from __future__ import annotations

import difflib
import re
from datetime import timedelta
from types import SimpleNamespace

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lab import settings_store
from lab.models import BoardItem, Call, utcnow
from lab.service import ServiceError, iso

from . import config, tenant

STATUSES = ("in_stock", "sold_out", "ask")
STATUS_LABEL = {"in_stock": "in stock", "sold_out": "sold out", "ask": "ask the owner"}
MAX_ITEMS = 200

SOLD_OUT = ("sold out", "soldout", "out of stock", "khatam", "khatm", "khtm", "nahi hai", "nahin hai", "nahi h", "finished", "खत्म", "नहीं है", "ख़त्म")
IN_STOCK = ("back in stock", "in stock", "available", "aa gaya", "aa gayi", "aagaya", "aagayi", "stock mein", "mil raha", "mil rahi", "hai abhi", "आ गया", "आ गई", "उपलब्ध")
ASK = ("ask me", "puchh", "pooch", "पूछ")
FILLER = {"ka", "ki", "ke", "hai", "ho", "gaya", "gayi", "mark", "set", "now", "is", "are", "the", "a", "bhi", "abhi", "aur", "and", "please", "kar", "do", "dena", "kijiye"}


def _aware(dt):
    return dt.replace(tzinfo=utcnow().tzinfo) if dt is not None and dt.tzinfo is None else dt


def _confirmed(i: BoardItem):
    return _aware(i.confirmed_at or i.updated_at)


def is_stale(i: BoardItem, stale_days: int) -> bool:
    return bool(stale_days) and i.status != "ask" and _confirmed(i) < utcnow() - timedelta(days=stale_days)


def item_out(i: BoardItem, stale_days: int = 0) -> dict:
    return {"id": i.id, "name": i.name, "price": i.price, "status": i.status, "updated_at": iso(i.updated_at), "confirmed_at": iso(_confirmed(i)), "stale": is_stale(i, stale_days)}


def list_items(session: Session) -> list[BoardItem]:
    return list(session.scalars(select(BoardItem).where(BoardItem.business_id == tenant.current()).order_by(BoardItem.position, BoardItem.name)))


def board_out(session: Session) -> dict:
    items = list_items(session)
    days = config.get_knowledge(session)["stale_days"]
    latest = max((_confirmed(i) for i in items), default=None)
    return {"items": [item_out(i, days) for i in items], "updated_at": iso(latest), "sold_out": sum(1 for i in items if i.status == "sold_out"),
            "stale": sum(1 for i in items if is_stale(i, days)), "stale_days": days}


def shareable(session: Session) -> list:
    """The board as the assistant may use it: anything not confirmed lately is treated as "ask the owner", so a price
    nobody has looked at for days is never quoted. This is what makes daily upkeep unnecessary."""
    days = config.get_knowledge(session)["stale_days"]
    return [SimpleNamespace(name=i.name, price=i.price, status="ask" if is_stale(i, days) else i.status) for i in list_items(session)]


def confirm_all(session: Session) -> int:
    """One tap: "everything on the board is still true"."""
    n = 0
    for i in list_items(session):
        if i.status != "ask":
            i.confirmed_at = utcnow()
            n += 1
    session.flush()
    return n


def clean_price(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    if re.fullmatch(r"[\d,]+(\.\d+)?", raw):
        return f"Rs {raw}"
    return re.sub(r"^(?:rs\.?|₹|inr)\s*", "Rs ", raw, flags=re.I)[:40]


def add_item(session: Session, name: str, price: str = "", status: str = "in_stock") -> BoardItem:
    name = re.sub(r"\s+", " ", name or "").strip()[:120]
    if not name:
        raise ServiceError("Give the item a name.", 422)
    if status not in STATUSES:
        raise ServiceError("Status must be in_stock, sold_out or ask.", 422)
    if (session.scalar(select(func.count()).select_from(BoardItem).where(BoardItem.business_id == tenant.current())) or 0) >= MAX_ITEMS:
        raise ServiceError(f"The board holds up to {MAX_ITEMS} items.", 409)
    clash = session.scalar(select(BoardItem).where(BoardItem.business_id == tenant.current(), func.lower(BoardItem.name) == name.lower()))
    if clash is not None:
        raise ServiceError(f"“{clash.name}” is already on the board.", 409)
    position = (session.scalar(select(func.max(BoardItem.position)).where(BoardItem.business_id == tenant.current())) or 0) + 1
    item = BoardItem(business_id=tenant.current(), name=name, price=clean_price(price), status=status, position=position, confirmed_at=utcnow())
    session.add(item)
    session.flush()
    return item


def parse_price_list(text: str) -> list[tuple[str, str]]:
    """Lines like "Basmati rice 5 kg - Rs 450", "Toor dal: 160" or just "Sugar". Returns [(name, price)]."""
    out = []
    for line in (text or "").splitlines():
        line = line.strip(" \t-•*·")
        if not line:
            continue
        m = re.match(r"^(?P<name>.+?)\s*(?:[:\-–—=]|\s)\s*(?:rs\.?|₹|inr)?\s*(?P<price>\d[\d,]*(?:\.\d+)?)\s*(?:/\s*\w+)?\s*$", line, flags=re.I)
        if m and not re.fullmatch(r"[\d\s.,]+", m.group("name")):
            out.append((m.group("name").strip(" :-–—="), m.group("price")))
        else:
            out.append((line, ""))
    return out


def import_items(session: Session, text: str) -> dict:
    added, skipped = 0, []
    for name, price in parse_price_list(text):
        try:
            add_item(session, name, price)
            added += 1
        except ServiceError as exc:
            skipped.append(f"{name}: {exc.message}")
    return {"added": added, "skipped": skipped}


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[\wऀ-ॿ]+", (text or "").lower()) if t not in FILLER]


def _status_of(clause: str) -> tuple[str | None, str]:
    """(status, the clause with the status words taken out)."""
    low = clause.lower()
    for status, words in (("sold_out", SOLD_OUT), ("in_stock", IN_STOCK), ("ask", ASK)):
        for w in sorted(words, key=len, reverse=True):
            if w in low:
                return status, re.sub(re.escape(w), " ", low)
    return None, low


def _best_match(name_tokens: list[str], items: list[BoardItem]) -> BoardItem | None:
    if not name_tokens:
        return None
    scored = []
    phrase = " ".join(name_tokens)
    for item in items:
        item_tokens = _tokens(item.name)
        if not item_tokens:
            continue
        overlap = len(set(name_tokens) & set(item_tokens)) / len(set(name_tokens))
        ratio = difflib.SequenceMatcher(None, phrase, " ".join(item_tokens)).ratio()
        scored.append((max(overlap * 0.9, ratio), item))
    scored.sort(key=lambda s: -s[0])
    if scored and scored[0][0] >= 0.6 and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.05):
        return scored[0][1]
    return None


PRICE_CUE = re.compile(r"(?:rs\.?|₹|inr|rupaye|rupees|rate|bhav|bhaw|@|ho gay|ho gaya|ho gayi|now|new)", re.I)
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
PRICE_FILLER = {"rs", "inr", "rupaye", "rupees", "rate", "bhav", "bhaw", "ho", "kar", "do", "now", "new", "update", "price", "daam", "kimat"}


def say(session: Session, text: str) -> dict:
    """"kaju katli khatam, toor dal 170 ho gayi" -> updates. Anything it cannot place is reported back, never guessed."""
    items = list_items(session)
    changed, unmatched = [], []
    for clause in re.split(r"[,;\n]|\s+aur\s+|\s+and\s+", text or "", flags=re.I):
        clause = clause.strip()
        if not clause:
            continue
        status, rest = _status_of(clause)
        numbers = NUMBER.findall(rest)
        price = ""
        if numbers and (status is None or PRICE_CUE.search(clause)):
            price = numbers[-1]
            rest = rest[: rest.rfind(price)] + " " + rest[rest.rfind(price) + len(price):]
        if status is None and not price:
            unmatched.append(clause)
            continue
        tokens = [t for t in _tokens(rest) if t not in PRICE_FILLER] if price else _tokens(rest)
        item = _best_match(tokens, items)
        if item is None:
            unmatched.append(clause)
            continue
        if status:
            item.status = status
        if price:
            item.price = clean_price(price)
            if not status and item.status == "ask":
                item.status = "in_stock"
        item.confirmed_at = utcnow()
        changed.append({"id": item.id, "name": item.name, "status": item.status, "price": item.price})
    session.flush()
    return {"changed": changed, "unmatched": unmatched}


def _norm(name: str) -> str:
    return " ".join(_tokens(name))


def find_existing(name: str, items: list[BoardItem]) -> BoardItem | None:
    """Strict match used for photos and bills, so a photo never silently overwrites the wrong item."""
    n = _norm(name)
    if not n:
        return None
    best, score = None, 0.0
    for i in items:
        r = difflib.SequenceMatcher(None, n, _norm(i.name)).ratio()
        if r > score:
            best, score = i, r
    return best if score >= 0.86 else None


def propose(session: Session, found: list[dict]) -> list[dict]:
    """Turn what the photo reader found into a list the owner can review: new items and price changes."""
    items = list_items(session)
    out = []
    for f in found:
        match = find_existing(f["name"], items)
        price = clean_price(f.get("price", ""))
        out.append({"name": f["name"], "price": price, "status": f.get("status") or "in_stock", "action": "update" if match else "new",
                    "existing_name": match.name if match else "", "old_price": match.price if match else "", "same": bool(match and match.price == price and match.status == (f.get("status") or "in_stock"))})
    return out


def apply_items(session: Session, wanted: list[dict]) -> dict:
    items = list_items(session)
    added = updated = 0
    for w in wanted[:MAX_ITEMS]:
        name = re.sub(r"\s+", " ", w.get("name", "")).strip()[:120]
        if not name:
            continue
        status = w.get("status") if w.get("status") in STATUSES else "in_stock"
        match = find_existing(name, items)
        if match:
            if w.get("price") not in (None, ""):
                match.price = clean_price(w["price"])
            match.status, match.confirmed_at = status, utcnow()
            updated += 1
        else:
            items.append(add_item(session, name, w.get("price", ""), status))
            added += 1
    session.flush()
    return {"added": added, "updated": updated}


# --- what callers asked that the board could not answer ---------------------------------



def asked_terms(session: Session, days: int = 30) -> list[dict]:
    items = list_items(session)
    dismissed = set(tenant.get(session, "dismissed", []) or [])
    counts: dict[str, dict] = {}
    since = utcnow() - timedelta(days=days)
    for call in session.scalars(select(Call).where(Call.business_id == tenant.current(), Call.started_at >= since, Call.status == "done")):
        for term in (call.meta or {}).get("unanswered", []):
            key = re.sub(r"\s+", " ", term.lower()).strip()
            if not key or key in dismissed or find_existing(key, items):
                continue
            row = counts.setdefault(key, {"term": term.strip(), "count": 0, "last_at": None})
            row["count"] += 1
            when = iso(call.started_at)
            row["last_at"] = max(filter(None, [row["last_at"], when]))
    return sorted(counts.values(), key=lambda r: (-r["count"], r["last_at"] or ""))[:20]


def dismiss_term(session: Session, term: str) -> None:
    current = list(tenant.get(session, "dismissed", []) or [])
    key = re.sub(r"\s+", " ", term.lower()).strip()
    if key and key not in current:
        tenant.put(session, "dismissed", (current + [key])[-200:])


def facts_for_prompt(items: list[BoardItem]) -> str:
    lines = []
    for i in items:
        if i.status == "in_stock":
            lines.append(f"- {i.name}: {i.price + ', ' if i.price else 'price: ask the owner, '}in stock")
        elif i.status == "sold_out":
            lines.append(f"- {i.name}: sold out today")
        else:
            lines.append(f"- {i.name}: do NOT state price or stock; take a message")
    return "\n".join(lines)


def summary_for_reply(items: list[BoardItem], limit: int = 8) -> str:
    """One line for the WhatsApp reply: what is on today's board."""
    shown = [i for i in items if i.status != "ask"][:limit]
    parts = [f"{i.name} {i.price}".strip() + (" (sold out)" if i.status == "sold_out" else "") for i in shown]
    return "; ".join(parts)


DEMO_BOARD = [("Basmati rice, 5 kg", "450", "in_stock"), ("Toor dal, 1 kg", "160", "in_stock"), ("Kaju katli, 1 kg", "900", "sold_out"), ("Sugar, 50 kg bag", "2150", "ask")]
