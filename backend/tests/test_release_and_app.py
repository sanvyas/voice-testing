import json
import os
import stat

import httpx
import pytest

import llm
from conftest import finish_run, wait_for

API, V1 = "/api/lab", "/api/v1"
GROQ_OK = {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}], "model": "openai/gpt-oss-20b", "usage": {}}
MODELS = {"data": [{"id": "openai/gpt-oss-20b"}, {"id": "llama-3.3-70b-versatile"}, {"id": "whisper-large-v3-turbo"}, {"id": "playai-tts"}]}


def groq_transport(seen=None, chat_status=200, chat_body=None, stt_text="I feel anxious today"):
    def handler(req: httpx.Request):
        if seen is not None:
            seen.append(req)
        if req.url.path.endswith("/models"):
            return httpx.Response(200, json=MODELS)
        if req.url.path.endswith("/audio/transcriptions"):
            return httpx.Response(200, json={"text": stt_text})
        if chat_status != 200:
            return httpx.Response(chat_status, json={"error": {"message": "Invalid API Key"}})
        return httpx.Response(200, json=chat_body or GROQ_OK)
    return httpx.MockTransport(handler)


@pytest.fixture
def prompt_ids(client):
    prompts = {p["name"]: p for p in client.get(f"{API}/prompts").json()}
    es = client.get(f"{API}/eval-sets").json()[0]["id"]
    sc = client.get(f"{API}/scenarios").json()
    return {"prod": prompts["A Space to Talk (production)"], "param": prompts["Parameterised therapist"], "es": es, "sc": [s["id"] for s in sc]}


def release(client, env, version_id, **over):
    return client.post(f"{API}/deployments", json={"environment": env, "prompt_version_id": version_id, **over})


def make_key(client, env="production", name="iOS app"):
    r = client.post(f"{API}/api-keys", json={"name": name, "environment": env})
    assert r.status_code == 201, r.text
    return r.json()


def hdr(key):
    return {"Authorization": f"Bearer {key['key']}"}


# --- provider credentials ---
def test_saving_a_groq_key_stores_it_encrypted_and_never_returns_it(real_client, tmp_path):
    seen = []
    llm.set_transport(groq_transport(seen))
    r = real_client.put(f"{API}/settings/providers/groq", json={"api_key": "  gsk_SECRET1234abcd \n", "model": "openai/gpt-oss-20b"})
    assert r.status_code == 200 and r.json()["warning"] == ""
    st = r.json()["provider"]
    assert st["configured"] and st["source"] == "ui" and st["key_hint"] == "…abcd" and "gsk_SECRET1234abcd" not in r.text
    assert "gsk_SECRET" not in real_client.get(f"{API}/settings/providers").text
    # ciphertext at rest
    from lab.db import session_scope
    from lab.models import Setting
    with session_scope() as s:
        stored = json.dumps(s.get(Setting, "provider.groq").value)
    assert "gsk_SECRET" not in stored and "key_enc" in stored
    key_file = tmp_path / "secret.key"
    if not os.getenv("TEST_DATABASE_URL"):  # SQLite mode: an owner-only key file is created next to the database
        assert key_file.exists() and stat.S_IMODE(key_file.stat().st_mode) == 0o600


def test_connection_test_reports_success_and_lists_models(real_client):
    llm.set_transport(groq_transport())
    real_client.put(f"{API}/settings/providers/groq", json={"api_key": "gsk_abcdefgh"})
    out = real_client.post(f"{API}/settings/providers/groq/test").json()
    assert out["ok"] and "answered" in out["message"]
    assert out["models"]["chat"] == ["llama-3.3-70b-versatile", "openai/gpt-oss-20b"] and out["models"]["stt"] == ["whisper-large-v3-turbo"]


def test_connection_test_explains_a_rejected_key(real_client):
    llm.set_transport(groq_transport(chat_status=401))
    real_client.put(f"{API}/settings/providers/groq", json={"api_key": "gsk_wrongwrong"})
    out = real_client.post(f"{API}/settings/providers/groq/test").json()
    assert not out["ok"] and "API key was rejected" in out["message"]
    assert real_client.post(f"{API}/settings/providers/sarvam/test").json()["ok"] is False  # nothing saved


