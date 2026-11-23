import pytest
from fastapi.testclient import TestClient

import hindi_speech
from assistant import lexicon


def entry(word, say, meaning=""):
    return lexicon.EntryIn(word=word, say=say, meaning=meaning)


def test_apply_replaces_whole_words_only():
    entries = [{"forms": ["ramesh"], "say": "रमेश", "meaning": "", "source": "business"}, {"forms": ["kaju katli", "kaju kathli"], "say": "काजू कतली", "meaning": "", "source": "business"}]
    assert lexicon.apply("Ramesh ji ko kaju kathli chahiye", entries) == "रमेश ji ko काजू कतली chahiye"
    assert lexicon.apply("rameshwar aayega", entries) == "rameshwar aayega"
    assert lexicon.apply("", entries) == ""


def test_devanagari_forms_match_and_never_double_replace():
    entries = [{"forms": ["बर्फी"], "say": "बरफ़ी", "meaning": "", "source": "business"}]
    assert lexicon.apply("एक किलो बर्फी", entries) == "एक किलो बरफ़ी"
    assert lexicon.apply("बरफ़ी", entries) == "बरफ़ी"


def test_forms_split_dedupe_and_limit():
    assert lexicon.forms("kaju katli, kaju kathli | काजू कतली , kaju katli") == ["kaju kathli", "kaju katli", "काजू कतली"]


def test_stt_prompt_leads_with_names_then_custom_words():
    entries = [{"forms": ["x"], "say": "बासमती", "meaning": "", "source": "built-in"}, {"forms": ["y"], "say": "बाबूजी स्वीट्स", "meaning": "", "source": "business"}]
    out = lexicon.stt_prompt(entries, {"business_name": "Babuji Sweets", "owner_name": "Ramesh"})
    assert out.startswith("Babuji Sweets, Ramesh, बाबूजी स्वीट्स") and "बासमती" in out
    assert len(lexicon.stt_prompt(entries * 400, None, limit=100)) <= 100


def test_local_words_block_lists_only_explained_custom_words():
    entries = [{"forms": ["udhar"], "say": "उधार", "meaning": "on credit", "source": "built-in"}, {"forms": ["chhutta"], "say": "छुट्टा", "meaning": "small change", "source": "business"}, {"forms": ["z"], "say": "ज़", "meaning": "", "source": "business"}]
    assert lexicon.local_words_block(entries) == "chhutta = small change"
    assert lexicon.local_words_block([]) == "(none listed)"


def test_tts_uses_the_list_before_the_number_rules(monkeypatch):
    import asyncio

    import tts
    seen = {}

    async def fake(key, text, language, phone=False, voice_id=None):
        seen["text"] = text
        return "v", b"a", "audio/mpeg", None
    monkeypatch.setattr(tts, "_google", fake)
    monkeypatch.setattr(tts, "key_for", lambda engine: ("k", "env"))
    entries = [{"forms": ["babuji sweets"], "say": "बाबूजी स्वीट्स", "meaning": "", "source": "business"}]
    asyncio.run(tts.synthesize("google", "babuji sweets में बर्फ़ी ₹480 किलो है", "hi-IN", lexicon=entries))
    assert seen["text"] == "बाबूजी स्वीट्स में बर्फ़ी चार सौ अस्सी रुपये किलो है"
    asyncio.run(tts.synthesize("google", "babuji sweets", "en-IN", lexicon=entries))
    assert seen["text"] == "babuji sweets"  # an English voice keeps the English spelling


def test_starter_list_is_valid_and_hindi_normalizer_still_handles_numbers():
    assert len(lexicon.STARTER) > 60 and all(e["say"] for e in lexicon.STARTER)
    assert hindi_speech.normalize("2 kg") == "दो किलो"


# ---- through the API -------------------------------------------------------------------------
from test_assistant import ai, clean  # noqa: E402,F401
from test_platform import admin, new_business, owner, platform  # noqa: E402,F401


