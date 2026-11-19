"""Sending the sign-in code by SMS through Plivo.

India requires an SMS sender ID, a registered template and a registered entity (TRAI "DLT"). Set them on the server:
  MUNSHI_SMS_SENDER        the 6-letter sender ID registered for OTP
  MUNSHI_DLT_ENTITY_ID     your registered principal entity id
  MUNSHI_DLT_TEMPLATE_ID   the id of the approved OTP template
  MUNSHI_OTP_TEMPLATE      the exact approved wording, with {code} where the digits go
Plivo's own account (Auth ID and token) is the one already saved under Phone line in the portal.
"""
from __future__ import annotations

import logging
import os

import llm
from lab import settings_store
from lab.runner import run_db
from lab.service import ServiceError

DEFAULT_TEMPLATE = "{code} is your Munshi login code. It is valid for 10 minutes. Do not share it with anyone."


def configured() -> bool:
    return bool(os.getenv("MUNSHI_SMS_SENDER", "").strip())


async def send_otp(to: str, code: str) -> None:
    """Raises ServiceError when SMS is not set up or Plivo refuses, so the caller can tell the person honestly."""
    from . import service

    sender = os.getenv("MUNSHI_SMS_SENDER", "").strip()
    if not sender and os.getenv("MUNSHI_DEV_OTP_LOG") == "1":  # local testing only: no SMS goes out, the code is written to the server log
        logging.getLogger("munshi.sms").warning("DEV sign-in code for %s: %s", to, code)
        return
    if not sender:
        raise ServiceError("Sign-in by SMS is not switched on for this server yet. Please try again later.", 503)
    creds = await run_db(lambda s: settings_store.get_phone(s, service.SECRET_BOX))
    if not (creds["auth_id"] and creds["auth_token"]):
        raise ServiceError("Sign-in by SMS is not switched on for this server yet. Please try again later.", 503)
    body = {"src": sender, "dst": to.lstrip("+"), "text": os.getenv("MUNSHI_OTP_TEMPLATE", DEFAULT_TEMPLATE).format(code=code)}
    if os.getenv("MUNSHI_DLT_ENTITY_ID"):
        body["dlt_entity_id"] = os.getenv("MUNSHI_DLT_ENTITY_ID")
    if os.getenv("MUNSHI_DLT_TEMPLATE_ID"):
        body["dlt_template_id"] = os.getenv("MUNSHI_DLT_TEMPLATE_ID")
    try:
        r = await llm.http_client().post(f"https://api.plivo.com/v1/Account/{creds['auth_id']}/Message/", json=body, auth=(creds["auth_id"], creds["auth_token"]), timeout=15)
    except Exception as exc:  # noqa: BLE001
        raise ServiceError("The code could not be sent right now. Please try again.", 502) from exc
    if r.status_code >= 300:
        raise ServiceError("The code could not be sent right now. Please try again.", 502)
