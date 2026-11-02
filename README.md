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

## Develop

```bash
cd backend && pip install -r requirements-dev.txt && python -m pytest -q
TEST_DATABASE_URL=postgresql://user@localhost/db python -m pytest -q   # also run everything on Postgres
```
