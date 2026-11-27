"""The owner app (design v5): people, WhatsApp thread, shop info, plan, voice."""
import json

import httpx
import llm
import pytest

from test_assistant import API, SUMMARY, add_item, ai, clean, connect_whatsapp, profile, wa_transport  # noqa: F401

ORDER = {"items": [{"name": "atta", "qty_n": 10, "unit": "kg", "board_name": "Atta"}, {"name": "sugar", "qty_n": 5, "unit": "kg", "board_name": "Sugar"}],
         "mode": "delivery", "when": "tomorrow morning", "address": "14 Gandhi Road"}
RICH = {**SUMMARY, "summary": "Sunil wants 10 kg atta and 5 kg sugar, delivery tomorrow morning.", "caller_name": "Sunil", "ask": "Rate and delivery time", "order": ORDER,
        "keep": ["Best time to call: before 9 pm"], "replies": [{"label": "Call tonight", "text": "I will call you at 8 pm tonight."}, {"label": "", "text": "Please send the full address."}]}


def make_call(client, ai, number, summary):
    ai.summary_raw = json.dumps(summary)
    cid = client.post(f"{API}/calls", json={"caller_number": number}).json()["call"]["id"]
    client.post(f"{API}/calls/{cid}/turns", json={"content": "namaste"})
    client.post(f"{API}/calls/{cid}/end")
    return cid


def test_the_structured_summary_is_saved_with_the_call(client, ai):
    profile(client, mode="board")
    add_item(client, "Atta", "Rs 42/kg")
    cid = make_call(client, ai, "98765 43210", RICH)
    d = client.get(f"{API}/calls/{cid}").json()
    assert d["ask"] == "Rate and delivery time" and d["order"]["mode"] == "delivery" and d["order"]["items"][0]["board_name"] == "Atta"
    assert d["keep"] == ["Best time to call: before 9 pm"] and [r["label"] for r in d["replies"]] == ["Call tonight", "Reply"]
    prompt = [c[0]["content"] for c in ai.calls if "BOARD ITEMS" in c[0]["content"]][-1]  # the call-notes prompt (a translation call may follow it)
    assert "BOARD ITEMS: Atta" in prompt and '"ask"' in prompt and "never confirms an order" in prompt


def test_a_messy_structured_summary_never_breaks_a_call(client, ai):
    profile(client)
    bad = {**SUMMARY, "order": "nonsense", "keep": "x", "replies": [1, {"text": ""}, {"label": "ok", "text": "fine"}], "ask": ["a"]}
    cid = make_call(client, ai, "98765 43210", bad)
    d = client.get(f"{API}/calls/{cid}").json()
    assert d["status"] == "done" and d["order"] == {} and d["keep"] == [] and d["replies"] == [{"label": "ok", "text": "fine"}]


def test_calls_from_one_person_are_one_row_with_a_waiting_count(client, ai):
    profile(client, mode="board")
    make_call(client, ai, "98765 43210", RICH)
    make_call(client, ai, "98765 43210", {**RICH, "summary": "Sunil asks again about delivery."})
    make_call(client, ai, "97000 11111", {**SUMMARY, "caller_name": "Meena", "importance": "fyi", "summary": "Meena asked the shop timing."})
    make_call(client, ai, "80000 55501", {**SUMMARY, "caller_name": "", "importance": "ignore", "summary": "Loan sales call."})
    need = client.get(f"{API}/people?tab=need").json()
    assert [r["calls"] for r in need["rows"]] == [2] and need["rows"][0]["pending"] == 2 and need["rows"][0]["kind"] == "need" and need["pending_calls"] == 2
    assert need["pending_today"] == 2 and need["pending_older"] == 0
    assert [r["name"] for r in client.get(f"{API}/people?tab=good").json()["rows"]] == ["Meena"]
    assert [r["summary"] for r in client.get(f"{API}/people?tab=spam").json()["rows"]] == ["Loan sales call."]
    everyone = client.get(f"{API}/people?tab=all").json()
    assert len(everyone["rows"]) == 3 and everyone["rows"][0]["kind"] == "need"  # people who are waiting come first
    assert [r["name"] for r in client.get(f"{API}/people?tab=all&q=meena").json()["rows"]] == ["Meena"]
    assert client.get(f"{API}/people?tab=all&range=today").json()["people"] == 3
    assert everyone["today"]["handled"] == 4 and everyone["today"]["orders"] == 4  # the fake summaries all say category "order"
    assert client.get(f"{API}/people?tab=sideways").status_code == 422


