import base64
import json

import httpx
import pytest

import llm
import tts

API = "/api/lab"
MP3 = b"ID3\x04fake-mp3-bytes"


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for k in ("GOOGLE_TTS_API_KEY", "DEEPINFRA_API_KEY", "TTS_CAP_CHARS_GOOGLE", "TTS_CAP_CHARS_CHATTERBOX"):
        monkeypatch.delenv(k, raising=False)
    yield
    llm.set_transport(None)
    tts.set_runtime(None)


def vendors(seen, *, chatterbox_json=None, google_status=200):
    def handler(req):
        seen.append(req)
        if req.url.host == "texttospeech.googleapis.com":
            if google_status != 200:
                return httpx.Response(google_status, json={"error": {"message": "API key not valid"}})
            return httpx.Response(200, json={"audioContent": base64.b64encode(MP3).decode()})
        if req.url.host == "api.deepinfra.com":
            return httpx.Response(200, json=chatterbox_json or {"audio": "data:audio/mpeg;base64," + base64.b64encode(MP3).decode(), "inference_status": {"cost": 0.0000048}})
        return httpx.Response(404)
    llm.set_transport(httpx.MockTransport(handler))


def test_google_speaks_with_the_chosen_voice_and_counts_characters(real_client):
    seen = []
    vendors(seen)
    saved = real_client.put(f"{API}/settings/tts", json={"google_key": "AIzaTESTKEY1234", "active": "google"}).json()
    assert saved["active"] == "google" and "AIzaTESTKEY1234" not in json.dumps(saved)  # the key is never sent back
    said = "नमस्ते, आप कैसे हैं?"
    res = real_client.post(f"{API}/speak", json={"text": said, "language": "hi-IN"})
    assert res.status_code == 200 and res.content == MP3 and res.headers["content-type"] == "audio/mpeg"
    assert res.headers["x-tts-voice"] == "hi-IN-Wavenet-A" and res.headers["x-tts-chars"] == str(len(said))
    sent = json.loads(seen[0].content)
    assert seen[0].headers["x-goog-api-key"] == "AIzaTESTKEY1234" and sent["voice"] == {"languageCode": "hi-IN", "name": "hi-IN-Wavenet-A"} and sent["audioConfig"]["audioEncoding"] == "MP3"
    google = next(e for e in real_client.get(f"{API}/settings/tts").json()["engines"] if e["id"] == "google")
    assert (google["used_chars"], google["calls"], google["free_left"], google["estimated_cost_usd"]) == (len(said), 1, 4_000_000 - len(said), 0.0)


def test_voice_choice_falls_back_when_a_language_has_no_wavenet():
    assert tts.google_voice("hi-IN", "Standard", "M") == "hi-IN-Standard-B"
    assert tts.google_voice("ta-IN", "Wavenet", "F") == "ta-IN-Wavenet-A"
    assert tts.google_voice("te-IN", "Wavenet", "F") == "te-IN-Standard-A"  # Telugu has Standard only
    assert tts.google_voice("en", "Wavenet", "M") == "en-IN-Wavenet-B" or tts.google_voice("en", "Wavenet", "M").startswith("en-")
    with pytest.raises(tts.TTSError, match="no Standard or WaveNet voice"):
        tts.google_voice("sw-KE")


def test_chatterbox_speaks_hindi_and_records_the_cost_deepinfra_reports(real_client):
    seen = []
    vendors(seen)
    real_client.put(f"{API}/settings/tts", json={"deepinfra_key": "DEEPKEY123"})
    res = real_client.post(f"{API}/speak", json={"text": "नमस्ते", "language": "hi-IN", "engine": "chatterbox"})
    assert res.status_code == 200 and res.content == MP3 and res.headers["x-tts-voice"] == "chatterbox-hi"
    sent = json.loads(seen[0].content)
    assert seen[0].headers["authorization"] == "Bearer DEEPKEY123" and sent["language_id"] == "hi" and sent["response_format"] == "mp3"
    cb = next(e for e in real_client.get(f"{API}/settings/tts").json()["engines"] if e["id"] == "chatterbox")
    assert cb["used_chars"] == 6 and cb["reported_cost_usd"] == pytest.approx(0.0000048)


