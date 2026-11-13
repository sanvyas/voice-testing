"""Today's board: the only prices and stock levels the assistant is allowed to state.

The owner keeps it current in a few seconds: tap a status, say "kaju katli khatam", or paste a price list.
Everything here is plain text matching. No model is involved, so an update can never be misread.
"""
from __future__ import annotations

import difflib
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lab.models import BoardItem
from lab.service import ServiceError, iso

STATUSES = ("in_stock", "sold_out", "ask")
STATUS_LABEL = {"in_stock": "in stock", "sold_out": "sold out", "ask": "ask the owner"}
MAX_ITEMS = 200

SOLD_OUT = ("sold out", "soldout", "out of stock", "khatam", "khatm", "khtm", "nahi hai", "nahin hai", "nahi h", "finished", "खत्म", "नहीं है", "ख़त्म")
IN_STOCK = ("back in stock", "in stock", "available", "aa gaya", "aa gayi", "aagaya", "aagayi", "stock mein", "mil raha", "mil rahi", "hai abhi", "आ गया", "आ गई", "उपलब्ध")
ASK = ("ask me", "puchh", "pooch", "पूछ")
FILLER = {"ka", "ki", "ke", "hai", "ho", "gaya", "gayi", "mark", "set", "now", "is", "are", "the", "a", "bhi", "abhi", "aur", "and", "please", "kar", "do", "dena", "kijiye"}


def item_out(i: BoardItem) -> dict:
    return {"id": i.id, "name": i.name, "price": i.price, "status": i.status, "updated_at": iso(i.updated_at)}


def list_items(session: Session) -> list[BoardItem]:
    return list(session.scalars(select(BoardItem).order_by(BoardItem.position, BoardItem.name)))


def board_out(session: Session) -> dict:
    items = list_items(session)
    latest = max((i.updated_at for i in items), default=None)
    return {"items": [item_out(i) for i in items], "updated_at": iso(latest), "sold_out": sum(1 for i in items if i.status == "sold_out")}


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
    if (session.scalar(select(func.count()).select_from(BoardItem)) or 0) >= MAX_ITEMS:
        raise ServiceError(f"The board holds up to {MAX_ITEMS} items.", 409)
    clash = session.scalar(select(BoardItem).where(func.lower(BoardItem.name) == name.lower()))
    if clash is not None:
        raise ServiceError(f"“{clash.name}” is already on the board.", 409)
    position = (session.scalar(select(func.max(BoardItem.position))) or 0) + 1
    item = BoardItem(name=name, price=clean_price(price), status=status, position=position)
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


def say(session: Session, text: str) -> dict:
    """"kaju katli khatam, toor dal aa gayi" -> updates. Anything it cannot place is reported back, never guessed."""
    items = list_items(session)
    changed, unmatched = [], []
    for clause in re.split(r"[,;\n]|\s+aur\s+|\s+and\s+", text or "", flags=re.I):
        clause = clause.strip()
        if not clause:
            continue
        status, rest = _status_of(clause)
        if status is None:
            unmatched.append(clause)
            continue
        item = _best_match(_tokens(rest), items)
        if item is None:
            unmatched.append(clause)
            continue
        item.status = status
        changed.append({"id": item.id, "name": item.name, "status": status})
    session.flush()
    return {"changed": changed, "unmatched": unmatched}


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