def test_words_are_saved_per_scope_and_isolated_between_businesses(platform):
    a_id, a_key = new_business(platform, "Babuji Sweets", "Ramesh")
    b_id, b_key = new_business(platform, "Gupta Sweets", "Anil")
    r = admin(platform, "PUT", "/lexicon", json={"scope": "platform", "entries": [{"word": "ladoo", "say": "लड्डू", "meaning": ""}]})
    assert r.status_code == 200 and r.json()["entries"][0]["say"] == "लड्डू"
    r = admin(platform, "PUT", "/lexicon", json={"scope": "business", "entries": [{"word": "Babuji Sweets", "say": "बाबूजी स्वीट्स", "meaning": "our shop"}]}, headers={"X-Business": a_id})
    assert r.status_code == 200
    view_a = admin(platform, "GET", "/lexicon?scope=business", headers={"X-Business": a_id}).json()
    view_b = admin(platform, "GET", "/lexicon?scope=business", headers={"X-Business": b_id}).json()
    assert [e["say"] for e in view_a["entries"]] == ["बाबूजी स्वीट्स"] and view_b["entries"] == []
    assert view_b["inherited"][0]["word"] == "ladoo" and len(view_b["builtin"]) > 60
    test = admin(platform, "POST", "/lexicon/test", json={"text": "Babuji Sweets का ladoo ₹20 है", "scope": "business"}, headers={"X-Business": a_id}).json()
    assert test["spoken"] == "बाबूजी स्वीट्स का लड्डू बीस रुपये है" and test["changed"]
    other = admin(platform, "POST", "/lexicon/test", json={"text": "Babuji Sweets", "scope": "business"}, headers={"X-Business": b_id}).json()
    assert other["spoken"] == "Babuji Sweets"  # another business's word does not leak


def test_an_owner_cannot_edit_the_word_list_and_bad_input_is_refused(platform):
    _, key = new_business(platform, "Babuji Sweets", "Ramesh")
    assert owner(platform, key, "PUT", "/lexicon", json={"scope": "business", "entries": []}).status_code in (401, 403)
    assert admin(platform, "PUT", "/lexicon", json={"scope": "platform", "entries": [{"word": " ", "say": "x", "meaning": ""}]}).status_code == 422
    assert admin(platform, "PUT", "/lexicon", json={"scope": "platform", "entries": [{"word": "a", "say": "x", "meaning": "", "extra": 1}]}).status_code == 422


def test_explained_words_reach_the_ai_prompt(platform):
    a_id, _ = new_business(platform, "Babuji Sweets", "Ramesh")
    admin(platform, "PUT", "/lexicon", json={"scope": "business", "entries": [{"word": "chhutta", "say": "छुट्टा", "meaning": "small change"}]}, headers={"X-Business": a_id})
    p = admin(platform, "POST", "/prompts/preview", json={"kind": "assistant", "text": "", "business_id": a_id}).json()
    assert "chhutta = small change" in p["text"] and "{{" not in p["text"]
    assert "feminine" in p["text"] or "masculine" in p["text"]


def test_the_speech_hint_is_cut_by_bytes_because_hindi_letters_take_three_each():
    """A shop with many Hindi words made the hint 979 bytes; Groq allows 896 and rejected every recording."""
    entries = [{"forms": ["x"], "say": "बासमती चावल और काजू कतली", "meaning": "", "source": "business"}] * 200
    hint = lexicon.stt_prompt(entries, {"business_name": "बाबूजी स्वीट्स", "owner_name": "रमेश"})
    assert 0 < len(hint.encode("utf-8")) <= 700


def test_a_rejected_hint_never_stops_speech_recognition(real_client):
    import httpx
    import llm
    calls = []

    def handler(req):
        calls.append(req.content)
        if b'name="prompt"' in req.content:
            return httpx.Response(400, json={"error": {"message": "prompt length must be 896 characters or fewer"}})
        return httpx.Response(200, json={"text": "ok suna"})
    llm.set_transport(httpx.MockTransport(handler))
    real_client.put("/api/lab/settings/providers/groq", json={"api_key": "gsk_abcdefgh"})
    import asyncio
    out = asyncio.run(llm.transcribe(b"audio", "a.mp3", "audio/mpeg", prompt="x" * 100))
    assert out.text == "ok suna" and len(calls) == 2 and b'name="prompt"' not in calls[1]
    assert len(llm._clip_bytes("बा" * 500, 800).encode("utf-8")) <= 800
