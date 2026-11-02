"""The assistant must remember the whole conversation, like a person: a name given at the start is still known 20 exchanges later."""
from conftest import finish_run

import prompts
from prompts import CONTINUITY_NOTE, PINNED_OPENING, build_messages, fit_history

API, V1 = "/api/lab", "/api/v1"


def remembers(messages):
    """A stand-in model that only knows the name if the name is actually in the messages it was sent."""
    said = " ".join(m["content"] for m in messages if m["role"] == "user")
    asked = messages[-1]["content"].lower()
    if "what is my name" in asked:
        return "Your name is Priya." if "My name is Priya" in said else "Sorry, what was your name?"
    return "I hear you. Tell me more."


def m(role, text):
    return {"role": role, "content": text}


# --- the memory builder
def test_whole_conversation_is_sent_when_it_fits():
    history = [m("user" if i % 2 == 0 else "assistant", f"turn {i}") for i in range(300)]
    out = build_messages("PROMPT", history, "latest")
    assert [x["content"] for x in out[1:]] == [x["content"] for x in history] + ["latest"]  # nothing dropped, nothing reordered
    assert out[0]["role"] == "system" and out[0]["content"].startswith("PROMPT") and CONTINUITY_NOTE in out[0]["content"]


def test_very_long_conversations_keep_the_opening_and_the_latest_turns(monkeypatch):
    monkeypatch.setattr(prompts, "HISTORY_CHAR_BUDGET", 1000)
    history = [m("user" if i % 2 == 0 else "assistant", f"T{i:03d} " + "x" * 90) for i in range(100)]
    fitted, trimmed = fit_history(history + [m("user", "T100 latest")], budget=1000)
    texts = [x["content"][:4] for x in fitted]
    assert trimmed and texts[:PINNED_OPENING] == [f"T{i:03d}" for i in range(PINNED_OPENING)]  # the opening is protected
    assert fitted[-1]["content"] == "T100 latest" and fitted[-2]["content"].startswith("T099")  # and the newest turns
    assert sum(len(x["content"]) for x in fitted) <= 1000 + 100 and texts == sorted(texts)  # bounded, still in order
    assert fitted[PINNED_OPENING]["role"] == "user"  # resumes on a person's turn
    assert "left out" not in build_messages("P", history, "latest")[0]["content"]  # at the default budget this fits: no trim note
    big = build_messages("P", [m("user", "a" * 70_000), m("assistant", "b" * 10)], "latest")
    assert "left out" in big[0]["content"]


# --- every path sends the model the whole conversation
def test_lab_live_talk_remembers_the_name_after_many_turns(client, seeded, fake):
    fake.assistant_reply = remembers
    s = client.post(f"{API}/live", json={"prompt_version_id": seeded["prod_version"]}).json()
    client.post(f"{API}/live/{s['id']}/turns", json={"content": "Hi, My name is Priya."})
    for i in range(30):
        client.post(f"{API}/live/{s['id']}/turns", json={"content": f"Filler {i}"})
    r = client.post(f"{API}/live/{s['id']}/turns", json={"content": "What is my name?"}).json()
    assert r["assistant"]["content"] == "Your name is Priya."
    assert len(fake.last_assistant_messages) == 1 + 2 * 31 + 1  # system + 31 exchanges + the new question: nothing dropped


def test_mobile_api_session_remembers(client, seeded, fake):
    fake.assistant_reply = remembers
    client.post(f"{API}/deployments", json={"environment": "production", "prompt_version_id": seeded["prod_version"], "confirm": True})
    key = client.post(f"{API}/api-keys", json={"name": "ios", "environment": "production"}).json()["key"]
    h = {"Authorization": f"Bearer {key}"}
    sid = client.post(f"{V1}/sessions", json={"client": "ios"}, headers=h).json()["session_id"]
    client.post(f"{V1}/sessions/{sid}/turns", json={"text": "Hello, My name is Priya"}, headers=h)
    for i in range(40):
        client.post(f"{V1}/sessions/{sid}/turns", json={"text": f"Filler {i}"}, headers=h)
    assert client.post(f"{V1}/sessions/{sid}/turns", json={"text": "What is my name?"}, headers=h).json()["reply"] == "Your name is Priya."


def test_production_chat_endpoint_remembers_more_than_the_old_16_messages(client, fake):
    fake.assistant_reply = remembers
    msgs = [m("user", "My name is Priya")]
    for i in range(60):  # 120 messages: the old endpoint rejected >40 and trimmed to 16
        msgs += [m("assistant", "Go on."), m("user", f"Filler {i}")]
    msgs += [m("assistant", "Mm."), m("user", "What is my name?")]
    r = client.post("/api/chat", json={"messages": msgs})
    assert r.status_code == 200 and r.json()["reply"] == "Your name is Priya."


def test_simulated_test_runs_use_the_same_memory(client, seeded, fake):
    fake.assistant_reply = remembers
    sc = client.post(f"{API}/scenarios", json={
        "name": "Memory check", "mood": "calm", "persona": "p", "opening_message": "My name is Priya", "max_turns": 20,
        "scripted_turns": [f"Filler {i}" for i in range(18)] + ["What is my name?"]}).json()
    run = finish_run(client, client.post(f"{API}/runs", json={"prompt_version_id": seeded["prod_version"], "eval_set_id": seeded["evalset"]["id"], "scenario_ids": [sc["id"]]}).json()["id"])
    conv = client.get(f"{API}/conversations/{run['conversations'][0]['id']}").json()
    assert len(conv["turns"]) == 40 and conv["turns"][-1]["content"] == "Your name is Priya."