def test_warns_on_unusual_groq_key_and_rejects_garbage(real_client):
    assert "gsk_" in real_client.put(f"{API}/settings/providers/groq", json={"api_key": "sk-abc123"}).json()["warning"]
    assert real_client.put(f"{API}/settings/providers/groq", json={"api_key": "two words"}).status_code == 422
    assert real_client.put(f"{API}/settings/providers/nope", json={"api_key": "x"}).status_code == 404


def test_saved_key_is_what_production_chat_uses_and_gpt_oss_gets_low_reasoning(real_client):
    seen = []
    llm.set_transport(groq_transport(seen))
    real_client.put(f"{API}/settings/providers/groq", json={"api_key": "gsk_live_key_1"})
    r = real_client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200 and r.json()["provider"] == "Groq"
    req = seen[-1]
    body = json.loads(req.content)
    assert req.headers["authorization"] == "Bearer gsk_live_key_1" and body["reasoning_effort"] == "low"
    assert body["model"] == "openai/gpt-oss-20b" and body["messages"][0]["role"] == "system"


def test_retries_without_reasoning_parameter_if_provider_rejects_it(real_client):
    calls = []

    def handler(req):
        body = json.loads(req.content)
        calls.append(body)
        if "reasoning_effort" in body:
            return httpx.Response(400, json={"error": {"message": "unsupported parameter: reasoning_effort"}})
        return httpx.Response(200, json=GROQ_OK)

    llm.set_transport(httpx.MockTransport(handler))
    real_client.put(f"{API}/settings/providers/groq", json={"api_key": "gsk_abcdefgh"})
    assert real_client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]}).status_code == 200
    assert ["reasoning_effort" in c for c in calls] == [True, False]


def test_empty_reply_from_exhausted_token_budget_has_a_useful_message(real_client):
    llm.set_transport(groq_transport(chat_body={"choices": [{"message": {"content": ""}, "finish_reason": "length"}]}))
    real_client.put(f"{API}/settings/providers/groq", json={"api_key": "gsk_abcdefgh"})
    r = real_client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 502 and "raise max tokens" in r.json()["detail"]


def test_env_key_works_and_is_reported_as_env(env):
    from fastapi.testclient import TestClient
    import main
    env.setenv("GROQ_API_KEY", "gsk_from_env_9999")
    with TestClient(main.app) as c:
        g = next(p for p in c.get(f"{API}/settings/providers").json() if p["id"] == "groq")
        assert g["configured"] and g["source"] == "env" and "9999" not in g["key_hint"]
    llm.set_runtime(None)


def test_removing_saved_key_falls_back_and_unreadable_key_is_flagged(real_client, tmp_path):
    real_client.put(f"{API}/settings/providers/groq", json={"api_key": "gsk_abcdefgh"})
    assert real_client.delete(f"{API}/settings/providers/groq/key").status_code == 204
    assert not next(p for p in real_client.get(f"{API}/settings/providers").json() if p["id"] == "groq")["configured"]
    real_client.put(f"{API}/settings/providers/groq", json={"api_key": "gsk_abcdefgh"})
    if os.getenv("TEST_DATABASE_URL"):
        os.environ["LAB_SECRET_KEY"] = "y" * 40  # simulate the encryption key changing
    else:
        (tmp_path / "secret.key").unlink()  # simulate losing the key file
    from fastapi.testclient import TestClient
    import main
    with TestClient(main.app) as c2:
        g = next(p for p in c2.get(f"{API}/settings/providers").json() if p["id"] == "groq")
        assert not g["configured"] and g["stored_key_unreadable"]
    llm.set_runtime(None)
    os.environ["LAB_SECRET_KEY"] = "x" * 40 if os.getenv("TEST_DATABASE_URL") else os.environ.get("LAB_SECRET_KEY", "")
    if not os.environ["LAB_SECRET_KEY"]:
        del os.environ["LAB_SECRET_KEY"]


def test_custom_base_url_validation(real_client):
    ok = real_client.put(f"{API}/settings/providers/custom", json={"base_url": "https://llm.example.com/v1/", "api_key": "k-123456", "model": "m"})
    assert ok.status_code == 200 and ok.json()["provider"]["base_url"] == "https://llm.example.com/v1"
    for bad in ("http://evil.example.com", "ftp://x", "https://169.254.169.254/v1", "not a url"):
        assert real_client.put(f"{API}/settings/providers/custom", json={"base_url": bad}).status_code == 422, bad


