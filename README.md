# Munshi: AI call assistant for small businesses

Munshi answers the calls a shop owner, wholesaler or small factory misses. It talks to the caller in their language, takes the message, and gives the owner a summary with a to-do list. Calls from people the owner always wants to talk to are never answered by the AI.

| Tab (`/assistant/`) | What you do |
|---|---|
| **Calls** | Calls that need you, a to-do list for each, the transcript, your own notes, and a one-tap Call back. |
| **Try it** | Phone your own assistant from the browser as if you were a customer. Add notes while it happens. |
| **Contacts** | People who always ring you (the AI does not answer them). Paste many at once. |
| **Board** | What the assistant may say about prices and stock. Update it with a photo of your price list or shelf, by voice or typing ("toor dal 170 ho gayi"), or tap "Everything is the same as before". Prices not confirmed for 2 days (adjustable) are treated as "ask the owner". |
| **Setup** | Your AI key, your business facts, the assistant's voice, and the Plivo phone line with the forwarding codes. |

**The portal (`/portal/`)** is the control room on a bigger screen, directly connected to the app: Overview (what needs you), Knowledge (the board, photo reader, freshness window, questions callers asked that it could not answer), Prompts (greeting, extra instructions and call-note rules, with versions and one-click restore), Integrations (every connection with status, a live Test button and its settings), Costs (rupees per call and per day, a monthly budget with an optional hard stop) and Activity (who changed what). The photo reader needs a vision-capable model; choose it under Integrations. Call summaries are kept to a one-line gist plus short to-dos.

The prompt testing lab that tunes the assistant's behaviour lives at `/lab/` (it was the first version of this repository, see below).

**Real phone calls** use Plivo: your phone forwards calls you miss to a Plivo number, Plivo calls `/telephony/plivo/*` on this server. It is turn based (about a 3 to 5 second pause after the caller stops), not live streaming. The phone path is tested with signed fake Plivo requests, not yet with a live Plivo account.

| Extra setting | Meaning |
|---|---|
| `PUBLIC_BASE_URL` | The https address Plivo calls. Needed if the server sits behind a proxy that hides the real host. |
| `ASSISTANT_MAX_CALLS_PER_DAY` | Stops spam from spending money (default 200). One number can call at most 5 times in 10 minutes. |
| `GOOGLE_TTS_API_KEY`, `DEEPINFRA_API_KEY`, `TTS_CAP_CHARS_*` | Voices and their monthly character limits (or paste the keys in Setup). |

Code map: `backend/assistant/` (`service.py` call logic and summary, `prompts.py` everything the model is told, `router.py` the product API, `phone.py` Plivo webhooks), `frontend/assistant/`. `frontend/portal/`, `assistant/vision.py` (photo reader), `assistant/costs.py`, `assistant/config.py` (budget, prompts, audit), `assistant/integrations.py`. Tests: `backend/tests/test_assistant.py`, `test_portal.py`.

---

# Voice Test Lab (`/lab/`)

Test a voice assistant's prompt against different moods, talk to it, and publish the version that passes to your web and mobile apps.

| Tab | What you do |
|---|---|
| **Test** | Write the prompt, set its `{{variables}}`, pick moods, press **Run test**. Each mood gets PASS or FAIL with the reason, and the score is compared with your previous test. |
| **Talk** | Speak to it (works on iPhone and Android through Whisper). **Finish** scores the conversation. |
| **Results** | Everything you tested, talked, or received from your app, with a trend line. |
| **Settings** | Groq connection and status, creativity and reply length, what counts as a pass, app keys. |

**Publish to my app** makes the web app and every mobile app use that prompt. Developers: [`docs/MOBILE_API.md`](docs/MOBILE_API.md).