def test_the_thread_holds_every_call_and_ready_replies(client, ai):
    profile(client, mode="board")
    add_item(client, "Atta", "Rs 42/kg")
    add_item(client, "Sugar", "Rs 46/kg")
    make_call(client, ai, "98765 43210", RICH)
    t = client.get(f"{API}/thread", params={"phone": "+919876543210"}).json()
    assert t["name"] == "Sunil" and t["can_reply"] and t["ask"] == "Rate and delivery time" and len(t["pending"]) == 1 and not t["resolved"]
    call = [i for i in t["items"] if i["type"] == "call"][0]
    assert call["summary"].startswith("Sunil wants") and call["points"][0].startswith("Call Ravi back") and call["done"] is False
    labels = [c["label"] for c in t["chips"]]
    assert labels[0] == "Total ₹650" and "Atta 10 kg × ₹42" in t["chips"][0]["text"] and labels[1:] == ["Call tonight", "Reply"]
    assert client.get(f"{API}/thread", params={"phone": "+911111111111"}).status_code == 404


def test_no_total_is_guessed_when_a_price_or_unit_does_not_match(client, ai):
    profile(client, mode="board")
    add_item(client, "Atta", "Rs 420 for 10 kg bag")  # not a per-unit price
    add_item(client, "Sugar", "Rs 46/litre")  # a different unit
    make_call(client, ai, "98765 43210", RICH)
    t = client.get(f"{API}/thread", params={"phone": "+919876543210"}).json()
    assert [c["label"] for c in t["chips"]] == ["Call tonight", "Reply"]


def test_an_owners_reply_goes_out_and_marks_the_person_done_only_if_whatsapp_accepts_it(client, ai, monkeypatch):
    monkeypatch.setenv("MUNSHI_WHATSAPP", "on")
    profile(client, mode="board")
    cid = make_call(client, ai, "98765 43210", RICH)
    assert client.post(f"{API}/messages", json={"phone": "+919876543210", "text": "Total Rs 650."}).status_code == 409  # WhatsApp not connected
    seen = []
    wa_transport(seen)
    connect_whatsapp(client)
    r = client.post(f"{API}/messages", json={"phone": "+919876543210", "text": "Total Rs 650."})
    assert r.status_code == 200 and r.json() == {"sent": True, "marked_done": 1}
    sent = json.loads(seen[-1].content)
    assert sent["type"] == "text" and sent["text"]["body"] == "Total Rs 650." and sent["to"] == "919876543210"
    t = client.get(f"{API}/thread", params={"phone": "+919876543210"}).json()
    assert [i["sender"] for i in t["items"] if i["type"] == "wa"] == ["owner"] and t["resolved"] and t["pending"] == []
    assert client.get(f"{API}/calls/{cid}").json()["reviewed"] is True


def test_whatsapp_replies_are_blocked_when_feature_is_off(client, ai):
    profile(client, mode="board")
    make_call(client, ai, "98765 43210", RICH)
    r = client.post(f"{API}/messages", json={"phone": "+919876543210", "text": "Total Rs 650."})
    assert r.status_code == 409 and "not enabled" in r.json()["detail"]


def test_a_closed_whatsapp_window_is_explained_and_nothing_is_marked_done(client, ai, monkeypatch):
    monkeypatch.setenv("MUNSHI_WHATSAPP", "on")
    profile(client, mode="board")
    make_call(client, ai, "98765 43210", RICH)
    wa_transport([], status=400, body={"error": {"code": 131047, "message": "Re-engagement message"}})
    connect_whatsapp(client)
    r = client.post(f"{API}/messages", json={"phone": "+919876543210", "text": "Hello"})
    assert r.status_code == 409 and "24 hours" in r.json()["detail"]
    t = client.get(f"{API}/thread", params={"phone": "+919876543210"}).json()
    assert t["pending"] and not [i for i in t["items"] if i["type"] == "wa"]
    assert client.post(f"{API}/messages", json={"phone": "+919876543210", "text": "   "}).status_code in (409, 422)


def test_people_who_called_can_be_set_to_always_ring(client, ai):
    profile(client, mode="board")
    make_call(client, ai, "98765 43210", RICH)
    client.post(f"{API}/contacts", json={"name": "Mummy", "phone": "98000 00022", "always_ring": True})
    k = client.get(f"{API}/people/known").json()
    assert [c["name"] for c in k["always"]] == ["Mummy"] and [c["name"] for c in k["customers"]] == ["Sunil"] and k["customers"][0]["id"] is None