def test_roles_are_saved_and_used(real_client):
    r = real_client.put(f"{API}/settings/roles", json={"judge": {"provider": "groq", "model": "llama-3.3-70b-versatile"}, "stt": {"provider": "groq", "model": "whisper-large-v3"}})
    assert r.status_code == 200 and "llama-3.3-70b-versatile" in r.json()["judge"]["effective"]
    assert llm.role("judge") == ("groq", "llama-3.3-70b-versatile") and llm.role("stt") == ("groq", "whisper-large-v3")
    assert real_client.put(f"{API}/settings/roles", json={"stt": {"provider": "sarvam"}}).status_code == 422


def test_short_secret_key_refused_at_startup(env):
    from fastapi.testclient import TestClient
    import main
    env.setenv("LAB_SECRET_KEY", "too-short")
    with pytest.raises(RuntimeError, match="32 characters"):
        with TestClient(main.app):
            pass


# --- releases ---
def test_production_release_gate_and_staging_is_free(client, prompt_ids, fake):
    v = prompt_ids["prod"]["latest_version"]["id"]
    assert release(client, "staging", v).status_code == 201  # staging never blocks
    r = release(client, "production", v)
    assert r.status_code == 409 and "no completed test run" in r.json()["detail"]
    assert release(client, "production", v, confirm=True).status_code == 201
    # after a passing run the gate opens without confirmation
    finish_run(client, client.post(f"{API}/runs", json={"prompt_version_id": v, "eval_set_id": prompt_ids["es"], "scenario_ids": prompt_ids["sc"][:2]}).json()["id"])
    ok = release(client, "production", v, note="tested")
    assert ok.status_code == 201 and ok.json()["evidence"]["latest_pass_rate"] == 100.0
    # a failing run closes it again
    pv = prompt_ids["param"]["latest_version"]["id"]
    fake.judge_scores = {"Empathy": 1, "Mood attunement": 1}
    finish_run(client, client.post(f"{API}/runs", json={"prompt_version_id": pv, "eval_set_id": prompt_ids["es"], "scenario_ids": prompt_ids["sc"][:2]}).json()["id"])
    low = release(client, "production", pv)
    assert low.status_code == 409 and "below" in low.json()["detail"]


def test_release_validates_variables_and_environment(client, prompt_ids):
    pv = prompt_ids["param"]["latest_version"]["id"]
    assert release(client, "qa", pv).status_code == 422
    assert release(client, "staging", pv, variables={"nope": "x"}).status_code == 422
    assert release(client, "staging", pv, model="m").status_code == 422  # model needs provider


def test_only_newest_release_is_active_and_rollback_works(client, prompt_ids):
    pv = prompt_ids["param"]["latest_version"]["id"]
    a = release(client, "staging", pv, variables={"tone": "calm"}).json()
    b = release(client, "staging", pv, variables={"tone": "playful"}).json()
    act = client.get(f"{API}/deployments/active").json()
    assert act["staging"]["id"] == b["id"] and act["production"] is None
    assert [d["active"] for d in client.get(f"{API}/deployments", params={"environment": "staging"}).json()] == [True, False]
    release(client, "staging", pv, variables=a["variables"])  # rollback = promote the old settings again
    assert client.get(f"{API}/deployments/active").json()["staging"]["variables"]["tone"] == "calm"


def test_chat_endpoint_serves_the_released_prompt_and_settings(client, prompt_ids, fake):
    pv = prompt_ids["param"]["latest_version"]["id"]
    release(client, "production", pv, variables={"assistant_name": "Juno"}, temperature=0.2, max_tokens=120, confirm=True)
    assert client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]}).status_code == 200
    system = fake.last_assistant_messages[0]["content"]
    assert system.startswith("You are Juno, a warm and steady") and "{{" not in system


# --- client API ---
def test_v1_requires_a_valid_key(client):
    assert client.post(f"{V1}/sessions", json={}).status_code == 401
    assert client.post(f"{V1}/sessions", json={}, headers={"Authorization": "Bearer vtl_nope"}).status_code == 401
    assert client.get(f"{V1}/config", headers={"X-API-Key": "vtl_nope"}).status_code == 401
    k = make_key(client)
    assert k["key"].startswith("vtl_") and "key" not in client.get(f"{API}/api-keys").json()[0]
    assert client.get(f"{V1}/config", headers={"X-API-Key": k["key"]}).status_code == 200  # header alternative


