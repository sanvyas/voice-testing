import csv
import os
import io

import pytest

from conftest import finish_run, wait_for

API = "/api/lab"


def start_run(client, seeded, scenario_moods=("anxious",), **over):
    body = {
        "prompt_version_id": seeded["prod_version"], "eval_set_id": seeded["evalset"]["id"],
        "scenario_ids": [seeded["scenarios"][m]["id"] for m in scenario_moods],
    }
    body.update(over)
    r = client.post(f"{API}/runs", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def conv_of(client, run):
    cid = run["conversations"][0]["id"]
    return client.get(f"{API}/conversations/{cid}").json()


# --- the main pipeline ---
def test_run_passes_end_to_end(client, seeded, fake):
    run = finish_run(client, start_run(client, seeded)["id"])
    assert run["status"] == "completed" and run["counts"]["passed"] == 1 and run["pass_rate"] == 100.0
    conv = conv_of(client, run)
    assert conv["verdict"] == "pass" and conv["score"] >= 75
    roles = [t["role"] for t in conv["turns"]]
    assert roles == ["user", "assistant"] * (len(roles) // 2) and len(roles) == 12  # 6 user turns x 2
    assert conv["turns"][0]["content"] == seeded["scenarios"]["anxious"]["opening_message"]
    assert all(t["latency_ms"] == 123 for t in conv["turns"] if t["role"] == "assistant")
    skipped = [r["key"] for r in conv["results"] if r["status"] == "skipped"]
    assert skipped == ["crisis_safety"]  # crisis-only parameter does not apply to an anxious caller
    assert conv["rendered_prompt"].startswith("You are a thoughtful")
    assert conv["avg_latency_ms"] == 123


def test_bad_judge_scores_cause_fail(client, seeded, fake):
    fake.judge_scores = {"Empathy": 1, "Mood attunement": 1}
    run = finish_run(client, start_run(client, seeded)["id"])
    conv = conv_of(client, run)
    assert conv["verdict"] == "fail" and "below the pass mark" in conv["verdict_reason"]
    assert run["counts"]["failed"] == 1 and run["pass_rate"] == 0.0


def test_required_parameter_failure_fails_despite_high_score(client, seeded, fake):
    fake.judge_scores = {"Honest about its role": 1}
    conv = conv_of(client, finish_run(client, start_run(client, seeded)["id"]))
    assert conv["verdict"] == "fail" and conv["score"] > 75
    assert "Honest about its role" in conv["verdict_reason"]


def test_crisis_scenario_applies_crisis_parameter(client, seeded, fake):
    fake.judge_scores = {"Crisis response": 1}
    conv = conv_of(client, finish_run(client, start_run(client, seeded, ("crisis",))["id"]))
    crisis = next(r for r in conv["results"] if r["key"] == "crisis_safety")
    assert crisis["status"] == "fail" and conv["verdict"] == "fail"


def test_rule_failures_come_from_the_actual_replies(client, seeded, fake):
    fake.assistant_reply = lambda m: "Here are tips:\n- breathe\n- sleep\nWhy? And when? **Try it**."
    conv = conv_of(client, finish_run(client, start_run(client, seeded)["id"]))
    status = {r["key"]: r["status"] for r in conv["results"]}
    assert status["no_markup"] == "fail" and status["one_question"] == "fail"
    assert status["spoken_length"] == "pass"


def test_variables_override_defaults_in_rendered_prompt(client, seeded, fake):
    run = start_run(client, seeded, prompt_version_id=seeded["param_version"], variables={"assistant_name": "Juno", "max_sentences": "2"})
    finish_run(client, run["id"])
    prompt = conv_of(client, client.get(f"{API}/runs/{run['id']}").json())["rendered_prompt"]
    assert "You are Juno, a warm and steady" in prompt and "at most 2 sentences" in prompt and "{{" not in prompt
    sent = fake.last_assistant_messages[0]["content"]
    assert sent.startswith(prompt) and "Conversation memory" in sent  # the lab prompt, then the shared memory instruction


def test_missing_and_unknown_variables_rejected(client, seeded):
    ver = client.post(f"{API}/prompts", json={"name": "v", "content": "Hi {{who}}"}).json()["versions"][0]["id"]
    body = {"prompt_version_id": ver, "eval_set_id": seeded["evalset"]["id"], "scenario_ids": [seeded["scenarios"]["sad"]["id"]]}
    r = client.post(f"{API}/runs", json=body)
    assert r.status_code == 422 and "who" in r.json()["detail"]
    r = client.post(f"{API}/runs", json={**body, "variables": {"who": "x", "extra": "y"}})
    assert r.status_code == 422 and "extra" in r.json()["detail"]
    assert client.post(f"{API}/runs", json={**body, "variables": {"who": "x"}}).status_code == 201


def test_scripted_scenario_is_deterministic_and_skips_simulator(client, seeded, fake):
    sc = client.post(f"{API}/scenarios", json={
        "name": "Scripted", "mood": "angry", "persona": "p", "opening_message": "Line one", "max_turns": 10,
        "scripted_turns": ["Line two", "Line three"]}).json()
    run = finish_run(client, start_run(client, seeded, ("sad",), scenario_ids=[sc["id"]])["id"])
    conv = conv_of(client, run)
    assert [t["content"] for t in conv["turns"] if t["role"] == "user"] == ["Line one", "Line two", "Line three"]
    assert fake.calls["simulator"] == 0


def test_simulator_can_end_the_call(client, seeded, fake):
    fake.user_lines = ["Okay.", "[END]"]
    conv = conv_of(client, finish_run(client, start_run(client, seeded)["id"]))
    assert len([t for t in conv["turns"] if t["role"] == "user"]) == 2


def test_provider_failure_marks_conversation_error_not_fail(client, seeded, fake):
    fake.fail_assistant = True
    run = finish_run(client, start_run(client, seeded)["id"])
    conv = conv_of(client, run)
    assert conv["status"] == "error" and conv["verdict"] == "error" and "boom" in conv["error"]
    assert run["counts"]["errored"] == 1 and run["pass_rate"] is None
    # and it can be retried once the provider recovers
    fake.fail_assistant = False
    r = client.post(f"{API}/conversations/{conv['id']}/reevaluate")
    assert r.status_code == 200
    again = wait_for(client, f"{API}/conversations/{conv['id']}", lambda d: d["status"] in ("completed", "error"))
    assert again["verdict"] == "pass" and len(again["turns"]) == 12  # regenerated from scratch, no duplicate turns


def test_judge_outage_yields_error_verdict(client, seeded, fake):
    fake.judge_raw = lambda m: "not json"
    conv = conv_of(client, finish_run(client, start_run(client, seeded)["id"]))
    assert conv["status"] == "completed" and conv["verdict"] == "error"


def test_repeats_and_run_limit(client, seeded, fake):
    run = start_run(client, seeded, ("anxious", "sad"), repeats=2)
    assert run["counts"]["total"] == 4
    finish_run(client, run["id"])
    r = client.post(f"{API}/runs", json={"prompt_version_id": seeded["prod_version"], "eval_set_id": seeded["evalset"]["id"],
                                         "scenario_ids": [s["id"] for s in seeded["scenarios"].values()], "repeats": 10})
    assert r.status_code == 422 and "limit" in r.json()["detail"]


def test_cancel_stops_pending_work(client, seeded, fake, env):
    env.setenv("LAB_MAX_CONCURRENCY", "1")
    fake.delay = 0.15
    run = start_run(client, seeded, tuple(seeded["scenarios"]))
    r = client.post(f"{API}/runs/{run['id']}/cancel")
    assert r.status_code == 200
    final = finish_run(client, run["id"], timeout=20)
    assert final["status"] == "cancelled"
    assert final["counts"]["cancelled"] >= 1 and final["counts"]["pending"] == 0
    assert client.post(f"{API}/runs/{run['id']}/cancel").status_code == 409


def test_cannot_delete_running_run_but_can_delete_finished(client, seeded, fake):
    fake.delay = 0.2
    run = start_run(client, seeded)
    assert client.delete(f"{API}/runs/{run['id']}").status_code == 409
    finish_run(client, run["id"], timeout=30)
    assert client.delete(f"{API}/runs/{run['id']}").status_code == 204
    assert client.get(f"{API}/runs/{run['id']}").status_code == 404
    assert client.get(f"{API}/conversations").json()["total"] == 0  # cascade


def test_history_filters_and_search(client, seeded, fake):
    fake.judge_scores = {"Empathy": 1, "Mood attunement": 1}
    finish_run(client, start_run(client, seeded, ("anxious",))["id"])
    fake.judge_scores = {}
    finish_run(client, start_run(client, seeded, ("sad", "angry"))["id"])
    q = lambda **p: client.get(f"{API}/conversations", params=p).json()  # noqa: E731
    assert q()["total"] == 3
    assert q(verdict="fail")["total"] == 1 and q(verdict="pass")["total"] == 2
    assert q(mood="sad")["total"] == 1 and q(source="live")["total"] == 0
    assert q(q="furious")["total"] == 1 and q(q="%")["total"] == 0  # wildcard is escaped
    assert q(limit=2)["total"] == 3 and len(q(limit=2)["items"]) == 2


def test_compare_runs_by_scenario(client, seeded, fake):
    a = finish_run(client, start_run(client, seeded, ("anxious", "sad"), name="A")["id"])
    fake.judge_scores = {"Empathy": 1, "Mood attunement": 1}
    b = finish_run(client, start_run(client, seeded, ("anxious", "sad"), name="B")["id"])
    cmp = client.get(f"{API}/runs/compare", params={"ids": f"{a['id']},{b['id']}"}).json()
    assert [r["name"] for r in cmp["runs"]] == ["A", "B"] and len(cmp["rows"]) == 2
    row = cmp["rows"][0]
    assert row["cells"][a["id"]]["passed"] == 1 and row["cells"][b["id"]]["failed"] == 1
    assert client.get(f"{API}/runs/compare", params={"ids": a["id"]}).status_code == 422


def test_csv_export_neutralises_formula_injection(client, seeded, fake):
    sc = client.post(f"{API}/scenarios", json={"name": "=HYPERLINK(\"http://evil\")", "mood": "sad", "persona": "p", "opening_message": "hi"}).json()
    run = finish_run(client, start_run(client, seeded, scenario_ids=[sc["id"]])["id"])
    r = client.get(f"{API}/runs/{run['id']}/export.csv")
    assert r.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(r.text)))
    assert rows[0][:5] == ["conversation_id", "title", "mood", "status", "verdict"] and "empathy" in rows[0]
    assert rows[1][1].startswith("'=HYPERLINK")


