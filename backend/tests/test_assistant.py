import asyncio
import base64
import json
import time

import httpx
import pytest
from plivo.utils.signature_v3 import construct_post_url, get_signature_v3

import llm
import tts
from assistant import phone, prompts, service

API = "/api/assistant"
LAB = "/api/lab"
SUMMARY = {"summary": "Ravi wants 20 packets of rice and a callback.", "caller_name": "Ravi", "category": "order", "importance": "action",
           "action_items": ["Call Ravi back about 20 packets of rice", "Confirm delivery for Friday"], "callback_number": "9876543210", "language": "Hinglish"}


class FakeAssistantLLM:
    """Stands in for llm.chat for the receptionist and the summary."""

    def __init__(self):
        self.replies = ["Sure, how many packets do you need?", "Got it. I'll tell the owner and they will call you back. <<END>>"]
        self.summary_raw = json.dumps(SUMMARY)
        self.calls = []
        self.fail = False

    async def __call__(self, messages, *, provider=None, model=None, temperature=0.7, max_tokens=350, retries=2):
        self.calls.append(messages)
        if self.fail:
            raise llm.LLMError("All configured providers failed. Fake: boom")
        if messages[0]["content"].startswith("You write call notes"):
            return llm.LLMResult(self.summary_raw, "Fake", "fake", 5, {"prompt_tokens": 400, "completion_tokens": 80})
        n = sum(1 for m in messages if m["role"] == "assistant")
        return llm.LLMResult(self.replies[min(n - 1, len(self.replies) - 1)] if n else self.replies[0], "Fake", "fake", 7, {"prompt_tokens": 500, "completion_tokens": 30})


@pytest.fixture
def ai(monkeypatch):
    f = FakeAssistantLLM()
    monkeypatch.setattr(llm, "chat", f)
    monkeypatch.setattr(llm, "configured_providers", lambda: ["groq"])
    return f


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for k in ("GOOGLE_TTS_API_KEY", "DEEPINFRA_API_KEY", "PUBLIC_BASE_URL"):
        monkeypatch.delenv(k, raising=False)
    yield
    llm.set_transport(None)
    tts.set_runtime(None)


def profile(client, **extra):
    body = {"business_name": "Sharma Traders", "owner_name": "Ramesh", "about": "Wholesale rice and pulses in Indore.", "faq": "Basmati rice: Rs 90/kg", "languages": ["en", "hi"], **extra}
    r = client.put(f"{API}/profile", json=body)
    assert r.status_code == 200, r.text
    return r.json()


# --- phone numbers, profile, contacts --------------------------------------------------

@pytest.mark.parametrize("raw,expected", [("9876543210", "+919876543210"), ("+91 98765 43210", "+919876543210"), ("09876543210", "+919876543210"), ("919876543210", "+919876543210"), ("+14155550123", "+14155550123")])
def test_phone_numbers_are_normalised(raw, expected):
    assert service.normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["", "12345", "abcdefghij", "1234567890", "+1"])
def test_bad_phone_numbers_are_refused(raw):
    with pytest.raises(Exception, match="not a valid phone number"):
        service.normalize_phone(raw)


def test_profile_is_saved_and_validated(client):
    assert client.get(f"{API}/profile").json()["assistant_on"] is True
    saved = profile(client, owner_phone="98765 43210")
    assert saved["owner_phone"] == "+919876543210" and client.get(f"{API}/profile").json()["business_name"] == "Sharma Traders"
    assert client.put(f"{API}/profile", json={"languages": ["xx"]}).status_code == 422
    assert client.put(f"{API}/profile", json={"owner_phone": "12"}).status_code == 422
    assert client.put(f"{API}/profile", json={"surprise": 1}).status_code == 422


