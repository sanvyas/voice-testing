"""The owner's screens in the owner's language.

The AI writes call notes in English. When the app is in Hindi, summaries, to-dos, order items and the conversation are shown in
Hindi (Devanagari), and the other way round. Each translation is made once, kept with the call, and made when the call ends for
the owner's own language, so opening a call is instant. If a translation cannot be made, the original text is shown, never a blank.
"""
from __future__ import annotations

import json
import logging
import re

import llm
from lab.models import Call
from lab.runner import run_db
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import tenant

logger = logging.getLogger("ai_therapy.assistant.translate")
DEV = re.compile(r"[ऀ-ॿ]")
LAT = re.compile(r"[A-Za-z]")
TARGET = {"hi": "Hindi written in Devanagari, in the simple everyday words used in a shop. Common English words people use daily (order, delivery, address, WhatsApp) are written in Devanagari too",
          "en": "clear, simple English"}


def _wrong_script(text: str, lang: str) -> bool:
    if not text or not text.strip():
        return False
    return (not DEV.search(text) and bool(LAT.search(text))) if lang == "hi" else bool(DEV.search(text))


def _sources(c: Call, turns: bool = False) -> dict[str, str]:
    m = c.meta or {}
    out = {"summary": c.summary or "", "ask": m.get("ask", "")}
    for i, a in enumerate(c.action_items or []):
        out[f"a{i}"] = a.get("text", "")
    for i, k in enumerate(m.get("keep") or []):
        out[f"k{i}"] = k
    order = m.get("order") or {}
    for i, it in enumerate(order.get("items") or []):
        out[f"o{i}"] = it.get("name", "")
    out["when"] = order.get("when", "")
    if turns:
        for i, t in enumerate(c.turns):
            out[f"t{i}"] = t.content
    return out


def _tr(c: Call, lang: str) -> dict:
    return ((c.meta or {}).get("tr") or {}).get(lang) or {}


async def ensure(call_ids: list[str], lang: str, turns: bool = False) -> None:
    """Make (and keep) the missing translations for these calls. Never raises."""
    if lang not in TARGET or not call_ids:
        return
    try:
        def gather(session: Session):
            todo = []
            for c in session.scalars(select(Call).where(Call.id.in_(call_ids), Call.business_id == tenant.current())):
                have = _tr(c, lang)
                todo += [(c.id, k, text) for k, text in _sources(c, turns).items() if k not in have and _wrong_script(text, lang)]
            return todo
        todo = await run_db(gather)
        done: dict[tuple[str, str], str] = {}
        for i in range(0, len(todo), 40):
            chunk = todo[i:i + 40]
            prompt = (f"You translate short notes for a small shop owner in India into {TARGET[lang]}. Keep names, numbers, quantities, units and times exactly. "
                      "The input is a JSON array of strings. Reply with ONLY a JSON array of strings, the same length and order, nothing else.")
            result = await llm.chat([{"role": "system", "content": prompt}, {"role": "user", "content": json.dumps([t for _, _, t in chunk], ensure_ascii=False)}], temperature=0, max_tokens=2000, retries=1)
            raw = result.reply
            arr = json.loads(raw[raw.find("["): raw.rfind("]") + 1])
            if isinstance(arr, list) and len(arr) == len(chunk):
                for (cid, k, _), text in zip(chunk, arr):
                    if isinstance(text, str) and text.strip():
                        done[(cid, k)] = text.strip()[:600]
        if done:
            def save(session: Session):
                for cid in {c for c, _ in done}:
                    c = session.scalar(select(Call).where(Call.id == cid, Call.business_id == tenant.current()))
                    if c is not None:
                        meta = dict(c.meta or {})
                        tr = {**(meta.get("tr") or {})}
                        tr[lang] = {**(tr.get(lang) or {}), **{k: v for (i, k), v in done.items() if i == cid}}
                        meta["tr"] = tr
                        c.meta = meta
            await run_db(save)
    except Exception as exc:  # noqa: BLE001 - a missing translation must never break a screen
        logger.warning("translation to %s failed: %s", lang, str(exc)[:200])


def _apply_detail(c: Call, detail: dict, lang: str, turns: bool) -> dict:
    tr = _tr(c, lang)
    if not tr:
        return detail
    detail["summary"] = tr.get("summary", detail["summary"])
    detail["ask"] = tr.get("ask", detail.get("ask", ""))
    detail["action_items"] = [{**a, "text": tr.get(f"a{i}", a["text"])} for i, a in enumerate(detail["action_items"])]
    detail["keep"] = [tr.get(f"k{i}", k) for i, k in enumerate(detail.get("keep") or [])]
    order = detail.get("order") or {}
    if order.get("items"):
        detail["order"] = {**order, "items": [{**it, "name": tr.get(f"o{i}", it["name"])} for i, it in enumerate(order["items"])], "when": tr.get("when", order.get("when", ""))}
    if turns:
        detail["turns"] = [{**t, "content": tr.get(f"t{i}", t["content"])} for i, t in enumerate(detail["turns"])]
    return detail


async def localize_detail(call_id: str, detail: dict, lang: str, turns: bool = False) -> dict:
    await ensure([call_id], lang, turns)
    return await _detail_from_db(call_id, detail, lang, turns)


async def _detail_from_db(call_id: str, detail: dict, lang: str, turns: bool) -> dict:
    def run(session: Session):
        from . import service
        return _apply_detail(service.load_call(session, call_id), detail, lang, turns)
    return await run_db(run)


async def localize_people(data: dict, lang: str) -> dict:
    ids = [r["call_id"] for r in data["rows"]]
    await ensure(ids, lang)

    def run(session: Session):
        for r in data["rows"]:
            c = session.scalar(select(Call).where(Call.id == r["call_id"], Call.business_id == tenant.current()))
            tr = _tr(c, lang) if c is not None else {}
            r["summary"], r["ask"] = tr.get("summary", r["summary"]), tr.get("ask", r["ask"])
        return data
    return await run_db(run)


async def localize_thread(data: dict, lang: str) -> dict:
    ids = [i["id"] for i in data["items"] if i["type"] == "call"]
    await ensure(ids, lang)

    def run(session: Session):
        last_ask = None
        for it in data["items"]:
            if it["type"] != "call":
                continue
            c = session.scalar(select(Call).where(Call.id == it["id"], Call.business_id == tenant.current()))
            tr = _tr(c, lang) if c is not None else {}
            it["summary"], it["ask"] = tr.get("summary", it["summary"]), tr.get("ask", it["ask"])
            it["points"] = [tr.get(f"a{i}", p) for i, p in enumerate(it["points"])]
            if it["id"] in data["pending"]:
                last_ask = it["ask"]
        if last_ask:
            data["ask"] = last_ask
        return data
    return await run_db(run)