def test_stats(client, seeded, fake):
    finish_run(client, start_run(client, seeded, ("anxious", "sad"))["id"])
    s = client.get(f"{API}/stats").json()
    assert s["total"] == 2 and s["pass_rate"] == 100.0 and {m["key"] for m in s["by_mood"]} == {"anxious", "sad"}
    assert s["by_prompt"][0]["key"] == "A Space to Talk (production) v1" and len(s["trend"]) == 1


# --- snapshots keep history reproducible ---
def test_editing_scenario_and_rubric_does_not_rewrite_history(client, seeded, fake):
    run = finish_run(client, start_run(client, seeded)["id"])
    conv_before = conv_of(client, run)
    sc = seeded["scenarios"]["anxious"]
    client.put(f"{API}/scenarios/{sc['id']}", json={**{k: sc[k] for k in ("name", "mood", "persona", "behavior", "opening_message", "intensity", "max_turns", "scripted_turns", "variables", "tags")}, "opening_message": "changed"})
    es = seeded["evalset"]
    client.put(f"{API}/eval-sets/{es['id']}", json={"name": "x", "pass_threshold": 99, "params": [{"key": "a", "name": "A", "kind": "rule", "config": {"rule": "no_formatting"}}]})
    conv_after = client.get(f"{API}/conversations/{conv_before['id']}").json()
    assert conv_after["scenario"]["opening_message"] == sc["opening_message"]
    assert conv_after["evalset"]["pass_threshold"] == 75 and len(conv_after["results"]) == 12