def test_chatterbox_accepts_raw_audio_responses(real_client):
    llm.set_transport(httpx.MockTransport(lambda req: httpx.Response(200, content=MP3, headers={"content-type": "audio/mpeg"})))
    real_client.put(f"{API}/settings/tts", json={"deepinfra_key": "DEEPKEY123"})
    assert real_client.post(f"{API}/speak", json={"text": "Hello there", "language": "en-US", "engine": "chatterbox"}).content == MP3


def test_chatterbox_says_plainly_when_it_cannot_speak_a_language(real_client):
    seen = []
    vendors(seen)
    real_client.put(f"{API}/settings/tts", json={"deepinfra_key": "DEEPKEY123"})
    res = real_client.post(f"{API}/speak", json={"text": "வணக்கம்", "language": "ta-IN", "engine": "chatterbox"})
    assert res.status_code == 502 and "cannot speak ta-IN" in res.json()["detail"] and "Hindi" in res.json()["detail"] and not seen


def test_vendor_errors_are_readable_and_not_counted(real_client):
    vendors([], google_status=403)
    real_client.put(f"{API}/settings/tts", json={"google_key": "AIzaBAD"})
    res = real_client.post(f"{API}/speak", json={"text": "Hello", "language": "en-US", "engine": "google"})
    assert res.status_code == 502 and "Google Cloud" in res.json()["detail"]
    google = next(e for e in real_client.get(f"{API}/settings/tts").json()["engines"] if e["id"] == "google")
    assert google["used_chars"] == 0


def test_monthly_cap_stops_spending(real_client, monkeypatch):
    seen = []
    vendors(seen)
    monkeypatch.setenv("TTS_CAP_CHARS_GOOGLE", "30")
    real_client.put(f"{API}/settings/tts", json={"google_key": "AIzaTESTKEY1234"})
    ok = real_client.post(f"{API}/speak", json={"text": "twenty characters!!!", "language": "en-US", "engine": "google"})
    blocked = real_client.post(f"{API}/speak", json={"text": "twenty characters!!!", "language": "en-US", "engine": "google"})
    assert ok.status_code == 200 and blocked.status_code == 429 and "monthly limit of 30" in blocked.json()["detail"] and len(seen) == 1


def test_device_voice_and_missing_keys_are_explained(real_client):
    assert real_client.get(f"{API}/settings/tts").json()["active"] == "device"
    res = real_client.post(f"{API}/speak", json={"text": "Hi", "language": "en-US"})
    assert res.status_code == 409 and "played by your device" in res.json()["detail"]
    res = real_client.post(f"{API}/speak", json={"text": "Hi", "language": "en-US", "engine": "google"})
    assert res.status_code == 502 and "no API key" in res.json()["detail"]


def test_settings_are_validated_and_keys_can_be_removed(real_client):
    assert real_client.put(f"{API}/settings/tts", json={"active": "elevenlabs"}).status_code == 422
    assert real_client.put(f"{API}/settings/tts", json={"google_tier": "Neural2"}).status_code == 422
    real_client.put(f"{API}/settings/tts", json={"google_key": "AIzaTESTKEY1234", "google_tier": "Standard", "google_gender": "M"})
    status = real_client.get(f"{API}/settings/tts").json()
    assert (status["google_tier"], status["google_gender"]) == ("Standard", "M") and next(e for e in status["engines"] if e["id"] == "google")["key_hint"] == "…1234"
    assert real_client.delete(f"{API}/settings/tts/google/key").status_code == 204
    assert not next(e for e in real_client.get(f"{API}/settings/tts").json()["engines"] if e["id"] == "google")["configured"]


def test_text_is_cleaned_before_speaking():
    assert tts.clean_text("**Hello**   there\n\n_friend_ `x`") == "Hello there friend x"
    long = ("This is a sentence. " * 400)
    cut = tts.clean_text(long)
    assert len(cut) <= tts.MAX_CHARS and cut.endswith(".")
