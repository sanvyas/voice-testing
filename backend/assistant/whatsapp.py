"""The instant WhatsApp reply a caller gets after a missed call (Meta WhatsApp Cloud API).

A business may start a conversation only with an approved message template, so this sends one. The owner creates the
template once in Meta Business Manager; Setup shows the exact text to paste. Not yet tested against a live Meta account.
"""
from __future__ import annotations

import os
import re

import llm

from . import board as board_mod

GRAPH = "https://graph.facebook.com"
TEMPLATE_BODY = "Hi, this is {{1}}. We missed your call. {{2}} Reply here with what you need and we will get back to you."


def _one_line(text: str, limit: int) -> str:
    """Template variables may not hold line breaks, tabs or long runs of spaces."""
    return re.sub(r"\s+", " ", text or "").strip()[:limit]


def reply_details(profile: dict, items) -> str:
    parts = []
    if profile.get("address"):
        parts.append(f"Address: {profile['address']}.")
    if profile.get("hours"):
        parts.append(f"Hours: {profile['hours']}.")
    if profile.get("mode") != "message":  # in message mode the owner has chosen not to share prices
        today = board_mod.summary_for_reply(items)
        if today:
            parts.append(f"Today: {today}.")
    return " ".join(parts) or f"{profile.get('owner_name') or 'We'} will call you back soon."


def preview(profile: dict, items) -> str:
    """What the caller will read, for the Try-it screen."""
    business = profile.get("business_name") or "this business"
    return TEMPLATE_BODY.replace("{{1}}", _one_line(business, 80)).replace("{{2}}", _one_line(reply_details(profile, items), 900))


def to_wa_number(e164: str) -> str:
    return re.sub(r"\D", "", e164 or "")


async def send_reply(creds: dict, to_number: str, profile: dict, items) -> dict:
    """Send the template. Returns {"sent": bool, "error": str, "id": str}. Never raises."""
    if not (creds.get("access_token") and creds.get("phone_number_id")):
        return {"sent": False, "error": "WhatsApp is not connected.", "id": ""}
    to = to_wa_number(to_number)
    if len(to) < 8:
        return {"sent": False, "error": "No caller number to reply to.", "id": ""}
    body = {"messaging_product": "whatsapp", "to": to, "type": "template", "template": {
        "name": creds["template"], "language": {"code": creds["language"]},
        "components": [{"type": "body", "parameters": [
            {"type": "text", "text": _one_line(profile.get("business_name") or "the business", 80)},
            {"type": "text", "text": _one_line(reply_details(profile, items), 900)}]}]}}
    url = f"{GRAPH}/{os.getenv('WHATSAPP_GRAPH_VERSION', 'v21.0')}/{creds['phone_number_id']}/messages"
    try:
        response = await llm.http_client().post(url, headers={"Authorization": f"Bearer {creds['access_token']}"}, json=body)
        data = response.json() if response.content else {}
        if response.status_code >= 400:
            message = (data.get("error") or {}).get("message") or response.reason_phrase
            return {"sent": False, "error": f"WhatsApp: {message}"[:300], "id": ""}
        return {"sent": True, "error": "", "id": ((data.get("messages") or [{}])[0]).get("id", "")}
    except Exception as exc:  # noqa: BLE001 - a failed courtesy message must never break a call
        return {"sent": False, "error": f"WhatsApp: {str(exc)[:200]}", "id": ""}
