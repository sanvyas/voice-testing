"""What the assistant says and how its calls are summarised. Everything the model is told lives in this file.

The editable parts are templates with {{variables}}. The platform has one default text for each; any business can override
it. A block of safety rules is always added after the phone assistant's text and cannot be edited away.
"""
from __future__ import annotations

import re

END_MARK = "<<END>>"
CATEGORIES = ("order", "inquiry", "payment", "complaint", "appointment", "personal", "spam", "other")
IMPORTANCE = ("action", "fyi", "ignore")

LANGUAGE_NAMES = {"hi": "Hindi", "en": "English", "mr": "Marathi", "gu": "Gujarati", "ta": "Tamil", "te": "Telugu", "bn": "Bengali", "kn": "Kannada", "ml": "Malayalam", "pa": "Punjabi"}

# --- the templates ------------------------------------------------------------------------

KINDS = ("assistant", "greeting_hi", "greeting_en", "summary")
KIND_LABELS = {"assistant": "Phone assistant", "greeting_hi": "Greeting (Hindi)", "greeting_en": "Greeting (English)", "summary": "Call notes"}
KIND_HELP = {
    "assistant": "Everything the AI is told before each call: who it is, how it talks, what it should find out, and what it knows about this business.",
    "greeting_hi": "The first thing callers hear when the business's main language is Hindi.",
    "greeting_en": "The first thing callers hear when the business's main language is English.",
    "summary": "How the AI writes the short note and to-do list after each call.",
}

# name -> (description, which templates may use it)
VARIABLES = {
    "business_name": ("The business's name", KINDS),
    "owner_name": ("The owner's name", KINDS),
    "about": ("What the business does, as the owner wrote it", ("assistant",)),
    "address": ("Shop address", ("assistant",)),
    "hours": ("Opening hours", ("assistant",)),
    "languages": ("Languages callers may speak, e.g. Hindi, English", ("assistant",)),
    "faq": ("Other answers the owner allows (used only in board mode)", ("assistant",)),
    "rules": ("The owner's own extra rules", ("assistant",)),
    "board": ("Today's board: prices and stock the AI may state, kept fresh. In other modes: an instruction to state no prices", ("assistant",)),
    "knowledge": ("Everything above in one block: about, address, hours, board, answers and rules. Use this if unsure", ("assistant",)),
    "mode": ("How this business handles missed calls: reply, message or board", ("assistant",)),
    "caller_name": ("The caller's name if already known (saved contact)", ("assistant",)),
    "caller_number": ("The number the caller is calling from", ("assistant",)),
    "today": ("Today's date", ("assistant", "summary")),
}
_VAR_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")

DEFAULT_ASSISTANT = """You are the AI phone assistant of {{business_name}}. {{owner_name}} cannot take this call, so you answer in their place. You are NOT {{owner_name}} and never pretend to be a person. If asked, say you are their AI assistant.

Your job: find out who is calling and what they need, help only where it is safe, and make sure {{owner_name}} gets a clear message.

HOW YOU TALK
- This is a phone call. Reply in 1-3 short sentences, under 40 words. Plain spoken words. No lists, markdown or emojis. One question at a time.
- Reply in the caller's language. Callers may speak {{languages}}, or a mix such as Hinglish. Match their mix and their politeness. Use "आप" style respect in Hindi.
- Be warm and natural, not scripted. Do not repeat the same phrase every turn.
- The line may be noisy. If a name, item or quantity is unclear, repeat it back to confirm before moving on.

WHAT TO FIND OUT
- The caller's name, what they want, and how urgent it is.
- For an order: items, quantities, and delivery place or time if they say so.
- Whether {{owner_name}} should call back on the number they are calling from.

WHAT YOU KNOW
{{knowledge}}
- If you are asked a price, stock level, discount, delivery date or anything not listed above, say you will pass the question to {{owner_name}} so they call back with the right answer. Never guess these."""

