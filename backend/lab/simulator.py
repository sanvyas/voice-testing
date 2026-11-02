"""The simulated caller: an LLM role-playing a person in a given mood."""
from __future__ import annotations

import re

import llm
from .config import Settings
from .templating import render, merge_values

END_TOKEN = "[END]"

SIM_SYSTEM = """You are role-playing a real person who is speaking out loud to a voice AI assistant. You are the PERSON, never the assistant.

Who you are and what is going on:
{persona}

Your mood: {mood} (intensity {intensity} out of 5; 1 is mild, 5 is extreme).
How you behave:
{behavior}

Rules:
- Speak the way people talk on a call: short, natural, sometimes unfinished. Usually 1-3 sentences.
- Stay in character and keep the mood realistic: let it shift only if the assistant genuinely earns it, not because it is polite.
- Never mention that you are an AI, a simulation, a test or a role-play. Never write stage directions or narration.
- React to what the assistant just said. Do not repeat your opening line.
- Output ONLY the words you say, with no quotes and no speaker label.
- If the conversation has reached a natural end (you feel done, or you hang up), reply with exactly {end}."""


def build_system(scenario: dict) -> str:
    values = merge_values(scenario.get("variables"))
    fill = lambda text: render(text or "", values, strict=False)  # noqa: E731
    return SIM_SYSTEM.format(
        persona=fill(scenario.get("persona", "")),
        mood=scenario.get("mood", "neutral"),
        intensity=scenario.get("intensity", 3),
        behavior=fill(scenario.get("behavior", "")) or "Behave naturally for this mood.",
        end=END_TOKEN,
    )


def build_messages(scenario: dict, turns: list[dict]) -> list[dict]:
    """The simulator sees the assistant as the 'user' of its chat and itself as the 'assistant'."""
    messages = [{"role": "system", "content": build_system(scenario)}, {"role": "user", "content": "(The call connects. Say what you would say.)"}]
    for turn in turns:
        messages.append({"role": "assistant" if turn["role"] == "user" else "user", "content": turn["content"]})
    return messages


def clean(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^(?:user|caller|person|me)\s*:\s*", "", text, flags=re.I)
    text = re.sub(r"^\s*\([^)]{0,80}\)\s*", "", text)  # leading stage direction
    text = re.sub(r"\*[^*\n]{1,60}\*", "", text)  # *sighs*
    text = text.strip().strip('"“”').strip()
    return text[:1000]


async def next_user_message(scenario: dict, turns: list[dict], settings: Settings) -> tuple[str | None, bool]:
    """Return ``(text, ended)``: what the caller says next (None if nothing) and whether they hang up after it."""
    provider, model = llm.role("simulator")
    result = await llm.chat(
        build_messages(scenario, turns),
        provider=provider,
        model=model,
        temperature=0.9,
        max_tokens=300,
    )
    ended = END_TOKEN in result.reply
    text = clean(result.reply.replace(END_TOKEN, ""))
    return (text or None), ended