## Run it locally

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py        # http://127.0.0.1:8001  (opens the lab)
```

Open **Settings**, paste your Groq key (console.groq.com/keys), press **Connect**.

## Deploy

Render: **New > Blueprint** on this repository (`render.yaml`). Set `DATABASE_URL` (Postgres) and `GROQ_API_KEY`; the rest is generated.
Docker: `docker build -t voice-lab . && docker run -p 8000:8000 -e DATABASE_URL=... -e GROQ_API_KEY=... -e LAB_OPEN_ACCESS=true voice-lab`.

Run **one** instance. Phones only allow the microphone on **https**.

| Setting | Meaning |
|---|---|
| `DATABASE_URL` | Postgres URL. Without it the lab uses a local SQLite file, lost on restart in a container. |
| `DATABASE_SCHEMA` | Put the lab's tables in their own schema (needed when sharing a database with another app). |
| `GROQ_API_KEY`, `GROQ_MODEL` | Or paste the key in Settings instead. |
| `LAB_API_TOKENS` / `LAB_OPEN_ACCESS` | Sign-in token, or `true` to run without sign-in on purpose (a warning banner is shown). Production refuses to start with neither. |
| `LAB_SECRET_KEY` | 32+ characters; encrypts keys saved in Settings. |
| `APP_RATE_LIMIT_PER_MIN`, `APP_CORS_ORIGINS` | Limits and allowed browser origins for `/api/v1`. |

More in `backend/.env.example`. At startup the server logs a self-check: whether Groq answers, and whether the model remembers a name from the start of a long conversation.

## Architecture

One FastAPI process (`backend/main.py`), one Postgres database, no build step on the frontend.

```
 Browser /lab (vanilla ES modules)      Mobile / web apps              Original voice page (/app)
        │  /api/lab/*  (token or open)        │  /api/v1/*  (app key)         │  /api/chat
        ▼                                     ▼                               ▼
   router.py · admin_router.py           api_v1.py                        main.py
        └──────────────┬──────────────────────┴───────────────────────────────┘
                       ▼
   sessions.py + prompts.build_messages  ← the ONLY place model input is built (memory lives here)
                       ▼
   llm.py ── Groq (chat + Whisper) · fallback providers          runner.py ── background tests
                       ▼                                                │
   Postgres (SQLAlchemy models.py, Alembic migrations) ◄────────────────┘
```

**Flows**
- **Test run:** `POST /runs` → `service.create_run` snapshots prompt, moods, rubric into queued conversations → `runner.py` alternates the simulated caller (`simulator.py`) and the assistant → `evaluation.py` scores → UI polls `/runs/{id}`.
- **Talk:** browser records → `/transcribe` (Whisper) → `/live/{id}/turns` → reply spoken by the device, or by Google/Chatterbox via `/speak` (`tts.py`) → `/finish` scores it.
- **App:** key → `/api/v1/sessions` uses the **release** of the key's environment → same `sessions.py` core as Talk.

**Verdict** (`evaluation.compute_verdict`): a failed *must-pass* check fails it; an unscorable check gives `error` (never a silent pass); otherwise weighted score ≥ pass mark.

**Rules that must hold**
1. Every model call goes through `llm.py`; every model input through `prompts.build_messages`. Never slice history elsewhere.
2. Prompt versions are immutable; conversations store snapshots (prompt, mood, rubric), so edits never rewrite history.
3. A release (`Deployment`) fixes prompt version, variables and model settings per environment. Open sessions keep the prompt they started with.
4. Production release evidence counts only runs with the **same version and variables**.
5. Run **one** instance: the job runner is in-process (state is in the DB; `Runner.recover` re-queues work after a restart).
6. Shared database: all tables live in `DATABASE_SCHEMA`; the DB role must have no access to other apps' tables.
7. Changing `models.py` needs `alembic revision --autogenerate`; a test fails if you forget. New NOT NULL columns need a `server_default`.
8. Frontend: no `innerHTML` and no inline `<script>` (tests enforce both). The CSP also blocks inline `style=""` attributes (only the browser enforces that): set styles from JS with `el.style.setProperty`.
9. Provider keys saved in Settings are encrypted (`secrets.py`, `LAB_SECRET_KEY`); client API keys are stored hashed.

**Where to look**

| Symptom | Start here |
|---|---|
| Groq errors, empty or cut-off replies | `llm.py` (`_call_once`, `reasoning_effort`, retries) and the startup `Self-check` log lines |
| Assistant forgets earlier turns | `prompts.py` (`build_messages`, `fit_history`) |
| Wrong pass/fail | `evaluation.py` (judge prompt, verdict), `rules.py` (exact checks) |
| Test stuck on "running" | `runner.py` (`_claim`, `recover`), `conversations.status` in the DB |
| App behaves differently from the lab | `release.py` (active deployment), `api_v1.py`, the key's environment |
| Can't sign in / unexpected open access | `security.py`, `config.validate_for_startup` (`LAB_API_TOKENS`, `LAB_OPEN_ACCESS`) |
| Data gone after a redeploy | `DATABASE_URL` missing: the "Temporary storage" banner shows |
| Server voices (Google, Chatterbox): no sound, wrong voice, monthly limit | `tts.py` (vendor calls), `/speak` and `/settings/tts` in `admin_router.py`, usage counters in `settings_store.py`, `frontend/lab/voice.js` |
| Call notes missing or wrong position | `Note` in `models.py` (migration `0003`), `/conversations/{id}/notes` in `router.py`, `notesPanel` in `frontend/lab/components.js` |
| Call summary wrong or missing, calls not answered, phone line problems | `assistant/service.py` (`run_turn`, `finish_call`), `assistant/prompts.py`, `assistant/phone.py` (signature check first: a 403 means the saved Plivo Auth Token or `PUBLIC_BASE_URL` is wrong) |
| Mic or voice problems | `frontend/lab/views/talk.js` (silence detection), `/transcribe` in `admin_router.py` |
| Schema or migration errors | `models.py`, `alembic/versions/`, `db.py` (schema and pool) |

Logs: Render dashboard → service → Logs. At startup the server logs `Database ready`, `Self-check groq` and `Self-check memory`; if any says FAILED, start there.

## Develop

```bash
cd backend && pip install -r requirements-dev.txt && python -m pytest -q
TEST_DATABASE_URL=postgresql://user@localhost/db python -m pytest -q   # also run everything on Postgres
```