def test_session_needs_a_release_then_replies_and_is_isolated_per_key(client, prompt_ids, fake):
    k1, k2 = make_key(client, name="ios"), make_key(client, name="android")
    r = client.post(f"{V1}/sessions", json={"client": "ios"}, headers=hdr(k1))
    assert r.status_code == 503 and "Promote" in r.json()["detail"]
    release(client, "production", prompt_ids["prod"]["latest_version"]["id"], confirm=True)
    assert client.get(f"{V1}/config", headers=hdr(k1)).json()["ready"] is True
    s = client.post(f"{V1}/sessions", json={"client": "ios", "user_ref": "u-42"}, headers=hdr(k1)).json()
    t1 = client.post(f"{V1}/sessions/{s['session_id']}/turns", json={"text": "I feel anxious."}, headers=hdr(k1)).json()
    t2 = client.post(f"{V1}/sessions/{s['session_id']}/turns", json={"text": "Mostly work."}, headers=hdr(k1)).json()
    assert t1["turn"] == 2 and t2["turn"] == 4 and t1["reply"] and t1["latency_ms"] == 123
    assert [m["role"] for m in fake.last_assistant_messages] == ["system", "user", "assistant", "user"]  # server keeps history
    # another app key cannot read, write or delete this session
    for call in (lambda: client.get(f"{V1}/sessions/{s['session_id']}", headers=hdr(k2)),
                 lambda: client.post(f"{V1}/sessions/{s['session_id']}/turns", json={"text": "x"}, headers=hdr(k2)),
                 lambda: client.delete(f"{V1}/sessions/{s['session_id']}", headers=hdr(k2))):
        assert call().status_code == 404
    tr = client.get(f"{V1}/sessions/{s['session_id']}", headers=hdr(k1)).json()
    assert [t["role"] for t in tr["turns"]] == ["user", "assistant"] * 2
    # visible in the lab's history with client info
    lab = client.get(f"{API}/conversations", params={"source": "app"}).json()["items"][0]
    assert (lab["client"], lab["environment"], lab["user_ref"], lab["status"]) == ("ios", "production", "u-42", "live")


def test_staging_and_production_keys_use_their_own_release(client, prompt_ids, fake):
    pv = prompt_ids["param"]["latest_version"]["id"]
    release(client, "staging", pv, variables={"assistant_name": "StagingBot"})
    release(client, "production", pv, variables={"assistant_name": "ProdBot"}, confirm=True)
    for env, name in (("staging", "StagingBot"), ("production", "ProdBot")):
        k = make_key(client, env)
        s = client.post(f"{V1}/sessions", json={}, headers=hdr(k)).json()
        client.post(f"{V1}/sessions/{s['session_id']}/turns", json={"text": "hello"}, headers=hdr(k))
        assert f"You are {name}," in fake.last_assistant_messages[0]["content"]


def test_lab_live_and_app_sessions_send_the_model_identical_requests(client, prompt_ids, fake):
    """The point of the shared core: same prompt + history + settings => same request, whatever the client."""
    pv = prompt_ids["param"]["latest_version"]["id"]
    vars_ = {"assistant_name": "Juno", "tone": "calm"}
    release(client, "production", pv, variables=vars_, temperature=0.4, max_tokens=200, confirm=True)
    lab = client.post(f"{API}/live", json={"prompt_version_id": pv, "variables": vars_, "temperature": 0.4, "max_tokens": 200}).json()
    k = make_key(client)
    app = client.post(f"{V1}/sessions", json={}, headers=hdr(k)).json()
    sent = []
    for text in ("I feel stuck.", "Work, mostly."):
        client.post(f"{API}/live/{lab['id']}/turns", json={"content": text})
        a = [m for m in fake.last_assistant_messages]
        client.post(f"{V1}/sessions/{app['session_id']}/turns", json={"text": text}, headers=hdr(k))
        sent.append((a, [m for m in fake.last_assistant_messages]))
    assert all(a == b for a, b in sent)


