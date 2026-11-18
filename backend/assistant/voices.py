"""Munshi's voice: four choices the owner can hear and pick. Each maps to a real Google Cloud voice for the language being spoken."""
from __future__ import annotations

import time

from lab.runner import run_db

VOICES = [
    {"id": "v1", "name": "Priya", "name_hi": "प्रिया", "gender": "F", "pick": 0, "desc": "Woman · calm and clear", "desc_hi": "महिला · शांत और साफ़"},
    {"id": "v2", "name": "Arjun", "name_hi": "अर्जुन", "gender": "M", "pick": 0, "desc": "Man · friendly", "desc_hi": "पुरुष · दोस्ताना"},
    {"id": "v3", "name": "Kavita", "name_hi": "कविता", "gender": "F", "pick": 1, "desc": "Woman · warm", "desc_hi": "महिला · गर्मजोशी वाली"},
    {"id": "v4", "name": "Rohan", "name_hi": "रोहन", "gender": "M", "pick": 1, "desc": "Man · slow and deep", "desc_hi": "पुरुष · धीमी और भारी"},
]
DEFAULT = "v1"
_BY_ID = {v["id"]: v for v in VOICES}
_CACHE: dict[str, tuple[float, str]] = {}


def get(voice_id: str | None) -> dict:
    return _BY_ID.get(voice_id or "", _BY_ID[DEFAULT])


def gender_of(voice_id: str | None) -> str:
    return get(voice_id)["gender"]


async def current() -> str:
    """The voice chosen by the business of this call. Kept in memory for a minute so a call turn does not wait for the database."""
    from . import service, tenant
    bid = tenant.active_id() or ""
    hit = _CACHE.get(bid)
    if hit and time.monotonic() - hit[0] < 60:
        return hit[1]
    vid = await run_db(lambda s: get(service.get_profile(s).get("voice"))["id"])
    _CACHE[bid] = (time.monotonic(), vid)
    return vid


def forget() -> None:
    _CACHE.clear()
