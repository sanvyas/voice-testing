"""The photo reader: turn a photo of a price list, shelf, handwritten rate board or purchase bill into board items.

It uses whichever model the owner picked in the portal (Groq or any OpenAI-compatible service such as OpenRouter) as the
"vision" role. The owner always reviews what it found before anything changes, because reading handwriting is not perfect.
"""
from __future__ import annotations

import base64
import json
import re
import struct
import zlib

import llm
from lab.service import ServiceError

from . import board

MAX_BYTES = 6 * 1024 * 1024
MIMES = {"image/jpeg", "image/png", "image/webp"}
DEFAULT_PROVIDER, DEFAULT_MODEL = "groq", "qwen/qwen3.8-27b"


def _tiny_png() -> str:
    """A valid 1x1 white PNG, built here so it can never be mistyped."""
    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff")) + chunk(b"IEND", b"")
    return base64.b64encode(png).decode()


TINY_PNG = _tiny_png()

INSTRUCTIONS = (
    "This photo is from a small shop in India: a price list, a handwritten rate board, a shelf with price tags, or a purchase bill. "
    "List every product you can read, with its selling price per unit if one is shown.\n"
    "Rules:\n"
    "- Copy product names as written (Hindi, English or mixed). Keep the size or unit in the name when shown, for example \"Basmati rice 5 kg\".\n"
    "- \"price\" is the number only, without currency. If no price is visible, leave it as an empty string.\n"
    "- Never guess or invent anything you cannot read. Skip unreadable lines.\n"
    "- If an item is marked sold out (khatam, out of stock), set \"status\" to \"sold_out\", otherwise \"in_stock\".\n"
    "Reply with ONLY a JSON array, for example: [{\"name\": \"Toor dal 1 kg\", \"price\": \"160\", \"status\": \"in_stock\"}]"
)


def which() -> tuple[str, str]:
    provider, model = llm.role("vision")
    return (provider or DEFAULT_PROVIDER, model or DEFAULT_MODEL) if provider else (DEFAULT_PROVIDER, __import__("os").getenv("VISION_MODEL", DEFAULT_MODEL))


def parse_items(raw: str) -> list[dict]:
    text = re.sub(r"^```(?:json)?|```$", "", (raw or "").strip(), flags=re.M).strip()
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        raise ValueError("no list in the model's reply")
    out, seen = [], set()
    for row in json.loads(text[start:end + 1]):
        if not isinstance(row, dict):
            continue
        name = re.sub(r"\s+", " ", str(row.get("name") or "")).strip()[:120]
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        price = re.sub(r"[^\d.,]", "", str(row.get("price") or ""))[:20]
        status = row.get("status") if row.get("status") in board.STATUSES else "in_stock"
        out.append({"name": name, "price": price, "status": status})
    return out[:80]


def _hint(message: str) -> str:
    low = message.lower()
    if any(w in low for w in ("image", "vision", "multimodal", "content", "unsupported")) or "http 400" in low or "http 404" in low:
        return message + " The photo reader model may not accept images. In the portal, open Integrations and pick a model that can read images."
    return message


async def read_image(image: bytes, mime: str) -> tuple[list[dict], str]:
    if mime not in MIMES:
        raise ServiceError("Send a JPEG, PNG or WebP photo.", 415)
    if not image or len(image) > MAX_BYTES:
        raise ServiceError("The photo is empty or larger than 6 MB.", 413)
    provider, model = which()
    url = f"data:{mime};base64,{base64.b64encode(image).decode()}"
    messages = [{"role": "user", "content": [{"type": "text", "text": INSTRUCTIONS}, {"type": "image_url", "image_url": {"url": url}}]}]
    try:
        result = await llm.chat(messages, provider=provider, model=model, temperature=0, max_tokens=3500, retries=1)
        return parse_items(result.reply), result.model
    except llm.LLMError as exc:
        raise ServiceError(_hint(str(exc).replace("All configured providers failed. ", "")), 502) from None
    except (ValueError, json.JSONDecodeError):
        raise ServiceError("The model's answer could not be read as a list of products. Try a clearer, closer photo.", 502) from None


async def selftest() -> dict:
    """Does the chosen model accept an image at all? (Says nothing about how well it reads handwriting.)"""
    provider, model = which()
    messages = [{"role": "user", "content": [{"type": "text", "text": "Reply with the single word: ok"}, {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{TINY_PNG}"}}]}]
    try:
        result = await llm.chat(messages, provider=provider, model=model, temperature=0, max_tokens=300, retries=0)
        return {"ok": True, "message": f"{provider} · {result.model} accepted an image in {result.latency_ms} ms.", "provider": provider, "model": model}
    except llm.LLMError as exc:
        return {"ok": False, "message": _hint(str(exc).replace("All configured providers failed. ", "")), "provider": provider, "model": model}
