---
name: instagram-reader
description: Free, open-source way to read a PUBLIC Instagram profile (bio, followers, verified, profile photo link) with Instaloader, and public posts/reels when a user-supplied login session is available. Use when the user shares an Instagram link or handle (instagram.com/<handle>, with or without ?srtk= or ?rpxt= tracking) and wants to see the account, its bio, or its content. Prefer this first for Instagram; use scrapecreators-api for other platforms or when a ScrapeCreators key works.
---

# Instagram reader (Instaloader, MIT, free)

Tool: [Instaloader](https://instaloader.github.io/) (PyPI package `instaloader`, MIT). Public data only. Never log in with the user's real account, never ask for a password in chat, never spoof app headers or user-agents to get around Instagram's login wall.

## Setup (once per container)
```bash
uv tool install instaloader   # or: pip install instaloader
```
Network: the environment must allow `www.instagram.com` (and `i.instagram.com`, `graph.instagram.com` if asked). `*.cdninstagram.com` is not needed for text.

## What works without a login (tested on a public account)
Profile metadata: handle, full name, bio, follower and following counts, verified flag, private flag, profile photo URL.
```bash
D=$(mktemp -d) && cd "$D" && instaloader --no-pictures --no-videos --no-video-thumbnails --no-compress-json --count 0 -- profile <handle>
python3 -I -c "import json,glob;n=json.load(open(glob.glob('<handle>/*.json')[0]))['node'];print(n['full_name'],n['biography'],n['edge_followed_by']['count'],n['is_verified'])"
```
Strip tracking params and use only the handle (dots allowed, no `@`).

## What does NOT work without a login
Posts, reels, captions, likes and comments. Instaloader reports `Redirected to login page`. Do not try to work around it. Say so plainly, then offer:
1. A throwaway Instagram account's cookies exported by the user (`--load-cookies`), saved as a secret/file by the user, never pasted in chat. Read-only use, a few requests, slow pace. Accounts can be restricted for automated use: warn the user.
2. The official Instagram Business Discovery API (needs the user's own Business/Creator account + token).
3. The user sends screenshots or screen recordings.
4. `scrapecreators-api`, if its key is valid.

## Reporting
State what was read and what was not. Never invent posts, captions or numbers. Followers etc. are as of the fetch time.
