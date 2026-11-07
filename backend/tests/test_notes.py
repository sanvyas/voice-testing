import pytest

from conftest import wait_for

API = "/api/lab"


def start(client, seeded):
    return client.post(f"{API}/live", json={"prompt_version_id": seeded["prod_version"]}).json()["id"]


def test_notes_while_live_record_where_in_the_call_they_were_written(client, seeded):
    cid = start(client, seeded)
    first = client.post(f"{API}/conversations/{cid}/notes", json={"body": "  Caller sounds tired from the start.  "})
    assert first.status_code == 201 and first.json()["body"] == "Caller sounds tired from the start." and first.json()["after_turn"] == 0
    client.post(f"{API}/live/{cid}/turns", json={"content": "I can't sleep."})  # user + assistant = 2 messages
    second = client.post(f"{API}/conversations/{cid}/notes", json={"body": "Reply was warm but asked two questions."}).json()
    assert second["after_turn"] == 2
    detail = client.get(f"{API}/conversations/{cid}").json()
    assert [n["body"] for n in detail["notes"]] == ["Caller sounds tired from the start.", "Reply was warm but asked two questions."]


def test_notes_after_the_call_and_in_the_call_log(client, seeded):
    cid = start(client, seeded)
    client.post(f"{API}/live/{cid}/turns", json={"content": "I feel flat."})
    client.post(f"{API}/live/{cid}/finish", json={"eval_set_id": seeded["evalset"]["id"]})
    wait_for(client, f"{API}/conversations/{cid}", lambda d: d["status"] == "completed")
    assert client.post(f"{API}/conversations/{cid}/notes", json={"body": "Scored pass but felt scripted."}).json()["after_turn"] == 2
    row = next(i for i in client.get(f"{API}/conversations?source=live").json()["items"] if i["id"] == cid)
    assert row["note_count"] == 1


def test_edit_and_delete_a_note(client, seeded):
    cid = start(client, seeded)
    nid = client.post(f"{API}/conversations/{cid}/notes", json={"body": "first draft"}).json()["id"]
    edited = client.put(f"{API}/notes/{nid}", json={"body": "better wording"}).json()
    assert edited["body"] == "better wording" and edited["after_turn"] == 0
    assert client.delete(f"{API}/notes/{nid}").status_code == 204
    assert client.get(f"{API}/conversations/{cid}").json()["notes"] == []
    assert client.delete(f"{API}/notes/{nid}").status_code == 404


@pytest.mark.parametrize("body", [{"body": ""}, {"body": "   "}, {"body": "x" * 2001}, {}, {"body": "ok", "after_turn": 5}])
def test_bad_notes_are_rejected(client, seeded, body):
    assert client.post(f"{API}/conversations/{start(client, seeded)}/notes", json=body).status_code == 422


def test_notes_for_a_missing_call_and_cascade_on_delete(client, seeded):
    assert client.post(f"{API}/conversations/nope/notes", json={"body": "hi"}).status_code == 404
    cid = start(client, seeded)
    client.post(f"{API}/live/{cid}/turns", json={"content": "hello"})
    client.post(f"{API}/live/{cid}/finish", json={"eval_set_id": seeded["evalset"]["id"]})
    wait_for(client, f"{API}/conversations/{cid}", lambda d: d["status"] == "completed")
    nid = client.post(f"{API}/conversations/{cid}/notes", json={"body": "gone with the call"}).json()["id"]
    assert client.delete(f"{API}/conversations/{cid}").status_code == 204
    assert client.put(f"{API}/notes/{nid}", json={"body": "x"}).status_code == 404