def test_finish_evaluates_only_when_an_app_rubric_is_configured(client, prompt_ids, fake):
    release(client, "production", prompt_ids["prod"]["latest_version"]["id"], confirm=True)
    k = make_key(client)

    def session():
        s = client.post(f"{V1}/sessions", json={"client": "android"}, headers=hdr(k)).json()["session_id"]
        client.post(f"{V1}/sessions/{s}/turns", json={"text": "I feel flat."}, headers=hdr(k))
        return s

    s1 = session()
    out = client.post(f"{V1}/sessions/{s1}/finish", headers=hdr(k)).json()
    assert out == {"session_id": s1, "status": "completed", "evaluating": False}
    assert client.get(f"{API}/conversations/{s1}").json()["verdict"] is None
    assert client.post(f"{V1}/sessions/{s1}/turns", json={"text": "more"}, headers=hdr(k)).status_code == 404  # closed
    assert client.put(f"{API}/settings/app", json={"eval_set_id": prompt_ids["es"]}).status_code == 200
    s2 = session()
    assert client.post(f"{V1}/sessions/{s2}/finish", headers=hdr(k)).json()["evaluating"] is True
    done = wait_for(client, f"{API}/conversations/{s2}", lambda d: d["status"] == "completed")
    assert done["verdict"] == "pass" and done["source"] == "app"
    assert client.get(f"{V1}/sessions/{s2}", headers=hdr(k)).json()["verdict"] == "pass"


def test_user_can_erase_their_session(client, prompt_ids):
    release(client, "production", prompt_ids["prod"]["latest_version"]["id"], confirm=True)
    k = make_key(client)
    s = client.post(f"{V1}/sessions", json={}, headers=hdr(k)).json()["session_id"]
    client.post(f"{V1}/sessions/{s}/turns", json={"text": "private"}, headers=hdr(k))
    assert client.delete(f"{V1}/sessions/{s}", headers=hdr(k)).status_code == 204
    assert client.get(f"{API}/conversations/{s}").status_code == 404


def test_revoked_key_stops_working_and_rate_limit_applies(client, prompt_ids, env):
    k = make_key(client)
    assert client.get(f"{V1}/config", headers=hdr(k)).status_code == 200
    client.delete(f"{API}/api-keys/{k['id']}")
    assert client.get(f"{V1}/config", headers=hdr(k)).status_code == 401


def test_rate_limit(env, fake):
    from fastapi.testclient import TestClient
    import main
    from lab import api_v1
    env.setenv("APP_RATE_LIMIT_PER_MIN", "3")
    api_v1.reset_rate_limits()
    with TestClient(main.app) as c:
        k = make_key(c)
        codes = [c.get(f"{V1}/config", headers=hdr(k)).status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]


def test_cors_only_for_configured_origins_and_only_on_v1(env, fake):
    from fastapi.testclient import TestClient
    import main
    env.setenv("APP_CORS_ORIGINS", "https://app.example.com")
    with TestClient(main.app) as c:
        k = make_key(c)
        ok = c.get(f"{V1}/config", headers={**hdr(k), "Origin": "https://app.example.com"})
        assert ok.headers["access-control-allow-origin"] == "https://app.example.com"
        assert "access-control-allow-origin" not in c.get(f"{V1}/config", headers={**hdr(k), "Origin": "https://evil.example"}).headers
        pre = c.options(f"{V1}/sessions", headers={"Origin": "https://app.example.com", "Access-Control-Request-Method": "POST"})
        assert pre.status_code == 204 and "Authorization" in pre.headers["access-control-allow-headers"]
        assert "access-control-allow-origin" not in c.get(f"{API}/config", headers={"Origin": "https://app.example.com"}).headers