def test_shop_info_shows_freshness_and_one_tap_confirms(client):
    profile(client, mode="board", address="21 Main Bazaar", delivery="Within 3 km", rules="No credit")
    add_item(client, "Atta", "Rs 42/kg")
    s = client.get(f"{API}/shop").json()
    assert [r["name"] for r in s["rates"]] == ["Atta"] and {f["field"] for f in s["facts"]} == {"delivery", "address", "rules"} and s["stale"] == 0
    from lab import db
    from assistant import service, tenant
    from datetime import timedelta
    with db.session_scope() as session, tenant.acting_as(tenant.first_business_id(session)):
        p = service.get_profile(session)
        old = (service.utcnow() - timedelta(days=10)).isoformat()
        service.save_profile(session, service.ProfileIn(**{**p, "confirmed": {"address": old}}))
        tenant.put(session, "profile", {**service.get_profile(session), "confirmed": {**service.get_profile(session)["confirmed"], "address": old}})
    s = client.get(f"{API}/shop").json()
    assert [f["field"] for f in s["facts"] if f["stale"]] == ["address"] and s["stale"] == 1
    assert client.post(f"{API}/shop/confirm", json={"id": "fact:address"}).json()["stale"] == 0
    rid = s["rates"][0]["id"]
    assert client.post(f"{API}/shop/confirm", json={"id": rid}).status_code == 200
    assert client.post(f"{API}/shop/confirm", json={"id": "fact:bogus"}).status_code == 404
    assert client.post(f"{API}/shop/confirm", json={"id": "nope"}).status_code == 404


def test_a_typed_update_is_read_shown_and_saved_only_after_the_owner_agrees(client, monkeypatch):
    profile(client, mode="board", address="21 Main Bazaar", rules="No credit")
    add_item(client, "Atta", "Rs 42/kg")
    seen = {}

    async def fake(messages, **kw):
        seen["system"] = messages[0]["content"]
        return llm.LLMResult(json.dumps({"rates": [{"name": "atta", "price": "44/kg"}, {"name": "chana dal", "price": "98/kg"}], "facts": [{"field": "hours", "text": "Closed on Sundays"}, {"field": "nonsense", "text": "x"}]}), "Fake", "fake", 5, {})
    monkeypatch.setattr(llm, "chat", fake)
    r = client.post(f"{API}/shop/understand", json={"text": "atta 44, chana dal 98, Sunday band"})
    assert r.status_code == 200 and "BOARD ITEMS: Atta" in seen["system"]
    d = r.json()
    assert [(x["name"], x["action"], x["old_price"]) for x in d["rates"]] == [("Atta", "update", "Rs 42/kg"), ("chana dal", "new", "")]
    assert [f["field"] for f in d["facts"]] == ["hours"]
    assert client.get(f"{API}/board").json()["items"][0]["price"] == "Rs 42/kg"  # nothing saved yet
    done = client.post(f"{API}/shop/apply", json={"rates": d["rates"], "facts": d["facts"]}).json()
    assert done["added"] == 1 and done["updated"] == 1 and done["facts"] == 1
    prices = {i["name"]: i["price"] for i in client.get(f"{API}/board").json()["items"]}
    assert prices["Atta"].startswith("44") and "98" in prices["chana dal"]
    assert client.get(f"{API}/profile").json()["hours"] == "Closed on Sundays"


def test_an_update_the_ai_cannot_read_is_refused_clearly(client, monkeypatch):
    profile(client, mode="board")

    async def broken(messages, **kw):
        raise llm.LLMError("All configured providers failed. Fake: boom")
    monkeypatch.setattr(llm, "chat", broken)
    assert client.post(f"{API}/shop/understand", json={"text": "atta 44"}).status_code == 502

    async def empty(messages, **kw):
        return llm.LLMResult("{}", "Fake", "fake", 5, {})
    monkeypatch.setattr(llm, "chat", empty)
    r = client.post(f"{API}/shop/understand", json={"text": "hello there"})
    assert r.status_code == 422 and "atta 44" in r.json()["detail"]


def test_the_plan_shows_the_trial_usage_and_cancels_and_restarts(client, ai):
    profile(client, mode="board")
    make_call(client, ai, "98765 43210", RICH)
    p = client.get(f"{API}/plan").json()
    assert p["status"] == "trial" and p["trial_days"] == 14 and 13 <= p["days_left"] <= 14 and p["calls_used"] == 1 and p["call_limit"] == 100 and p["billing_live"] is False
    assert client.put(f"{API}/plan", json={"upi": "not a upi"}).status_code == 422
    assert client.put(f"{API}/plan", json={"upi": "ramesh@okbank"}).json()["upi"] == "ramesh@okbank"
    assert client.put(f"{API}/plan", json={"cancelled": True}).json()["status"] == "cancelled"
    assert client.put(f"{API}/plan", json={"cancelled": False}).json()["status"] == "trial"
    assert client.put(f"{API}/plan", json={"upi": ""}).json()["upi"] == ""


