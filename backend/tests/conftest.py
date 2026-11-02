import json
import os
import re
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import llm  # noqa: E402
from lab import security  # noqa: E402


class FakeLLM:
    """Stands in for llm.chat. Distinguishes assistant / simulator / judge calls by their system prompt."""

    def __init__(self):
        self.calls = {"assistant": 0, "simulator": 0, "judge": 0}
        self.assistant_reply = lambda messages: "That sounds really heavy. What part of it is weighing on you most right now?"
        self.user_lines = ["It just keeps going round in my head.", "I can't switch it off at night.", "Maybe. I don't know.", "Thanks, that helps a bit."]
        self.judge_scores: dict[str, int] = {}  # substring of criterion name -> score
        self.default_judge_score = 5
        self.judge_raw = None  # override: function(messages)->str
        self.fail_assistant = False
        self.delay = 0.0
        self.last_assistant_messages = None

    async def __call__(self, messages, *, provider=None, model=None, temperature=0.7, max_tokens=350, retries=2):
        import asyncio

        system = messages[0]["content"]
        if self.delay:
            await asyncio.sleep(self.delay)
        if "role-playing a real person" in system:
            self.calls["simulator"] += 1
            n = sum(1 for m in messages if m["role"] == "assistant")  # lines already spoken by the caller
            line = self.user_lines[min(n - 1, len(self.user_lines) - 1)]
            return llm.LLMResult(line, "Fake", "fake-sim", 5)
        if "impartial evaluator" in system:
            self.calls["judge"] += 1
            if self.judge_raw:
                return llm.LLMResult(self.judge_raw(messages), "Fake", "fake-judge", 5)
            user = messages[-1]["content"] if messages[-1]["role"] == "user" else messages[1]["content"]
            crit = re.search(r"Criterion: (.+)", messages[1]["content"]).group(1)
            score = next((s for k, s in self.judge_scores.items() if k.lower() in crit.lower()), self.default_judge_score)
            quote = re.search(r"\] ASSISTANT: (.{10,40})", messages[1]["content"])
            return llm.LLMResult(
                json.dumps({"score": score, "reasoning": f"Scored {score} for {crit}.", "evidence": [quote.group(1) if quote else "x"]}),
                "Fake", "fake-judge", 5,
            )
        self.calls["assistant"] += 1
        self.last_assistant_messages = messages
        if self.fail_assistant:
            raise llm.LLMError("All configured providers failed. Fake: boom")
        return llm.LLMResult(self.assistant_reply(messages), "Fake", "fake-assistant", 123)


@pytest.fixture
def fake(monkeypatch):
    f = FakeLLM()
    monkeypatch.setattr(llm, "chat", f)
    return f


@pytest.fixture
def env(tmp_path, monkeypatch):
    for key in ("GROQ_API_KEY", "SARVAM_API_KEY", "OPENAI_COMPAT_BASE_URL", "OPENAI_COMPAT_API_KEY", "LAB_API_TOKENS", "JUDGE_PROVIDER", "JUDGE_MODEL"):
        monkeypatch.delenv(key, raising=False)
    pg = os.getenv("TEST_DATABASE_URL")
    if pg:  # run the whole suite on Postgres: start every test from an empty schema
        from sqlalchemy import create_engine, text
        from lab.config import normalize_database_url
        eng = create_engine(normalize_database_url(pg))
        with eng.begin() as c:
            c.execute(text("DROP SCHEMA public CASCADE")); c.execute(text("CREATE SCHEMA public"))
        eng.dispose()
        monkeypatch.setenv("DATABASE_URL", pg)
        monkeypatch.setenv("LAB_SECRET_KEY", "x" * 40)
    else:
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'lab.db'}")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("LAB_SEED_DEFAULTS", "true")
    security.reset_throttle()
    return monkeypatch


@pytest.fixture
def client(env, fake):
    from fastapi.testclient import TestClient

    import main

    with TestClient(main.app) as c:
        yield c


def wait_for(client, path, predicate, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = client.get(path).json()
        if predicate(data):
            return data
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting on {path}: {data}")


def finish_run(client, run_id, timeout=15):
    return wait_for(client, f"/api/lab/runs/{run_id}", lambda d: d["status"] in ("completed", "cancelled"), timeout)


@pytest.fixture
def seeded(client):
    """ids of the seeded objects keyed by name/mood."""
    prompts = {p["name"]: p for p in client.get("/api/lab/prompts").json()}
    scenarios = {s["mood"]: s for s in client.get("/api/lab/scenarios").json()}
    evalset = client.get("/api/lab/eval-sets").json()[0]
    return {
        "prod_version": prompts["A Space to Talk (production)"]["latest_version"]["id"],
        "param_version": prompts["Parameterised therapist"]["latest_version"]["id"],
        "scenarios": scenarios,
        "evalset": evalset,
    }


@pytest.fixture
def real_client(env):
    """App with the REAL llm module (no FakeLLM); tests route HTTP through llm.set_transport."""
    from fastapi.testclient import TestClient

    import main
    from lab import api_v1

    api_v1.reset_rate_limits()
    with TestClient(main.app) as c:
        yield c
    llm.set_transport(None)
    llm.set_runtime(None)