# --- speech to text ---
def test_audio_turn_transcribes_then_replies(real_client, prompt_ids_real=None):
    seen = []
    llm.set_transport(groq_transport(seen, stt_text="  I feel anxious today "))
    real_client.put(f"{API}/settings/providers/groq", json={"api_key": "gsk_abcdefgh"})
    pv = real_client.get(f"{API}/prompts").json()[0]["latest_version"]["id"]
    real_client.post(f"{API}/deployments", json={"environment": "production", "prompt_version_id": pv, "confirm": True})
    k = make_key(real_client)
    sid = real_client.post(f"{V1}/sessions", json={"client": "ios"}, headers=hdr(k)).json()["session_id"]
    r = real_client.post(f"{V1}/sessions/{sid}/audio-turn", headers=hdr(k), data={"language": "en-IN"}, files={"file": ("clip.m4a", b"\x00fakeaudio", "audio/mp4")})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["transcript"] == "I feel anxious today" and out["reply"] == "ok" and not out["no_speech"]
    stt = next(q for q in seen if q.url.path.endswith("/audio/transcriptions"))
    assert stt.headers["authorization"] == "Bearer gsk_abcdefgh" and b'name="model"' in stt.content and b"whisper-large-v3-turbo" in stt.content
    assert b'name="language"' in stt.content and b"\r\n\r\nen\r\n" in stt.content  # en-IN -> en
    assert b"clip.m4a" in stt.content


def test_silent_audio_returns_no_speech_without_calling_the_model(real_client):
    chat_calls = []

    def handler(req):
        if req.url.path.endswith("/audio/transcriptions"):
            return httpx.Response(200, json={"text": "   "})
        chat_calls.append(1)
        return httpx.Response(200, json=GROQ_OK)

    llm.set_transport(httpx.MockTransport(handler))
    real_client.put(f"{API}/settings/providers/groq", json={"api_key": "gsk_abcdefgh"})
    pv = real_client.get(f"{API}/prompts").json()[0]["latest_version"]["id"]
    real_client.post(f"{API}/deployments", json={"environment": "production", "prompt_version_id": pv, "confirm": True})
    k = make_key(real_client)
    sid = real_client.post(f"{V1}/sessions", json={}, headers=hdr(k)).json()["session_id"]
    out = real_client.post(f"{V1}/sessions/{sid}/audio-turn", headers=hdr(k), files={"file": ("a.webm", b"x", "audio/webm")}).json()
    assert out["no_speech"] is True and out["reply"] is None and not chat_calls
    assert real_client.get(f"{V1}/sessions/{sid}", headers=hdr(k)).json()["turns"] == []


def test_stt_errors_are_clear(real_client):
    r = real_client.post(f"{API}/transcribe", files={"file": ("a.webm", b"x", "audio/webm")})
    assert r.status_code == 502 and "Groq" in r.json()["detail"]  # no provider connected
    llm.set_transport(groq_transport(chat_status=401))
    llm.set_transport(httpx.MockTransport(lambda req: httpx.Response(401, json={"error": {"message": "Invalid API Key"}})))
    real_client.put(f"{API}/settings/providers/groq", json={"api_key": "gsk_abcdefgh"})
    r = real_client.post(f"{API}/transcribe", files={"file": ("a.webm", b"x", "audio/webm")})
    assert r.status_code == 502 and "rejected" in r.json()["detail"]
    assert real_client.post(f"{API}/transcribe", files={"file": ("a.webm", b"", "audio/webm")}).status_code == 422


def test_release_evidence_only_counts_runs_with_the_same_variables(client, prompt_ids, fake):
    pv = prompt_ids["param"]["latest_version"]["id"]
    run = lambda vars_: finish_run(client, client.post(f"{API}/runs", json={"prompt_version_id": pv, "eval_set_id": prompt_ids["es"], "scenario_ids": prompt_ids["sc"][:2], "variables": vars_}).json()["id"])  # noqa: E731
    run({"tone": "calm"})  # passes
    ev = lambda vars_: client.post(f"{API}/deployments/evidence", json={"prompt_version_id": pv, "variables": vars_}).json()  # noqa: E731
    assert ev({"tone": "calm"})["latest_pass_rate"] == 100.0
    assert ev({"tone": "playful"})["tested"] is False  # same version, different variables: untested
    assert ev({})["tested"] is False  # defaults were never run either
    # so the gate blocks a production release of untested variables even though the version has a passing run
    assert release(client, "production", pv, variables={"tone": "playful"}).status_code == 409
    assert release(client, "production", pv, variables={"tone": "calm"}).status_code == 201
    # a failing experiment with other variables must not block the tested release
    fake.judge_scores = {"Empathy": 1, "Mood attunement": 1}
    run({"tone": "BLUNT"})
    fake.judge_scores = {}
    assert release(client, "production", pv, variables={"tone": "calm"}).status_code == 201
