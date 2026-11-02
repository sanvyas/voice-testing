import pytest

import llm
from conftest import FakeLLM, finish_run

API, V1 = "/api/lab", "/api/v1"


class Recorder(FakeLLM):
    def __init__(self):
        super().__init__()
        self.model_calls = []

    async def __call__(self, messages, *, provider=None, model=None, temperature=0.7, max_tokens=350, retries=2):
        s = messages[0]["content"]
        if "role-playing a real person" not in s and "impartial evaluator" not in s:
            self.model_calls.append((temperature, max_tokens))
        return await super().__call__(messages, provider=provider, model=model, temperature=temperature, max_tokens=max_tokens, retries=retries)


# --- creativity and reply length
def test_defaults_then_saved_values(client):
    assert client.get(f"{API}/settings/generation").json() == {"temperature": 0.7, "max_tokens": 350}
    assert client.put(f"{API}/settings/generation", json={"temperature": 0.3, "max_tokens": 600}).json() == {"temperature": 0.3, "max_tokens": 600}
    assert client.get(f"{API}/settings/generation").json() == {"temperature": 0.3, "max_tokens": 600}


@pytest.mark.parametrize("body", [{"temperature": 2.5, "max_tokens": 350}, {"temperature": -0.1, "max_tokens": 350}, {"temperature": 0.7, "max_tokens": 10}, {"temperature": 0.7, "max_tokens": 5000}, {"temperature": 0.7}])
def test_invalid_values_are_rejected(client, body):
    assert client.put(f"{API}/settings/generation", json=body).status_code == 422


def test_saved_values_reach_tests_talk_and_releases(env, monkeypatch):
    rec = Recorder(); monkeypatch.setattr(llm, "chat", rec)
    from fastapi.testclient import TestClient
    import main
    with TestClient(main.app) as c:
        c.put(f"{API}/settings/generation", json={"temperature": 0.25, "max_tokens": 777})
        prompts = c.get(f"{API}/prompts").json(); pv = prompts[0]["latest_version"]["id"]
        sc = [s["id"] for s in c.get(f"{API}/scenarios").json()][:1]; es = c.get(f"{API}/eval-sets").json()[0]["id"]
        run = finish_run(c, c.post(f"{API}/runs", json={"prompt_version_id": pv, "eval_set_id": es, "scenario_ids": sc}).json()["id"])
        assert run["config"]["temperature"] == 0.25 and run["config"]["max_tokens"] == 777           # recorded with the test
        live = c.post(f"{API}/live", json={"prompt_version_id": pv}).json()
        c.post(f"{API}/live/{live['id']}/turns", json={"content": "hello"})                            # Talk
        dep = c.post(f"{API}/deployments", json={"environment": "staging", "prompt_version_id": pv}).json()
        assert (dep["gen"]["temperature"], dep["gen"]["max_tokens"]) == (0.25, 777)                    # releases
        # an explicit value on a request still wins over the saved setting
        c.post(f"{API}/live", json={"prompt_version_id": pv, "temperature": 1.1, "max_tokens": 120})
    assert rec.model_calls and all(call == (0.25, 777) for call in rec.model_calls)                                 # every model call used it


# --- sign-in off, on purpose
def test_open_access_removes_the_lab_sign_in_but_not_the_app_api_keys(env, fake):
    from fastapi.testclient import TestClient
    import main
    env.setenv("APP_ENV", "production")
    env.setenv("LAB_OPEN_ACCESS", "true")                      # no tokens at all: allowed because it was asked for
    with TestClient(main.app) as c:
        assert c.get(f"{API}/prompts").status_code == 200       # no token needed
        cfg = c.get(f"{API}/config").json()
        assert cfg["open_access"] is True and cfg["auth_required"] is False
        assert c.post(f"{V1}/sessions", json={}).status_code == 401   # the mobile API still needs its own key


def test_open_access_wins_even_if_a_token_is_still_configured_and_turning_it_off_restores_sign_in(env, fake):
    from fastapi.testclient import TestClient
    import main
    env.setenv("LAB_API_TOKENS", "t" * 32)
    env.setenv("LAB_OPEN_ACCESS", "true")
    with TestClient(main.app) as c:
        assert c.get(f"{API}/prompts").status_code == 200
    env.setenv("LAB_OPEN_ACCESS", "false")
    with TestClient(main.app) as c:
        assert c.get(f"{API}/prompts").status_code == 401
        cfg = c.get(f"{API}/config", headers={"Authorization": "Bearer " + "t" * 32}).json()
        assert cfg["auth_required"] is True and cfg["open_access"] is False


def test_production_still_refuses_to_start_unprotected_by_accident(env, fake):
    from fastapi.testclient import TestClient
    import main
    env.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError, match="LAB_OPEN_ACCESS"):
        with TestClient(main.app):
            pass