def test_the_voice_choice_is_saved_and_decides_the_verbs_the_ai_uses(client, ai):
    v = client.get(f"{API}/voices").json()
    assert [x["name"] for x in v["voices"]] == ["Priya", "Arjun", "Kavita", "Rohan"] and v["current"] == "v1"
    profile(client, mode="board", voice="v2")
    assert client.get(f"{API}/voices").json()["current"] == "v2"
    cid = client.post(f"{API}/calls", json={"caller_number": "98765 43210"}).json()["call"]["id"]
    client.post(f"{API}/calls/{cid}/turns", json={"content": "namaste"})
    assert "masculine" in ai.calls[-1][0]["content"]
    profile(client, mode="board", voice="v3")
    cid = client.post(f"{API}/calls", json={"caller_number": "98765 43211"}).json()["call"]["id"]
    client.post(f"{API}/calls/{cid}/turns", json={"content": "namaste"})
    assert "feminine" in ai.calls[-1][0]["content"]
    assert client.put(f"{API}/profile", json={"business_name": "X", "owner_name": "Y", "voice": "v9"}).status_code == 422
    r = client.post(f"{API}/voices/sample", json={"voice": "v1"})
    assert r.status_code == 409 and "phone" in r.json()["detail"]


def test_each_voice_maps_to_a_real_google_voice_of_the_right_gender():
    import tts
    names = {vid: tts.google_voice("hi-IN", gender=g, pick=p) for vid, g, p in (("v1", "F", 0), ("v2", "M", 0), ("v3", "F", 1), ("v4", "M", 1))}
    assert len(set(names.values())) == 4 and all(n.startswith("hi-IN-Wavenet-") for n in names.values())
    assert tts.google_voice("hi-IN", gender="F", pick=7)  # a pick beyond the list wraps round


def test_opening_and_closing_times_become_the_hours_the_ai_states(client):
    p = profile(client, mode="board", open="8:00", close="21:00")
    assert p["hours"] == "8:00 to 21:00" and p["confirmed"]["hours"]
    assert profile(client, mode="board", open="9:00", close="20:00")["hours"] == "9:00 to 20:00"
    assert profile(client, mode="board", languages=["hi", "hing"])["languages"] == ["hi", "hing"]


# ---- the owner's language -----------------------------------------------------------------------

class Translator:
    """Stands in for the model: translates by looking each string up in a table, counts the calls."""
    TABLE = {"Sunil wants 10 kg atta and 5 kg sugar, delivery tomorrow morning.": "सुनील को 10 किलो आटा और 5 किलो चीनी चाहिए, कल सुबह डिलीवरी।", "Rate and delivery time": "रेट और डिलीवरी का समय",
             "atta": "आटा", "sugar": "चीनी", "tomorrow morning": "कल सुबह", "Call Ravi back about 20 packets of rice": "20 पैकेट चावल के बारे में रवि को फ़ोन करें", "Confirm delivery for Friday": "शुक्रवार की डिलीवरी पक्की करें",
             "Best time to call: before 9 pm": "फ़ोन करने का अच्छा समय: रात 9 बजे से पहले", "namaste": "नमस्ते"}

    def __init__(self):
        self.calls = 0

    async def __call__(self, messages, **kw):
        self.calls += 1
        asked = json.loads(messages[1]["content"])
        return llm.LLMResult(json.dumps([self.TABLE.get(x, x) for x in asked], ensure_ascii=False), "Fake", "fake", 3, {})


def finished_call(client, ai, monkeypatch):
    profile(client, mode="board", ui_lang="en")  # owner reads English at the moment of the call, so nothing is translated yet
    cid = make_call(client, ai, "98765 43210", RICH)
    fake = Translator()
    monkeypatch.setattr(llm, "chat", fake)
    return cid, fake


