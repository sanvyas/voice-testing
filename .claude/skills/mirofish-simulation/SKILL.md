---
name: mirofish-simulation
description: Run MiroFish (open-source multi-agent swarm simulation, github.com/666ghj/MiroFish) to rehearse how a community of people reacts to a product, message or decision, and how opinions spread between them. Use when the user wants to simulate users' reactions, adoption, objections and word of mouth, or "what would make them use it". Needs an OpenAI-compatible LLM key and a Zep Cloud key. Complements the individual buyer panel (founder-consumer): MiroFish adds interaction between people.
---

# MiroFish simulation for product adoption

MiroFish builds a knowledge graph from seed documents, turns the people in it into agents with personalities and memory, lets them post, reply and react on a simulated Twitter-like and Reddit-like platform for N rounds, then writes a report and lets you interview any agent. License: AGPL-3.0. We run it locally as a tool and do not copy its code into our product.

## When to use it (and when not)
- Use it for **social dynamics**: which objection spreads, who influences whom, what a trusted sceptic does to a launch, what a founder's answer changes.
- Do not use it as a poll or a forecast. Agents are LLM role-play: they lean agreeable and invent detail. Treat every share as an upper bound and compare against the 100-buyer panel (`founder/panel/insights.md`) and real owners.
- It is heavy on LLM calls. Start small (fewer than 40 rounds, 30-ish agents) and watch cost and rate limits.

## Needs
- A local clone: `GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/666ghj/mirofish` (read-only; add_repo shows it is served anonymously).
- Python 3.11 or 3.12 (not 3.13) and `uv`: `cd backend && uv sync --python 3.12`.
- `.env` in the repo root with `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL_NAME` (any OpenAI-format API) and `ZEP_API_KEY` (Zep Cloud free tier). In this cloud environment keys go through `request_credential` for the host (the proxy injects the real header), so put a placeholder value in `.env`. Never ask the user to paste a key in chat.
- Network: the LLM host and `api.getzep.com` must be reachable (saving a credential for a host allows it).

## Steps
1. Write the seed brief (facts and setting only; no predicted results, no earlier panel conclusions). Example: `seed-munshi.md` in this folder.
2. Write the requirement in plain language: the question, the horizon (e.g. 30 days), and what the report must cover (who adopts, who pays, objections that spread, what changes minds, what could kill it).
3. Start the backend: `cd backend && uv run python run.py` (Flask API). Then call, in order: `POST /api/graph/ontology/generate` (seed file plus requirement), `POST /api/graph/build`, `POST /api/simulation/create`, `POST /api/simulation/prepare` (poll `/prepare/status`), `POST /api/simulation/start` (set a small `max_rounds`), poll `/api/simulation/<id>/run-status`, then `POST /api/report/generate`. Read each route's fields in `backend/app/api/*.py` before calling; they can change.
4. Read what happened, not only the report: `/api/simulation/<id>/posts`, `/comments`, `/timeline`, `/agent-stats`.
5. Interview agents with `POST /api/simulation/interview` or `/interview/batch`, for example the passers: "what would make you try it?".
6. Report: the question, setup (agents, rounds, model), findings with quoted posts, the comparison with the buyer panel, and the limits above. Say plainly what was and was not run.

## Rules
- Label all output as simulated. No simulated quote goes into an ad or a pitch.
- Keep the run small first, show cost and rate-limit failures honestly, and stop on repeated 429s rather than looping.
