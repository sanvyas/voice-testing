# Launch guide: sign-in, onboarding, alerts, backups, legal

What is built, what to set on the server, and what only a person can do. Written 2026-11-19.

## 1. Sign in with a phone number
- Owners sign in with their mobile number and a 6-digit SMS code. A new number becomes a new business and goes through the onboarding steps. The session stays on that phone for 90 days.
- Limits: one code per 45 seconds and 5 per hour per number, 20 per hour per address, 5 wrong tries per code, a code works once for 10 minutes.
- **Demo number for testing:** `+91 90000 00001`, code `246810`. It opens a sample shop ("Demo Kirana") with two sample calls and sends no SMS. Switch it off before launch with `MUNSHI_DEMO_LOGIN=off`.
- Try it on the live app before sign-in is compulsory: `https://munshi-r3ws.onrender.com/assistant/?signin=1`
- **Making sign-in compulsory:** set `LAB_API_TOKENS` (a long random admin token) and `LAB_OPEN_ACCESS=false`. Then `/assistant/` shows the sign-in screen to everyone, and `/portal/` asks for the admin token. Existing owner links (`?k=`) keep working.
- **SMS in India needs telecom registration (TRAI "DLT")**: a registered entity, a 6-letter sender ID and an approved OTP template, arranged with your SMS provider (Plivo, or an Indian provider). Then set:
  `MUNSHI_SMS_SENDER`, `MUNSHI_DLT_ENTITY_ID`, `MUNSHI_DLT_TEMPLATE_ID`, `MUNSHI_OTP_TEMPLATE` (the exact approved text, with `{code}`). The Plivo Auth ID and token are the ones saved under Integrations. Until this is done only the demo number can sign in, and the portal checklist says so.
- Local testing only: `MUNSHI_DEV_OTP_LOG=1` writes codes to the server log instead of sending SMS. Never set it in production.

## 2. Onboarding
Six short steps for a new owner (details, timing and address, first rates, languages and voice, the call-forwarding code, a test call). Each step saves as they go. Existing, already set-up shops skip it. Route: `/assistant/#/start`.

## 3. Alerts and backups
- **Alerts:** one row per problem with a count (AI provider failing, AI daily limit reached, SMS not delivering, a business near or over its monthly budget, old-data deletion failing). They show on the portal Overview. Set `ALERT_WEBHOOK_URL` (Slack, Discord or any JSON webhook) to be told; repeats at most every 30 minutes.
- **Uptime monitor:** point it at `/health/deep` (503 if the database is down; `"status":"degraded"` while an error alert is open).
- **Launch checklist:** portal Overview shows every item still needed for launch, with the fix. API: `GET /api/assistant/admin/readiness`.
- **Backups:** `GET /api/assistant/admin/backup` (portal: "Download backup") or `python -m assistant.backup export file.json.gz`; restore with `python -m assistant.backup restore file.json.gz --replace-everything`. The file holds callers' numbers and conversations; keep it private. Keys inside stay encrypted, so a restore needs the same `LAB_SECRET_KEY`. Restores are covered by tests.
  **Still your job:** this is a manual copy, not a schedule. Turn on Supabase's own backups (daily backups need a paid plan; point-in-time recovery is an add-on), and do one test restore. Consider a scheduled job that downloads the file to storage you control.

## 4. Legal and privacy
Pages (public): `/legal/privacy`, `/legal/terms`, `/legal/delete-account` (Hindi summary on each). They describe what the system actually does: transcripts and notes are stored, audio is not kept, our phone provider is asked to delete its copy of each recording, and calls older than 365 days are deleted automatically (`MUNSHI_RETENTION_DAYS`, minimum 30).
- **You must fill in** (server variables; the pages show a visible marker until you do): `LEGAL_ENTITY`, `LEGAL_ADDRESS`, `GRIEVANCE_NAME`, `GRIEVANCE_EMAIL`, `SUPPORT_EMAIL`, `LEGAL_JURISDICTION`. **Have a lawyer read the three pages before launch.** They are a careful draft, not legal advice.
- In the app: consent checkbox at sign-in (version and time recorded), Settings has Download my data, Delete my account and data (type DELETE), Sign out, and links to both policies.
- Every call greeting says it is an AI assistant and that the conversation is noted.
- Google Play (when you publish an Android app): it requires an in-app way to delete the account **and** a web link for it. Use `https://<your host>/legal/delete-account` in the Data safety form, and answer the form from section 2 of the privacy policy.

### What the rules say (and how sure we are)
- **DPDP Act and Rules:** the Rules were notified in November 2025 and start in phases. The main duties on businesses (notice and consent, security, breach reporting, retention, grievance system with a reply within at most 90 days) apply from about May 2027. Nothing found gives small businesses an exemption. We already follow these now; the pages commit to a 30-day reply. Check the official text at meity.gov.in.
- **TRAI and AI calls:** several sources describe a draft requirement that AI voice calls say so at the start, and consent practices for recording. We could not confirm from TRAI's own text what is in force, so we do both anyway (the greeting says AI and "conversation is noted"). Sector rules (insurance, banking) may add recording duties. Ask counsel.
- **SMS:** OTP and transactional SMS in India need DLT registration (see section 1).

### Things only a person can finish
1. Fill the six legal variables and have the pages reviewed.
2. Register for DLT and set the SMS variables.
3. Sign data-processing terms with the providers that handle personal data (Render, Supabase, Groq, Google Cloud, Plivo, and Meta/Sarvam/DeepInfra if used). Check where Render and Supabase servers are, and say so in the policy if outside India.
4. Turn on and test database backups.
5. Appoint the grievance officer and watch that mailbox.

## Not covered here yet
Voice providers (speech-to-text and text-to-speech choices, cost and fallbacks), turning the web app into an installable Android/iOS app (PWA, Play Store listing), and the hosting plan (always-on service, region close to India). These are the next planning items.

## Sources
- DPDP Rules 2025 summaries: [SCC Online](https://www.scconline.com/blog/post/2025/12/26/digital-personal-data-protection-rules-2025-key-highlights/), [Khaitan & Co](https://www.khaitanco.com/sites/default/files/2025-11/ERGO%20-%20Digital%20Personal%20%20Data%20Protection%20Rules%20-%2015%20November%202025.pdf), [Baker Botts](https://ourtake.bakerbotts.com/post/102lund/india-notifies-final-rules-for-digital-data-protection-act)
- AI calling, recording consent and DLT (vendor commentary, not regulator text): [Exotel](https://exotel.com/glossary/call-recording-compliance-in-india/), [Caller.Digital](https://caller.digital/blog/voice-ai-compliance-stack-india-2026), [Edesy](https://edesy.in/blog/trai-regulations-ai-calling-india.md)
- Google Play account deletion: [Google Play Help](https://support.google.com/googleplay/android-developer/answer/13327111)