def test_contacts_import_duplicates_and_always_ring(client):
    r = client.post(f"{API}/contacts/import", json={"text": "Ravi, 9876543210\n8765432109, Sunita\nbad line here\n+91 98765 43210"}).json()
    assert r["added"] == 2 and len(r["skipped"]) == 2
    contacts = {c["name"]: c for c in client.get(f"{API}/contacts").json()}
    assert contacts["Sunita"]["phone"] == "+918765432109" and contacts["Ravi"]["always_ring"] is True
    assert client.post(f"{API}/contacts", json={"name": "Dup", "phone": "9876543210"}).status_code == 409
    cid = contacts["Ravi"]["id"]
    assert client.put(f"{API}/contacts/{cid}", json={"always_ring": False}).json()["always_ring"] is False
    assert client.delete(f"{API}/contacts/{cid}").status_code == 204


# --- a call from start to summary --------------------------------------------------------

def test_a_full_call_is_answered_summarised_and_listed(client, ai):
    profile(client)
    start = client.post(f"{API}/calls", json={"caller_number": "98765 43210"}).json()
    cid = start["call"]["id"]
    assert not start["routed_to_owner"] and "AI assistant" in start["greeting"] and "Sharma Traders" in start["greeting"]
    t1 = client.post(f"{API}/calls/{cid}/turns", json={"content": "Namaste, mujhe chawal chahiye", "audio_seconds": 6}).json()
    assert t1["assistant"]["content"].startswith("Sure") and not t1["ended"]
    system = ai.calls[0][0]["content"]
    assert "Sharma Traders" in system and "Basmati rice: Rs 90/kg" in system and "Never guess" in system and "Conversation memory" in system
    t2 = client.post(f"{API}/calls/{cid}/turns", json={"content": "20 packets please, call me back"}).json()
    assert t2["ended"] and "<<END>>" not in t2["assistant"]["content"]
    done = client.post(f"{API}/calls/{cid}/end").json()
    assert (done["status"], done["importance"], done["category"], done["caller_name"]) == ("done", "action", "order", "Ravi")
    assert [a["text"] for a in done["action_items"]][0].startswith("Call Ravi back") and all(not a["done"] for a in done["action_items"])
    assert done["callback_number"] == "+919876543210" and done["language"] == "Hinglish"
    assert [t["role"] for t in done["turns"]] == ["assistant", "caller", "assistant", "caller", "assistant"]
    assert done["cost"]["currency"] == "INR" and done["cost"]["ai"] > 0 and done["cost"]["speech_to_text"] > 0
    assert client.post(f"{API}/calls/{cid}/turns", json={"content": "hello?"}).status_code == 409
    assert client.post(f"{API}/calls/{cid}/end").json()["summary"] == done["summary"]  # finishing twice is harmless
    listing = client.get(f"{API}/calls?importance=action").json()
    assert listing["total"] == 1 and listing["items"][0]["open_actions"] == 2
    assert client.get(f"{API}/stats").json()["needs_action"] == 1


def test_ticking_off_every_action_marks_the_call_dealt_with(client, ai):
    profile(client)
    cid = client.post(f"{API}/calls", json={}).json()["call"]["id"]
    client.post(f"{API}/calls/{cid}/turns", json={"content": "I need rice"})
    call = client.post(f"{API}/calls/{cid}/end").json()
    first, second = call["action_items"]
    assert client.put(f"{API}/calls/{cid}/actions/{first['id']}", json={"done": True}).json()["reviewed"] is False
    assert client.put(f"{API}/calls/{cid}/actions/{second['id']}", json={"done": True}).json()["reviewed"] is True
    assert client.get(f"{API}/stats").json()["needs_action"] == 0
    assert client.put(f"{API}/calls/{cid}/actions/nope", json={"done": True}).status_code == 404


def test_a_bad_summary_never_loses_the_call(client, ai):
    profile(client)
    cid = client.post(f"{API}/calls", json={}).json()["call"]["id"]
    client.post(f"{API}/calls/{cid}/turns", json={"content": "I need rice"})
    ai.summary_raw = "I am sorry, I cannot do that."
    done = client.post(f"{API}/calls/{cid}/end").json()
    assert done["status"] == "done" and done["importance"] == "action" and "failed" in done["summary_error"] and len(done["turns"]) == 3


