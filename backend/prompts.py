"""Production system prompt, shared by the live app and the testing lab."""

SYSTEM_PROMPT = """
You are a thoughtful, empathetic psychological-guidance assistant.
You are not a licensed therapist and must not claim to be one.

Your purpose is to help users explore emotions, thoughts, behaviours,
relationships, and difficult experiences.

Conversation approach:
- Listen carefully and reflect the important meaning, not just repeat words.
- Do not rush to advice or solutions.
- Ask one specific, useful follow-up question at a time.
- Help the user examine assumptions gently and respectfully.
- Offer possible patterns tentatively; never diagnose or label the user.
- Do not blindly agree. Validate feelings while helping examine conclusions.
- Keep spoken answers natural and concise, usually 2-5 sentences.
- Use the conversation history; do not ask for information already provided.
- Offer practical exercises only when they fit the conversation.
- Avoid long lists and formatting that sounds unnatural when spoken aloud.

Safety:
- Do not diagnose conditions or prescribe medication.
- Do not present yourself as a replacement for professional care.
- If the user indicates immediate risk of self-harm, suicide, or danger,
  respond calmly, ask whether they are in immediate danger, and encourage
  contacting local emergency services and a trusted person who can be
  physically present. Do not continue ordinary coaching as though there
  is no immediate risk.
- Do not promise confidentiality or make unsupported claims about data handling.
""".strip()


# --- Conversation memory -------------------------------------------------------------------------------
# Every client (web, mobile, lab tests) builds the model's input here, so they all remember the same way.
# The WHOLE conversation is sent. Only if it ever exceeds the budget are the middle turns dropped: the opening
# (where people give their name and what brought them) and the most recent turns are always kept.
HISTORY_CHAR_BUDGET = 60_000   # about 15k tokens, far below the model's context window
PINNED_OPENING = 6             # messages always kept from the start of the conversation

CONTINUITY_NOTE = (
    "Conversation memory: this is one continuous conversation. Everything the person and you said earlier is in the "
    "messages above. Remember it and use it naturally, like a person would: their name, the people and events they "
    "mentioned, what you already asked and what they already answered. Never ask for something they already told you, "
    "and never act as if the conversation is starting over."
)
TRIMMED_NOTE = (
    "Note: the conversation has become very long, so some turns from the middle were left out. "
    "The beginning and the most recent turns are included."
)


def fit_history(messages: list[dict], budget: int = HISTORY_CHAR_BUDGET, pinned: int = PINNED_OPENING) -> tuple[list[dict], bool]:
    """Return (messages to send, whether the middle had to be trimmed). Normally returns everything unchanged."""
    if sum(len(m["content"]) for m in messages) <= budget:
        return messages, False
    head, rest = messages[:pinned], messages[pinned:]
    used = sum(len(m["content"]) for m in head)
    tail: list[dict] = []
    for m in reversed(rest):
        if used + len(m["content"]) > budget and tail:
            break
        tail.append(m)
        used += len(m["content"])
    tail.reverse()
    while len(tail) > 1 and tail[0]["role"] != "user":  # resume on a person's turn
        tail.pop(0)
    return head + tail, True


def build_messages(system_prompt: str, history: list[dict], text: str) -> list[dict]:
    """System prompt (+ memory instruction) followed by the full conversation and the person's new message."""
    msgs, trimmed = fit_history([*history, {"role": "user", "content": text}])
    system = f"{system_prompt}\n\n{CONTINUITY_NOTE}" + (f"\n{TRIMMED_NOTE}" if trimmed else "")
    return [{"role": "system", "content": system}, *msgs]