def test_hindi_screens_show_call_notes_in_hindi_and_translate_only_once(client, ai, monkeypatch):
    cid, fake = finished_call(client, ai, monkeypatch)
    d = client.get(f"{API}/calls/{cid}", params={"lang": "hi"}).json()
    assert d["summary"].startswith("सुनील को 10 किलो आटा") and d["ask"] == "रेट और डिलीवरी का समय" and d["keep"] == ["फ़ोन करने का अच्छा समय: रात 9 बजे से पहले"]
    assert [i["name"] for i in d["order"]["items"]] == ["आटा", "चीनी"] and d["order"]["when"] == "कल सुबह" and d["action_items"][0]["text"].startswith("20 पैकेट चावल")
    assert d["order"]["address"] == "14 Gandhi Road" and d["order"]["items"][0]["qty_n"] == 10  # names, numbers and the saved original stay as they were
    n = fake.calls
    client.get(f"{API}/calls/{cid}", params={"lang": "hi"})
    rows = client.get(f"{API}/people", params={"tab": "need", "lang": "hi"}).json()["rows"]
    assert rows[0]["summary"].startswith("सुनील को") and rows[0]["ask"] == "रेट और डिलीवरी का समय" and fake.calls == n  # kept with the call: no second model call
    t = client.get(f"{API}/thread", params={"phone": "+919876543210", "lang": "hi"}).json()
    call = [i for i in t["items"] if i["type"] == "call"][0]
    assert call["summary"].startswith("सुनील को") and call["points"][0].startswith("20 पैकेट चावल") and t["ask"] == "रेट और डिलीवरी का समय" and fake.calls == n
    english = client.get(f"{API}/calls/{cid}").json()  # without a language the saved English is returned unchanged
    assert english["summary"].startswith("Sunil wants")
    assert client.get(f"{API}/calls/{cid}", params={"lang": "fr"}).status_code == 422


def test_the_conversation_is_translated_only_when_asked_for(client, ai, monkeypatch):
    cid, fake = finished_call(client, ai, monkeypatch)
    plain = client.get(f"{API}/calls/{cid}", params={"lang": "hi"}).json()
    assert plain["turns"][1]["content"] == "namaste"
    full = client.get(f"{API}/calls/{cid}", params={"lang": "hi", "turns": "true"}).json()
    assert full["turns"][1]["content"] == "नमस्ते"
    assert client.get(f"{API}/calls/{cid}").json()["turns"][1]["content"] == "namaste"


def test_a_failed_translation_shows_the_original_and_never_breaks_the_screen(client, ai, monkeypatch):
    profile(client, mode="board", ui_lang="en")
    cid = make_call(client, ai, "98765 43210", RICH)

    async def broken(messages, **kw):
        raise llm.LLMError("All configured providers failed. Fake: boom")
    monkeypatch.setattr(llm, "chat", broken)
    d = client.get(f"{API}/calls/{cid}", params={"lang": "hi"})
    assert d.status_code == 200 and d.json()["summary"].startswith("Sunil wants")
    assert client.get(f"{API}/people", params={"tab": "need", "lang": "hi"}).status_code == 200


def test_text_already_in_the_right_language_is_not_sent_to_the_model(client, ai, monkeypatch):
    profile(client, mode="board", ui_lang="en")
    cid = make_call(client, ai, "98765 43210", {**RICH, "summary": "सुनील को आटा चाहिए", "ask": "रेट बताना", "keep": [], "order": {"items": [], "mode": "", "when": "", "address": ""}, "action_items": ["रवि को फ़ोन करें"]})
    fake = Translator()
    monkeypatch.setattr(llm, "chat", fake)
    d = client.get(f"{API}/calls/{cid}", params={"lang": "hi"}).json()
    assert d["summary"] == "सुनील को आटा चाहिए" and fake.calls == 0


def test_the_owners_language_is_saved_and_notes_are_ready_when_the_call_ends(client, ai, monkeypatch):
    profile(client, mode="board")  # ui_lang defaults to Hindi
    assert client.get(f"{API}/profile").json()["ui_lang"] == "hi"
    fake = Translator()
    cid = client.post(f"{API}/calls", json={"caller_number": "98765 43210"}).json()["call"]["id"]
    client.post(f"{API}/calls/{cid}/turns", json={"content": "namaste"})
    ai.summary_raw = json.dumps(RICH)
    original = llm.chat

    async def both(messages, **kw):  # the receptionist and the call notes use the app's fake; translations use the table
        return await (fake(messages, **kw) if messages[0]["content"].startswith("You translate") else original(messages, **kw))
    monkeypatch.setattr(llm, "chat", both)
    client.post(f"{API}/calls/{cid}/end")
    assert fake.calls == 1  # made at the end of the call, in the owner's language
    n = fake.calls
    assert client.get(f"{API}/calls/{cid}", params={"lang": "hi"}).json()["ask"] == "रेट और डिलीवरी का समय" and fake.calls == n
    assert client.put(f"{API}/profile", json={"business_name": "X", "owner_name": "Y", "ui_lang": "fr"}).status_code == 422