def test_a_call_that_needs_action_always_has_something_to_do(client, ai):
    profile(client)
    cid = client.post(f"{API}/calls", json={}).json()["call"]["id"]
    client.post(f"{API}/calls/{cid}/turns", json={"content": "I need rice"})
    ai.summary_raw = json.dumps({**SUMMARY, "action_items": []})
    done = client.post(f"{API}/calls/{cid}/end").json()
    assert done["importance"] == "action" and [a["text"] for a in done["action_items"]] == ["Follow up: " + SUMMARY["summary"]]


def test_a_practice_call_needs_the_business_to_be_described_first(client, ai):
    r = client.post(f"{API}/calls", json={})
    assert r.status_code == 409 and "business name" in r.json()["detail"]


def test_summary_json_is_cleaned_and_bad_values_are_repaired():
    s = service.parse_summary('```json\n{"summary": "x", "category": "weird", "importance": "urgent", "action_items": ["a", "", 5], "language": "Hindi"}\n```')
    assert (s.category, s.importance, s.action_items) == ("other", "fyi", ["a", "5"])


def test_a_caller_who_says_nothing_is_not_worth_the_owners_time(client, ai):
    profile(client)
    cid = client.post(f"{API}/calls", json={}).json()["call"]["id"]
    done = client.post(f"{API}/calls/{cid}/end").json()
    assert done["importance"] == "ignore" and "without saying anything" in done["summary"] and len(ai.calls) == 0


def test_a_model_failure_saves_nothing_and_the_caller_can_try_again(client, ai):
    profile(client)
    cid = client.post(f"{API}/calls", json={}).json()["call"]["id"]
    ai.fail = True
    assert client.post(f"{API}/calls/{cid}/turns", json={"content": "hello"}).status_code == 502
    ai.fail = False
    assert len(client.get(f"{API}/calls/{cid}").json()["turns"]) == 1
    assert client.post(f"{API}/calls/{cid}/turns", json={"content": "hello"}).status_code == 200


def test_always_ring_contacts_are_not_answered_by_the_assistant(client, ai):
    profile(client)
    client.post(f"{API}/contacts", json={"name": "Mummy", "phone": "9000000001"})
    start = client.post(f"{API}/calls", json={"caller_number": "9000000001"}).json()
    assert start["routed_to_owner"] and start["greeting"] == "" and start["call"]["handled_by"] == "owner" and start["call"]["caller_name"] == "Mummy"
    assert client.post(f"{API}/calls/{start['call']['id']}/turns", json={"content": "hi"}).status_code == 409
    assert client.get(f"{API}/calls").json()["total"] == 0  # the assistant's list only holds calls it handled
    assert client.get(f"{API}/stats").json()["rang_you_7d"] == 1


def test_switching_the_assistant_off_or_having_no_ai_key_is_explained(client, ai, monkeypatch):
    profile(client, assistant_on=False)
    r = client.post(f"{API}/calls", json={})
    assert r.status_code == 409 and "switched off" in r.json()["detail"]
    profile(client)
    monkeypatch.setattr(llm, "configured_providers", lambda: [])
    r = client.post(f"{API}/calls", json={})
    assert r.status_code == 409 and "AI key" in r.json()["detail"]


