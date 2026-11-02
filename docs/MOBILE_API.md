# Client API for the mobile app (`/api/v1`)

Your app talks to the same server and the same conversation core as the web lab and the web app, so a conversation
behaves identically on iOS, Android and web. **The app never sends a prompt, variables or model settings.** It opens a
session, and the server applies the *release* (prompt version + variables + model settings) of the environment the API key belongs to.

```
Lab: test → Release to Staging → try on phone with a staging key → Release to Production → production key
```

## Authentication

Create keys in the lab under **Settings → Mobile and web apps**. Send `Authorization: Bearer vtl_…` (or `X-API-Key: vtl_…`).
A key is bound to one environment (`staging` or `production`). Keys are shown once and stored hashed. Never ship a
production key inside a public web page; for native apps keep it out of source control (build config / secure storage).
Default rate limit: 60 requests per minute per key (`APP_RATE_LIMIT_PER_MIN`).

Errors are JSON `{"detail": "..."}`. Common codes: `401` bad key, `404` unknown session (or not yours), `409` session closed or
limit reached, `429` rate limited, `502` model/speech provider failed, `503` nothing released to this environment yet.

## Flow

| Step | Request |
|---|---|
| Check readiness | `GET /api/v1/config` → `{ready, environment, release, speech_to_text}` |
| Start a conversation | `POST /api/v1/sessions` `{"client":"ios","user_ref":"<your user id>"}` → `{session_id}` |
| Send text, get the reply | `POST /api/v1/sessions/{id}/turns` `{"text":"…"}` → `{reply, latency_ms, turn, model}` |
| Send a recording | `POST /api/v1/sessions/{id}/audio-turn` multipart `file` (+ optional `language`, e.g. `en-IN`) → `{transcript, reply, no_speech, stt_latency_ms, latency_ms}` |
| Speech to text only | `POST /api/v1/transcribe` multipart `file` → `{text}` |
| Read the transcript | `GET /api/v1/sessions/{id}` |
| Finish | `POST /api/v1/sessions/{id}/finish` → `{status, evaluating}` |
| Erase a user's data | `DELETE /api/v1/sessions/{id}` |

`user_ref` is your own opaque identifier. Do not send names, emails or phone numbers.
If `no_speech` is `true` the clip contained no speech and **no reply was generated**; just start listening again.

### Voice on the phone

Two options, both give the same assistant replies:

1. **Server speech recognition (recommended for parity).** Record a short clip (AAC/m4a on iOS, webm/ogg/mp3/wav also accepted,
   up to about 12 MB), upload it to `audio-turn`, speak the `reply` with the platform text-to-speech
   (`AVSpeechSynthesizer` on iOS, `TextToSpeech` on Android). Recognition is Whisper via your Groq key, identical on every platform.
2. **On-device recognition.** Use the platform recogniser and send the text to `turns`.

Text-to-speech is a client concern; the server returns text. Use the same voice settings in your app that you tested with in the lab.

## Examples

```bash
KEY=vtl_xxx; BASE=https://your-lab.example.com/api/v1
SID=$(curl -s -X POST $BASE/sessions -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
      -d '{"client":"ios","user_ref":"u-123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["session_id"])')
curl -s -X POST $BASE/sessions/$SID/turns -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' -d '{"text":"I feel anxious about tomorrow."}'
curl -s -X POST $BASE/sessions/$SID/audio-turn -H "Authorization: Bearer $KEY" -F file=@clip.m4a -F language=en-IN
curl -s -X POST $BASE/sessions/$SID/finish -H "Authorization: Bearer $KEY"
```

```swift
// Swift (URLSession)
var req = URLRequest(url: URL(string: "\(base)/sessions/\(sid)/turns")!)
req.httpMethod = "POST"
req.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
req.setValue("application/json", forHTTPHeaderField: "Content-Type")
req.httpBody = try JSONEncoder().encode(["text": userText])
let (data, _) = try await URLSession.shared.data(for: req)
```

```kotlin
// Kotlin (OkHttp)
val body = """{"text":"$text"}""".toRequestBody("application/json".toMediaType())
val req = Request.Builder().url("$base/sessions/$sid/turns").header("Authorization", "Bearer $apiKey").post(body).build()
```

Interactive schema: `/docs` on the server.

## What gets stored

Each session is stored as a conversation (transcript, timings, client, your `user_ref`) and appears in the lab under
**Conversations → App traffic**, where you can evaluate it. Optionally, **Settings → Mobile and web apps → Evaluate finished
app sessions** scores every finished session automatically (this spends model tokens). Because these are real users' conversations, decide on a retention
period, tell users what is stored, and call `DELETE /sessions/{id}` when someone asks for deletion.