# --- prompts / scenarios / rubric CRUD & validation ---
def test_prompt_versions_are_immutable_and_increment(client):
    p = client.post(f"{API}/prompts", json={"name": "P", "content": "Hello {{x}}", "variable_defaults": {"x": "1"}}).json()
    v2 = client.post(f"{API}/prompts/{p['id']}/versions", json={"content": "Hello {{x}} {{y}}", "note": "added y"}).json()
    assert v2["version"] == 2 and v2["variables"] == ["x", "y"]
    full = client.get(f"{API}/prompts/{p['id']}").json()
    assert [v["version"] for v in full["versions"]] == [2, 1] and full["versions"][1]["content"] == "Hello {{x}}"


def test_prompt_validation(client):
    r = client.post(f"{API}/prompts", json={"name": "P", "content": "Hello {{x}}", "variable_defaults": {"typo": "1"}})
    assert r.status_code == 422 and "typo" in r.text
    assert client.post(f"{API}/prompts", json={"name": "", "content": "x"}).status_code == 422
    assert client.post(f"{API}/prompts", json={"name": "P", "content": "x", "bogus": 1}).status_code == 422
    assert client.post(f"{API}/prompts", json={"name": "P", "content": "x", "variable_defaults": {"1bad": "v"}}).status_code == 422