def test_a_very_long_call_is_wrapped_up(client, ai):
    profile(client)
    cid = client.post(f"{API}/calls", json={}).json()["call"]["id"]
    for _ in range(service.MAX_TURNS // 2 - 1):
        client.post(f"{API}/calls/{cid}/turns", json={"content": "and another thing"})
    last = client.post(f"{API}/calls/{cid}/turns", json={"content": "one more"}).json()
    assert last["ended"] and "Wrap it up now" in ai.calls[-1][0]["content"]


def test_notes_on_calls_live_and_afterwards(client, ai):
    profile(client)
    cid = client.post(f"{API}/calls", json={}).json()["call"]["id"]
    n1 = client.post(f"{API}/calls/{cid}/notes", json={"body": "  Greeting sounded stiff.  "}).json()
    assert n1["body"] == "Greeting sounded stiff." and n1["after_turn"] == 1
    client.post(f"{API}/calls/{cid}/turns", json={"content": "I need rice"})
    client.post(f"{API}/calls/{cid}/end")
    n2 = client.post(f"{API}/calls/{cid}/notes", json={"body": "Summary was right."}).json()
    assert n2["after_turn"] == 3
    assert client.put(f"{API}/call-notes/{n1['id']}", json={"body": "Greeting was fine."}).json()["body"] == "Greeting was fine."
    assert client.get(f"{API}/calls").json()["items"][0]["note_count"] == 2
    assert client.delete(f"{API}/call-notes/{n2['id']}").status_code == 204
    assert [n["body"] for n in client.get(f"{API}/calls/{cid}").json()["notes"]] == ["Greeting was fine."]
    assert client.post(f"{API}/calls/{cid}/notes", json={"body": " "}).status_code == 422
    assert client.delete(f"{API}/calls/{cid}").status_code == 204 and client.put(f"{API}/call-notes/{n1['id']}", json={"body": "x"}).status_code == 404


def test_the_prompt_never_lets_the_assistant_invent_or_take_secrets():
    p = prompts.receptionist_prompt({**service.DEFAULT_PROFILE, "owner_name": "Ramesh", "business_name": "Sharma Traders", "faq": "Rice Rs 90"})
    for must in ("AI assistant", "Never guess", "Never promise", "OTPs", "112", prompts.END_MARK):
        assert must in p
    assert "Rice Rs 90" in p and "Hindi" in p


def test_cost_estimate_adds_up(client, ai):
    from lab.models import Call
    c = Call(source="phone", duration_s=95, meta={"stt_s": 60, "llm_in": 10000, "llm_out": 500, "tts_chars": 800, "tts_engine": "google"})
    cost = service.estimate_cost(c)
    assert cost["phone"] == pytest.approx(4 * 0.38 / 2, abs=0.01)  # 95 s = 4 half-minute steps
    assert cost["voice"] == pytest.approx(800 * 4 / 1e6 * 95, abs=0.001) and cost["total"] == pytest.approx(sum(cost[k] for k in ("speech_to_text", "ai", "voice", "phone")), abs=0.01)


def test_status_says_what_is_missing(client, ai):
    s = client.get(f"{API}/status").json()
    assert s["ai_ready"] and not s["profile_ready"] and not s["phone"]["connected"] and s["voice"]["engine"] == "device"
    assert s["webhooks"]["answer"].endswith("/telephony/plivo/answer") and any(c["dial"] == "##002#" for c in s["forwarding"])
    profile(client)
    client.put(f"{API}/phone", json={"auth_id": "MAXXXX", "auth_token": "tokentokentoken", "number": "+91 80 4711 2233"})
    s = client.get(f"{API}/status").json()
    assert s["profile_ready"] and s["phone"]["connected"] and s["phone"]["number"].startswith("+91") and "tokentoken" not in json.dumps(s)
    assert any("**61*91" in c["dial"] for c in s["forwarding"])


# --- the Plivo phone line ------------------------------------------------------------------

TOKEN = "plivo-test-auth-token"
BASE = "http://testserver"


def signed(client, path, form, query="", token=TOKEN, nonce="n0nce123"):
    url = f"{BASE}{path}" + (f"?{query}" if query else "")
    base = construct_post_url(url, dict(form)).decode()
    sig = get_signature_v3(token.encode(), base, nonce.encode()).decode()
    return client.post(path + (f"?{query}" if query else ""), data=form, headers={"X-Plivo-Signature-V3": sig, "X-Plivo-Signature-V3-Nonce": nonce})


@pytest.fixture
def line(client, ai):
    profile(client, owner_phone="9811111111")
    client.put(f"{API}/phone", json={"auth_id": "MAXXXX", "auth_token": TOKEN, "number": "+918047112233"})
    phone.audio_store._items.clear()
    return client


def test_unsigned_or_wrongly_signed_webhooks_are_refused(line):
    assert line.post("/telephony/plivo/answer", data={"CallUUID": "u1", "From": "9876543210"}).status_code == 403
    assert signed(line, "/telephony/plivo/answer", {"CallUUID": "u1", "From": "9876543210"}, token="wrong-token").status_code == 403
    assert line.get(f"{API}/calls").json()["total"] == 0


def test_webhooks_are_refused_until_a_phone_line_is_connected(client, ai):
    assert signed(client, "/telephony/plivo/answer", {"CallUUID": "u1", "From": "9876543210"}).status_code == 403


def test_a_phone_call_is_greeted_listens_replies_and_is_summarised_on_hangup(line, ai, monkeypatch):
    r = signed(line, "/telephony/plivo/answer", {"CallUUID": "uuid-1", "From": "+919876543210", "To": "+918047112233"})
    assert r.status_code == 200 and "<Speak>" in r.text and "AI assistant" in r.text and "<Record " in r.text and "/telephony/plivo/turn?call=" in r.text
    call_id = r.text.split("call=")[1].split('"')[0]
    # Plivo retries the same CallUUID: still one call
    again = signed(line, "/telephony/plivo/answer", {"CallUUID": "uuid-1", "From": "+919876543210", "To": "+918047112233"})
    assert call_id in again.text

    async def fake_download(url):
        return b"x" * 4000

    async def fake_transcribe(audio, filename, content_type, **kw):
        return llm.Transcript("mujhe 20 packet chawal chahiye", "Groq", "whisper", 300)

    monkeypatch.setattr(phone, "_download", fake_download)
    monkeypatch.setattr(llm, "transcribe", fake_transcribe)
    t1 = signed(line, "/telephony/plivo/turn", {"CallUUID": "uuid-1", "RecordUrl": "https://media.plivo.com/r.mp3", "RecordingDuration": "6"}, query=f"call={call_id}")
    assert "<Speak>Sure, how many packets" in t1.text and "<Record " in t1.text and "<Hangup/>" not in t1.text
    t2 = signed(line, "/telephony/plivo/turn", {"CallUUID": "uuid-1", "RecordUrl": "https://media.plivo.com/r2.mp3", "RecordingDuration": "5"}, query=f"call={call_id}")
    assert "<Hangup/>" in t2.text and "&lt;&lt;END" not in t2.text and "<<END>>" not in t2.text
    assert signed(line, "/telephony/plivo/hangup", {"CallUUID": "uuid-1", "Duration": "74"}).status_code == 204
    done = None
    for _ in range(60):
        done = line.get(f"{API}/calls/{call_id}").json()
        if done["status"] == "done":
            break
        time.sleep(0.05)
    assert done["status"] == "done" and done["source"] == "phone" and done["duration_s"] == 74 and done["importance"] == "action" and done["caller_number"] == "+919876543210"
    assert done["cost"]["phone"] > 0


def test_silence_ends_the_call_politely_after_two_empty_turns(line, ai, monkeypatch):
    r = signed(line, "/telephony/plivo/answer", {"CallUUID": "uuid-2", "From": "+919876543210"})
    call_id = r.text.split("call=")[1].split('"')[0]

    async def tiny(url):
        return b"x"

    monkeypatch.setattr(phone, "_download", tiny)
    first = signed(line, "/telephony/plivo/turn", {"CallUUID": "uuid-2", "RecordUrl": "https://media.plivo.com/s.mp3"}, query=f"call={call_id}")
    assert "could not hear that" in first.text and "<Hangup/>" not in first.text
    second = signed(line, "/telephony/plivo/turn", {"CallUUID": "uuid-2", "RecordUrl": "https://media.plivo.com/s.mp3"}, query=f"call={call_id}")
    assert "<Hangup/>" in second.text and len(ai.calls) == 0


def test_always_ring_callers_get_a_polite_unavailable_message_not_the_ai(line, ai):
    line.post(f"{API}/contacts", json={"name": "Mummy", "phone": "9000000001"})
    r = signed(line, "/telephony/plivo/answer", {"CallUUID": "uuid-3", "From": "+919000000001"})
    assert "not available right now" in r.text and "<Hangup/>" in r.text and "<Record " not in r.text and len(ai.calls) == 0
    assert line.get(f"{API}/stats").json()["rang_you_7d"] == 1


def test_assistant_off_and_daily_limit_hang_up_without_spending(line, ai, monkeypatch):
    profile(line, assistant_on=False)
    off = signed(line, "/telephony/plivo/answer", {"CallUUID": "uuid-4", "From": "+919876543210"})
    assert "<Hangup/>" in off.text and "<Record " not in off.text
    profile(line)
    monkeypatch.setattr(phone, "MAX_CALLS_PER_DAY", 1)
    ok = signed(line, "/telephony/plivo/answer", {"CallUUID": "uuid-5", "From": "+919876543210"})
    blocked = signed(line, "/telephony/plivo/answer", {"CallUUID": "uuid-6", "From": "+919876543211"})
    assert "<Record " in ok.text and "<Hangup/>" in blocked.text and "<Record " not in blocked.text


def test_one_caller_cannot_flood_the_line(line, ai):
    for i in range(phone.MAX_CALLS_PER_CALLER_10MIN):
        assert "<Record " in signed(line, "/telephony/plivo/answer", {"CallUUID": f"flood-{i}", "From": "+919876543210"}).text
    assert "<Record " not in signed(line, "/telephony/plivo/answer", {"CallUUID": "flood-x", "From": "+919876543210"}).text


def test_server_voice_is_played_to_the_caller_when_one_is_set_up(line, ai):
    mp3 = b"ID3\x04fake-mp3"
    llm.set_transport(httpx.MockTransport(lambda req: httpx.Response(200, json={"audioContent": base64.b64encode(mp3).decode()})))
    line.put(f"{LAB}/settings/tts", json={"google_key": "AIzaTESTKEY1234", "active": "google"})
    r = signed(line, "/telephony/plivo/answer", {"CallUUID": "uuid-7", "From": "+919876543210"})
    assert "<Play>" in r.text and "<Speak>" not in r.text
    url = r.text.split("<Play>")[1].split("</Play>")[0]
    audio = line.get(url.replace(BASE, ""))
    assert audio.status_code == 200 and audio.content == mp3 and audio.headers["content-type"] == "audio/mpeg"
    assert line.get("/telephony/audio/" + "0" * 32 + ".mp3").status_code == 404


def test_expired_audio_is_gone():
    store = phone.AudioStore(ttl=0)
    key = store.put(b"a", "audio/mpeg")
    time.sleep(0.01)
    assert store.get(key) is None


def test_recordings_must_come_over_https():
    with pytest.raises(ValueError):
        asyncio.run(phone._download("http://169.254.169.254/latest"))


def test_calls_left_open_are_closed_and_summarised(client, ai):
    from datetime import timedelta

    from lab import db
    from lab.models import Call, utcnow

    profile(client)
    old = client.post(f"{API}/calls", json={}).json()["call"]["id"]
    client.post(f"{API}/calls/{old}/turns", json={"content": "I need rice"})
    fresh = client.post(f"{API}/calls", json={}).json()["call"]["id"]
    with db.session_scope() as session:
        session.get(Call, old).started_at = utcnow() - timedelta(hours=3)
    assert asyncio.run(service.close_stale_calls()) == 1
    closed = client.get(f"{API}/calls/{old}").json()
    assert closed["status"] == "done" and closed["importance"] == "action" and client.get(f"{API}/calls/{fresh}").json()["status"] == "live"


def test_the_assistant_never_hangs_up_on_its_own_question(client, ai):
    profile(client)
    ai.replies = ["Ramesh will call you back. Should he use this number? <<END>>"]
    cid = client.post(f"{API}/calls", json={}).json()["call"]["id"]
    t = client.post(f"{API}/calls/{cid}/turns", json={"content": "I need rice"}).json()
    assert t["ended"] is False and t["assistant"]["content"].endswith("?") and "<<END>>" not in t["assistant"]["content"]