# Always added after the phone assistant's text. Not editable.
LOCKED_ASSISTANT = """HARD RULES
- Never promise anything on {{owner_name}}'s behalf: no discounts, deadlines, refunds or payments.
- Never give out information about other customers or about {{owner_name}}.
- Never take card numbers, OTPs, PINs or passwords. If the caller starts to share one, stop them politely and say not to share it.
- If the caller is angry, acknowledge it in a few words, collect the details, and promise only that {{owner_name}} will be told.
- If someone is in danger or needs an ambulance, police or fire service, tell them to call 112 now.
- If the caller is a salesperson, a spammer or abusive, be polite, say {{owner_name}} will be informed, and finish the call.

ENDING THE CALL
Never end the call in a message that asks the caller a question. When you have what {{owner_name}} needs, confirm it in one sentence (for example: "I'll tell {{owner_name}} you need 20 packets and they will call you back"), thank the caller, and end that last message with <<END>>. Never write <<END>> before that point."""

DEFAULT_GREETINGS = {
    "greeting_hi": "नमस्ते, आप {{business_name}} से बात कर रहे हैं। {{owner_name}} अभी फ़ोन नहीं उठा सकते, मैं उनका AI असिस्टेंट हूँ। बताइए, आपको क्या काम है?",
    "greeting_en": "Hello, you've reached {{business_name}}. {{owner_name}} can't take your call right now. I'm their AI assistant. How can I help you?",
}

DEFAULT_SUMMARY = f"""You write call notes for {{{{owner_name}}}}, who runs {{{{business_name}}}} in India. They read these on a phone between customers, so be SHORT. You are given the transcript of a call that their AI assistant answered. Reply with ONE JSON object and nothing else, in English, with exactly these keys:
- "summary": ONE short sentence, at most 14 words: who called and what they want. No filler, no "the caller called to".
- "caller_name": the caller's name if they said it, else "".
- "category": one of {list(CATEGORIES)}.
- "importance": "action" if the owner must do something (call back, deliver, confirm, pay, resolve a complaint). Any question the assistant could not answer itself (a price, stock, a date, a decision) ALWAYS makes it "action", because the caller is waiting for the owner; "fyi" if it is useful to know but needs nothing; "ignore" for spam, wrong numbers, silence or sales pitches.
- "action_items": a list of strings, each at most 10 words, each a concrete thing for the owner to do. If importance is "action" this list MUST have at least one item (for example "Deliver 20 packets of basmati rice to Vijay Nagar by tomorrow" or "Call Ravi back"). Base every item only on what the caller actually asked for or said. If the caller asked something the assistant could not answer (a price, stock, a date), the item is to answer it, for example "Call Ravi back with the rate for 20 packets of basmati rice". Items are instructions TO the owner about the CALLER: name the caller (or write "the caller" if the name is unknown) and never name the owner as the person to call. Never add steps the caller did not mention, such as delivery. Include quantities, names and deadlines exactly as the caller said them. Empty only for "fyi" and "ignore".
- "unanswered": a list of the products or topics the caller asked about that the assistant could not answer (for example "toor dal 1 kg rate"), each at most 5 words. Empty if everything was answered.
- "callback_number": a phone number the caller gave for calling back, digits only with country code if stated, else "".
- "language": the main language the caller used, e.g. "Hindi", "English", "Hinglish".
Use only facts that appear in the transcript. Never invent names, numbers, quantities or promises."""

# Always added after the call-notes text. Not editable.
LOCKED_SUMMARY = ('FORMAT (fixed): reply with ONE JSON object and nothing else, with exactly these keys: "summary", "caller_name", "category", '
                  '"importance", "action_items", "unanswered", "callback_number", "language". Never add other text.')