def test_prompt_preview_and_archive(client):
    r = client.post(f"{API}/prompts/preview", json={"content": "A {{a}} {{b}}", "variables": {"a": "1"}}).json()
    assert r["variables"] == ["a", "b"] and r["missing"] == ["b"] and r["rendered"] == "A 1 {{b}}"
    p = client.post(f"{API}/prompts", json={"name": "Temp", "content": "x"}).json()
    assert client.delete(f"{API}/prompts/{p['id']}").status_code == 204
    assert p["id"] not in [x["id"] for x in client.get(f"{API}/prompts").json()]
    assert p["id"] in [x["id"] for x in client.get(f"{API}/prompts", params={"include_archived": True}).json()]
    assert client.post(f"{API}/prompts/{p['id']}/restore").json()["archived"] is False


def test_scenario_validation_and_normalisation(client):
    base = {"name": "S", "mood": "Very Anxious", "persona": "p", "opening_message": "hi"}
    s = client.post(f"{API}/scenarios", json=base).json()
    assert s["mood"] == "very_anxious"
    for bad in ({"intensity": 9}, {"max_turns": 0}, {"mood": "bad mood!"}, {"scripted_turns": [""]}, {"variables": {"a b": "x"}}):
        assert client.post(f"{API}/scenarios", json={**base, **bad}).status_code == 422, bad


def test_evalset_validation(client):
    ok = {"key": "a", "name": "A", "kind": "rule", "config": {"rule": "no_formatting"}}
    base = {"name": "E", "params": [ok]}
    assert client.post(f"{API}/eval-sets", json=base).status_code == 201
    cases = [
        {"params": []},
        {"params": [ok, ok]},  # duplicate keys
        {"params": [{**ok, "key": "Bad Key"}]},
        {"params": [{**ok, "config": {"rule": "unknown"}}]},
        {"params": [{**ok, "kind": "llm_judge", "config": {"criteria": "short"}}]},
        {"params": [{**ok, "kind": "llm_judge", "config": {"criteria": "long enough criteria", "min_score": 9}}]},
        {"params": [{**ok, "weight": 0}]},
        {"pass_threshold": 101},
    ]
    for case in cases:
        assert client.post(f"{API}/eval-sets", json={**base, **case}).status_code == 422, case


def test_evalset_update_replaces_params(client):
    es = client.post(f"{API}/eval-sets", json={"name": "E", "params": [{"key": "a", "name": "A", "kind": "rule", "config": {"rule": "no_formatting"}}]}).json()
    upd = client.put(f"{API}/eval-sets/{es['id']}", json={"name": "E2", "pass_threshold": 60, "params": [
        {"key": "a", "name": "A2", "kind": "rule", "config": {"rule": "max_words_per_reply", "max": 40}},
        {"key": "b", "name": "B", "kind": "llm_judge", "config": {"criteria": "Be kind and warm."}, "required": True}]})
    assert upd.status_code == 200
    body = upd.json()
    assert body["name"] == "E2" and [p["key"] for p in body["params"]] == ["a", "b"] and body["params"][1]["config"]["min_score"] == 4


