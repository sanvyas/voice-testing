"""OTP delivery: MSG91 (recommended for India — handles DLT), or Plivo (needs your own DLT registration).

Pick the provider with MUNSHI_OTP_PROVIDER (msg91 or plivo, default msg91).

MSG91 (recommended):
  MUNSHI_MSG91_AUTHKEY       your MSG91 authkey from msg91.com
  MUNSHI_MSG91_TEMPLATE_ID   the OTP template ID from MSG91's SendOTP section

Plivo (requires your own DLT registration):
  MUNSHI_SMS_SENDER          the 6-letter sender ID registered for OTP
  MUNSHI_DLT_ENTITY_ID       your registered principal entity id
  MUNSHI_DLT_TEMPLATE_ID     the id of the approved OTP template
  MUNSHI_OTP_TEMPLATE        the exact approved wording, with {code} where the digits go
"""
from __future__ import annotations

import logging
import os

import llm
from lab import settings_store
from lab.runner import run_db
from lab.service import ServiceError

DEFAULT_TEMPLATE = "{code} is your Munshi login code. It is valid for 10 minutes. Do not share it with anyone."


def provider() -> str:
    return os.getenv("MUNSHI_OTP_PROVIDER", "msg91").strip().lower()


def configured() -> bool:
    p = provider()
    if p == "msg91":
        return bool(os.getenv("MUNSHI_MSG91_AUTHKEY", "").strip())
    if p == "plivo":
        return bool(os.getenv("MUNSHI_SMS_SENDER", "").strip())
    return False


async def send_otp(to: str, code: str) -> None:
    """Raises ServiceError when SMS is not set up or the provider refuses."""
    p = provider()
    if p == "msg91":
        await _send_msg91(to, code)
    elif p == "plivo":
        await _send_plivo(to, code)
    else:
        raise ServiceError(f"Unknown OTP provider: {p}. Set MUNSHI_OTP_PROVIDER to msg91 or plivo.", 503)


async def _send_msg91(to: str, code: str) -> None:
    authkey = os.getenv("MUNSHI_MSG91_AUTHKEY", "").strip()
    template_id = os.getenv("MUNSHI_MSG91_TEMPLATE_ID", "").strip()

    if not authkey and os.getenv("MUNSHI_DEV_OTP_LOG") == "1":
        logging.getLogger("munshi.sms").warning("DEV sign-in code for %s: %s", to, code)
        return
    if not authkey:
        raise ServiceError("Sign-in by SMS is not set up yet. The MSG91 authkey is missing.", 503)
    if not template_id:
        raise ServiceError("Sign-in by SMS is not set up yet. The MSG91 template ID is missing.", 503)

    mobile = to.lstrip("+")
    body = {"template_id": template_id, "mobile": mobile, "otp": code}
    try:
        r = await llm.http_client().post(
            "https://control.msg91.com/api/v5/otp",
            headers={"authkey": authkey, "Content-Type": "application/json"},
            json=body,
            timeout=15,
        )
    except Exception as exc:  # noqa: BLE001
        raise ServiceError("The code could not be sent right now. Please try again.", 502) from exc
    if r.status_code >= 300:
        detail = ""
        try:
            detail = r.json().get("message", "")
        except Exception:  # noqa: BLE001
            pass
        logging.getLogger("munshi.sms").error("MSG91 error %s: %s", r.status_code, detail)
        raise ServiceError("The code could not be sent right now. Please try again.", 502)


async def _send_plivo(to: str, code: str) -> None:
    from . import service

    sender = os.getenv("MUNSHI_SMS_SENDER", "").strip()
    if not sender and os.getenv("MUNSHI_DEV_OTP_LOG") == "1":
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