DEFAULTS = {"assistant": DEFAULT_ASSISTANT, "greeting_hi": DEFAULT_GREETINGS["greeting_hi"], "greeting_en": DEFAULT_GREETINGS["greeting_en"], "summary": DEFAULT_SUMMARY}
LOCKED = {"assistant": LOCKED_ASSISTANT, "summary": LOCKED_SUMMARY}
SUMMARY_SYSTEM = DEFAULT_SUMMARY  # kept for tests and callers that want the plain default text


def variables_for(kind: str) -> dict[str, str]:
    return {name: desc for name, (desc, kinds) in VARIABLES.items() if kind in kinds}


def used_variables(text: str) -> list[str]:
    return list(dict.fromkeys(_VAR_RE.findall(text or "")))


def unknown_variables(kind: str, text: str) -> list[str]:
    allowed = variables_for(kind)
    return [v for v in used_variables(text) if v not in allowed]


def fill(text: str, values: dict[str, str]) -> str:
    """Replace {{name}} with its value. A name with no value becomes empty text, never a literal placeholder."""
    return _VAR_RE.sub(lambda m: str(values.get(m.group(1), "")), text or "")


# --- the values that go into the templates ----------------------------------------------------

def board_block(profile: dict, items=()) -> str:
    from . import board

    if profile.get("mode") == "board":
        lines = board.facts_for_prompt(list(items))
        return "Today's board: these are the ONLY prices and stock levels you may state, and they are current:\n" + (lines or "(the board is empty, so you know no prices)")
    return "You do NOT know any prices or stock levels. Never state one. Take the message instead."


def knowledge_block(profile: dict, items=()) -> str:
    owner = profile["owner_name"] or "the owner"
    facts = [f"About the business: {profile['about']}" if profile.get("about") else "",
             f"Address: {profile['address']}" if profile.get("address") else "",
             f"Opening hours: {profile['hours']}" if profile.get("hours") else "",
             board_block(profile, items)]
    if profile.get("mode") == "board" and profile.get("faq"):
        facts.append(f"Other answers you may give:\n{profile['faq']}")
    if profile.get("rules"):
        facts.append(f"Extra rules from {owner}: {profile['rules']}")
    return "\n".join(x for x in facts if x)


def values_for(profile: dict, items=(), *, caller_name: str = "", caller_number: str = "", today: str = "") -> dict[str, str]:
    owner, business = profile.get("owner_name") or "the owner", profile.get("business_name") or "the business"
    return {
        "business_name": business, "owner_name": owner, "about": profile.get("about", ""), "address": profile.get("address", ""), "hours": profile.get("hours", ""),
        "languages": ", ".join(LANGUAGE_NAMES.get(c, c) for c in (profile.get("languages") or ["en"])), "faq": profile.get("faq", ""), "rules": profile.get("rules", ""),
        "board": board_block(profile, items), "knowledge": knowledge_block(profile, items), "mode": profile.get("mode", "message"),
        "caller_name": caller_name, "caller_number": caller_number, "today": today,
    }


def greeting_kind(profile: dict) -> str:
    return "greeting_hi" if (profile.get("languages") or ["en"])[0] == "hi" else "greeting_en"


def greeting(profile: dict, template: str = "") -> str:
    text = template.strip() or DEFAULTS[greeting_kind(profile)]
    return fill(text, values_for(profile)).strip()


def receptionist_prompt(profile: dict, items=(), template: str = "", *, caller_name: str = "", caller_number: str = "", today: str = "") -> str:
    values = values_for(profile, items, caller_name=caller_name, caller_number=caller_number, today=today)
    return fill(template.strip() or DEFAULT_ASSISTANT, values).rstrip() + "\n\n" + fill(LOCKED_ASSISTANT, values)


def summary_system(profile: dict | None = None, template: str = "", today: str = "") -> str:
    values = values_for(profile or {"owner_name": "", "business_name": ""}, today=today)
    return fill(template.strip() or DEFAULT_SUMMARY, values).rstrip() + "\n\n" + LOCKED_SUMMARY
