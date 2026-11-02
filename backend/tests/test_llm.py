import httpx
import pytest

import llm


def ok_body(text="hello", model="m"):
    return {"choices": [{"message": {"content": text}}], "model": model, "usage": {"total_tokens": 3}}


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for k in ("GROQ_API_KEY", "SARVAM_API_KEY", "OPENAI_COMPAT_BASE_URL", "OPENAI_COMPAT_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(llm.asyncio, "sleep", lambda s: _noop())
    yield
    llm.set_transport(None)


async def _noop():
    return None


def route(handler):
    llm.set_transport(httpx.MockTransport(handler))


async def test_no_keys_is_a_clear_error():
    with pytest.raises(llm.LLMError, match="No LLM provider is connected"):
        await llm.chat([{"role": "user", "content": "x"}])


async def test_falls_back_from_groq_to_sarvam(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setenv("SARVAM_API_KEY", "s")
    seen = []

    def handler(req):
        seen.append(req.url.host)
        if "groq" in req.url.host:
            return httpx.Response(401, json={"error": "bad key"})
        assert req.headers["authorization"] == "Bearer s"
        return httpx.Response(200, json=ok_body("from sarvam", "sarvam-105b"))

    route(handler)
    res = await llm.chat([{"role": "user", "content": "x"}])
    assert (res.reply, res.provider) == ("from sarvam", "Sarvam") and seen == ["api.groq.com", "api.sarvam.ai"]


async def test_retries_transient_errors_then_succeeds(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "g")
    attempts = []

    def handler(req):
        attempts.append(1)
        return httpx.Response(429, headers={"retry-after": "1"}, json={}) if len(attempts) < 3 else httpx.Response(200, json=ok_body())

    route(handler)
    assert (await llm.chat([{"role": "user", "content": "x"}])).reply == "hello" and len(attempts) == 3


async def test_does_not_retry_client_errors_and_retries_zero_means_once(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "g")
    attempts = []
    route(lambda req: (attempts.append(1), httpx.Response(400, json={}))[1])
    with pytest.raises(llm.LLMError):
        await llm.chat([{"role": "user", "content": "x"}])
    assert len(attempts) == 1
    attempts.clear()
    route(lambda req: (attempts.append(1), httpx.Response(503, json={}))[1])
    with pytest.raises(llm.LLMError):
        await llm.chat([{"role": "user", "content": "x"}], retries=0)
    assert len(attempts) == 1


async def test_empty_reply_is_an_error(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "g")
    route(lambda req: httpx.Response(200, json=ok_body("   ")))
    with pytest.raises(llm.LLMError, match="empty"):
        await llm.chat([{"role": "user", "content": "x"}], retries=0)


async def test_explicit_provider_and_model_override(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setenv("SARVAM_API_KEY", "s")
    bodies = []

    def handler(req):
        import json
        bodies.append((req.url.host, json.loads(req.content)))
        return httpx.Response(200, json=ok_body())

    route(handler)
    await llm.chat([{"role": "user", "content": "x"}], provider="sarvam", model="custom-model", temperature=0.1, max_tokens=99)
    host, body = bodies[0]
    assert host == "api.sarvam.ai" and body["model"] == "custom-model" and body["temperature"] == 0.1 and body["max_tokens"] == 99
    with pytest.raises(llm.LLMError, match="requires an explicit provider"):
        await llm.chat([{"role": "user", "content": "x"}], model="m")
    with pytest.raises(llm.LLMError, match="not configured"):
        await llm.chat([{"role": "user", "content": "x"}], provider="custom")


async def test_custom_openai_compatible_provider(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPAT_BASE_URL", "https://llm.example.com/v1/")
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "k")
    monkeypatch.setenv("OPENAI_COMPAT_MODEL", "my-model")
    urls = []
    route(lambda req: (urls.append(str(req.url)), httpx.Response(200, json=ok_body()))[1])
    assert llm.configured_providers() == ["custom"]
    await llm.chat([{"role": "user", "content": "x"}])
    assert urls == ["https://llm.example.com/v1/chat/completions"]
