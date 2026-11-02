# Voice Test Lab

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
- **Talk:** browser records → `/transcribe` (Whisper) → `/live/{id}/turns` → reply spoken by the device → `/finish` scores it.
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
8. Frontend: no `innerHTML` and no inline script/style (the CSP blocks them; tests enforce). Set styles with `el.style.setProperty`.
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
| Mic or voice problems | `frontend/lab/views/talk.js` (silence detection), `/transcribe` in `admin_router.py` |
| Schema or migration errors | `models.py`, `alembic/versions/`, `db.py` (schema and pool) |

Logs: Render dashboard → service → Logs. At startup the server logs `Database ready`, `Self-check groq` and `Self-check memory`; if any says FAILED, start there.

## Develop

```bash
cd backend && pip install -r requirements-dev.txt && python -m pytest -q
TEST_DATABASE_URL=postgresql://user@localhost/db python -m pytest -q   # also run everything on Postgres
```