# --- live voice sessions and imports ---
def test_live_session_flow(client, seeded, fake):
    s = client.post(f"{API}/live", json={"prompt_version_id": seeded["prod_version"], "scenario_id": seeded["scenarios"]["sad"]["id"]}).json()
    assert s["status"] == "live" and s["mood"] == "sad" and s["source"] == "live"
    t1 = client.post(f"{API}/live/{s['id']}/turns", json={"content": "I feel flat."}).json()
    t2 = client.post(f"{API}/live/{s['id']}/turns", json={"content": "Not sure why."}).json()
    assert (t1["user"]["idx"], t1["assistant"]["idx"], t2["user"]["idx"]) == (1, 2, 3)
    assert [m["role"] for m in fake.last_assistant_messages] == ["system", "user", "assistant", "user"]  # server-side history
    r = client.post(f"{API}/live/{s['id']}/finish", json={"eval_set_id": seeded["evalset"]["id"]})
    assert r.status_code == 200
    done = wait_for(client, f"{API}/conversations/{s['id']}", lambda d: d["status"] == "completed")
    assert done["verdict"] == "pass" and len(done["turns"]) == 4 and fake.calls["simulator"] == 0
    assert client.post(f"{API}/live/{s['id']}/turns", json={"content": "more"}).status_code == 409  # closed


def test_live_failed_turn_leaves_no_dangling_user_turn(client, seeded, fake):
    s = client.post(f"{API}/live", json={"prompt_version_id": seeded["prod_version"]}).json()
    fake.fail_assistant = True
    assert client.post(f"{API}/live/{s['id']}/turns", json={"content": "hello"}).status_code == 502
    fake.fail_assistant = False
    assert client.get(f"{API}/conversations/{s['id']}").json()["turns"] == []
    assert client.post(f"{API}/live/{s['id']}/turns", json={"content": "hello"}).json()["user"]["idx"] == 1


def test_live_finish_requires_a_reply(client, seeded):
    s = client.post(f"{API}/live", json={"prompt_version_id": seeded["prod_version"]}).json()
    r = client.post(f"{API}/live/{s['id']}/finish", json={"eval_set_id": seeded["evalset"]["id"]})
    assert r.status_code == 422


def test_import_transcript_is_evaluated(client, seeded, fake):
    body = {"title": "From prod", "mood": "angry", "eval_set_id": seeded["evalset"]["id"], "turns": [
        {"role": "user", "content": "I hate this."}, {"role": "assistant", "content": "I hear how angry you are. What happened?", "latency_ms": 900}]}
    c = client.post(f"{API}/conversations/import", json=body).json()
    done = wait_for(client, f"{API}/conversations/{c['id']}", lambda d: d["status"] == "completed")
    assert done["source"] == "imported" and done["verdict"] in ("pass", "fail")
    latency = next(r for r in done["results"] if r["key"] == "latency")
    assert latency["status"] == "pass"
    bad = {**body, "turns": [{"role": "assistant", "content": "x"}, {"role": "user", "content": "y"}]}
    assert client.post(f"{API}/conversations/import", json=bad).status_code == 422


def test_reevaluate_with_a_different_rubric(client, seeded, fake):
    conv = conv_of(client, finish_run(client, start_run(client, seeded)["id"]))
    strict = client.post(f"{API}/eval-sets", json={"name": "Strict", "pass_threshold": 90, "params": [
        {"key": "short", "name": "Very short", "kind": "rule", "config": {"rule": "max_words_per_reply", "max": 3}}]}).json()
    assert client.post(f"{API}/conversations/{conv['id']}/reevaluate", json={"eval_set_id": strict["id"]}).status_code == 200
    again = wait_for(client, f"{API}/conversations/{conv['id']}", lambda d: d["status"] == "completed")
    assert again["verdict"] == "fail" and [r["key"] for r in again["results"]] == ["short"] and again["evalset"]["name"] == "Strict"
    assert len(again["turns"]) == 12  # transcript untouched


def test_restart_recovery_requeues_interrupted_work(env, fake):
    from fastapi.testclient import TestClient
    import main
    from lab.db import session_scope
    from lab.models import Conversation, Turn

    with TestClient(main.app) as c:
        seeded_ids = {
            "v": c.get(f"{API}/prompts").json()[0]["latest_version"]["id"],
            "s": c.get(f"{API}/scenarios").json()[0]["id"],
            "e": c.get(f"{API}/eval-sets").json()[0]["id"],
        }
        run = c.post(f"{API}/runs", json={"prompt_version_id": seeded_ids["v"], "eval_set_id": seeded_ids["e"], "scenario_ids": [seeded_ids["s"]]}).json()
        finish_run(c, run["id"])
        cid = run["conversations"][0]["id"]
        # simulate a crash mid-generation: row stuck in 'running' with a half-written transcript
        with session_scope() as s:
            conv = s.get(Conversation, cid)
            conv.status, conv.verdict, conv.generated = "running", None, False
            for t in list(conv.turns)[2:]:
                s.delete(t)
    with TestClient(main.app) as c:  # restart
        d = wait_for(c, f"{API}/conversations/{cid}", lambda d: d["status"] == "completed")
        assert d["verdict"] == "pass" and len(d["turns"]) == 12
        assert c.get(f"{API}/runs/{run['id']}").json()["status"] == "completed"


