"""Every setting you can change must actually reach the model call that answers the person."""
import llm
from conftest import FakeLLM

API, V1 = "/api/lab", "/api/v1"


class Recorder(FakeLLM):
    def __init__(self):
        super().__init__()
        self.assistant_calls = []

    async def __call__(self, messages, *, provider=None, model=None, temperature=0.7, max_tokens=350, retries=2):
        if "role-playing a real person" not in messages[0]["content"] and "impartial evaluator" not in messages[0]["content"]:
            self.assistant_calls.append({"system": messages[0]["content"], "provider": provider, "model": model, "temperature": temperature, "max_tokens": max_tokens})
        return await super().__call__(messages, provider=provider, model=model, temperature=temperature, max_tokens=max_tokens, retries=retries)


def test_a_release_changes_every_client_prompt_variables_and_model_settings(env, monkeypatch):
    rec = Recorder(); monkeypatch.setattr(llm, "chat", rec)
    from fastapi.testclient import TestClient
    import main
    with TestClient(main.app) as c:
        pv = next(p for p in c.get(f"{API}/prompts").json() if p["name"] == "Parameterised therapist")["latest_version"]["id"]
        # change prompt text (new version) + variable + temperature + max tokens + model, then release
        v2 = c.post(f"{API}/prompts/{c.get(f'{API}/prompts').json()[0]['id']}/versions", json={"content": "You are {{assistant_name}}. Answer like a pirate. {{tone}}", "variable_defaults": {"assistant_name": "Sage", "tone": "calm"}}).json()
        r = c.post(f"{API}/deployments", json={"environment": "production", "prompt_version_id": v2["id"], "variables": {"assistant_name": "Juno", "tone": "playful"}, "temperature": 0.15, "max_tokens": 222, "provider": "groq", "model": "llama-3.3-70b-versatile", "confirm": True})
        assert r.status_code == 201, r.text
        key = c.post(f"{API}/api-keys", json={"name": "app", "environment": "production"}).json()["key"]
        sid = c.post(f"{V1}/sessions", json={}, headers={"Authorization": f"Bearer {key}"}).json()["session_id"]
        c.post(f"{V1}/sessions/{sid}/turns", json={"text": "hi"}, headers={"Authorization": f"Bearer {key}"})   # mobile app
        c.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})                                # original web app
    assert len(rec.assistant_calls) == 2
    for call in rec.assistant_calls:
        assert call["system"].startswith("You are Juno. Answer like a pirate. playful")   # new text + variables applied
        assert (call["temperature"], call["max_tokens"], call["provider"], call["model"]) == (0.15, 222, "groq", "llama-3.3-70b-versatile")


def test_an_open_session_keeps_the_prompt_it_started_with(env, monkeypatch):
    rec = Recorder(); monkeypatch.setattr(llm, "chat", rec)
    from fastapi.testclient import TestClient
    import main
    with TestClient(main.app) as c:
        p = c.get(f"{API}/prompts").json()[0]
        v1 = p["latest_version"]["id"]
        c.post(f"{API}/deployments", json={"environment": "production", "prompt_version_id": v1, "confirm": True})
        key = c.post(f"{API}/api-keys", json={"name": "app", "environment": "production"}).json()["key"]; h = {"Authorization": f"Bearer {key}"}
        sid = c.post(f"{V1}/sessions", json={}, headers=h).json()["session_id"]
        v2 = c.post(f"{API}/prompts/{p['id']}/versions", json={"content": "You are NEW."}).json()
        c.post(f"{API}/deployments", json={"environment": "production", "prompt_version_id": v2["id"], "confirm": True})
        c.post(f"{V1}/sessions/{sid}/turns", json={"text": "hi"}, headers=h)                       # the call already in progress
        sid2 = c.post(f"{V1}/sessions", json={}, headers=h).json()["session_id"]
        c.post(f"{V1}/sessions/{sid2}/turns", json={"text": "hi"}, headers=h)                      # the next person's call
    assert "You are NEW." not in rec.assistant_calls[0]["system"] and rec.assistant_calls[1]["system"].startswith("You are NEW.")