# --- auth ---
def test_auth_required_when_tokens_configured(env, fake):
    from fastapi.testclient import TestClient
    import main
    token = "t" * 32
    env.setenv("LAB_API_TOKENS", f"{token},other-token-other-token-1234")
    with TestClient(main.app) as c:
        assert c.get(f"{API}/prompts").status_code == 401
        assert c.get(f"{API}/prompts", headers={"Authorization": "Bearer nope"}).status_code == 401
        assert c.get(f"{API}/prompts", headers={"Authorization": f"Bearer {token}"}).status_code == 200
        assert c.get(f"{API}/prompts", headers={"Authorization": "Bearer other-token-other-token-1234"}).status_code == 200
        assert c.get(f"{API}/prompts", headers={"Authorization": f"Basic {token}"}).status_code == 401
        assert c.get("/health").status_code == 200  # probes stay open
        assert c.get("/lab/").status_code == 200  # static shell has no data; API calls need the token


def test_failed_logins_are_throttled(env, fake):
    from fastapi.testclient import TestClient
    import main
    env.setenv("LAB_API_TOKENS", "t" * 32)
    with TestClient(main.app) as c:
        codes = [c.get(f"{API}/prompts", headers={"Authorization": "Bearer x"}).status_code for _ in range(12)]
        assert codes[:10] == [401] * 10 and codes[10:] == [429, 429]
        # even the right token is refused while throttled
        assert c.get(f"{API}/prompts", headers={"Authorization": "Bearer " + "t" * 32}).status_code == 429


def test_production_refuses_to_start_without_tokens(env, fake):
    from fastapi.testclient import TestClient
    import main
    env.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError, match="LAB_API_TOKENS"):
        with TestClient(main.app):
            pass
    env.setenv("LAB_API_TOKENS", "short")
    with pytest.raises(RuntimeError, match="24 characters"):
        with TestClient(main.app):
            pass
    env.setenv("LAB_API_TOKENS", "k" * 32)
    with TestClient(main.app) as c:
        assert c.get(f"{API}/prompts", headers={"Authorization": "Bearer " + "k" * 32}).status_code == 200
        cfg = c.get(f"{API}/config", headers={"Authorization": "Bearer " + "k" * 32}).json()
        assert cfg["storage"] == ("database" if os.getenv("TEST_DATABASE_URL") else "temporary")  # SQLite with no mounted disk is flagged


def test_security_headers(client):
    r = client.get("/lab/")
    assert "script-src 'self'" in r.headers["content-security-policy"] and r.headers["x-frame-options"] == "DENY"
    assert client.get(f"{API}/config").headers["cache-control"] == "no-store"


# --- the original app still works ---
def test_original_chat_endpoint_unchanged(client, fake):
    r = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200 and r.json() == {"reply": fake.assistant_reply(None), "provider": "Fake", "model": "fake-assistant"}
    from prompts import SYSTEM_PROMPT
    system = fake.last_assistant_messages[0]
    assert system["role"] == "system" and system["content"].startswith(SYSTEM_PROMPT) and "Conversation memory" in system["content"]
    assert client.post("/api/chat", json={"messages": [{"role": "assistant", "content": "hi"}]}).status_code == 400
    fake.fail_assistant = True
    assert client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]}).status_code == 502


def test_seed_matches_production_prompt(client):
    from prompts import SYSTEM_PROMPT
    prod = next(p for p in client.get(f"{API}/prompts").json() if p["name"].startswith("A Space to Talk"))
    assert prod["latest_version"]["content"] == SYSTEM_PROMPT


def test_seed_runs_once(env, fake):
    from fastapi.testclient import TestClient
    import main
    for _ in range(2):
        with TestClient(main.app) as c:
            assert len(c.get(f"{API}/scenarios").json()) == 8 and len(c.get(f"{API}/prompts").json()) == 2


def test_site_root_opens_the_lab_and_original_page_lives_at_app(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"] == "/lab/"
    assert "A space to talk" in client.get("/app").text
