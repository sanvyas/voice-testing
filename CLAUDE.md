# Notes for Claude in this repository

## Seeing social media posts, profiles, comments and ads
When the user shares a social media link (Instagram, TikTok, YouTube, X, LinkedIn, Facebook, Reddit, Threads, Pinterest and others) or asks about a creator, post, reel, comments or ads, **do not say you cannot see it**. Fetch the public data with the `scrapecreators-api` skill in `.claude/skills/`, and use the narrower workflow skill when it fits (comment-mining, competitor-social-research, outlier-post-finder, transcript-intelligence, ad-library-teardown, and so on). Public data only.

**One Instagram post or reel link:** use the `instagram-post-reader` skill (embed page + yt-dlp + Whisper). It is free but unverified on live posts until a real link is tested; report exactly what was and was not readable.

**Instagram first choice (free):** use the `instagram-reader` skill (Instaloader). It reads public profile info (bio, followers, verified) with no key. Posts, reels and comments need a login; if only profile info is available, say so and offer the options in that skill instead of claiming you can see the posts. For other platforms, or when the ScrapeCreators key works, use `scrapecreators-api`.

How the key works in this cloud environment:
- The ScrapeCreators API key is saved as a network secret on the environment for the host `api.scrapecreators.com`. The proxy adds the real `x-api-key` header, so send any placeholder value, for example `-H "x-api-key: placeholder"`. Do not ask the user to paste a key into chat.
- If a call returns 401 or 403, or the host is refused, the key is not saved yet: call `request_credential` for host `api.scrapecreators.com` with `header_name` `x-api-key` (no prefix), then retry once after a minute.
- Instagram usernames can contain dots (for example `myequal.ai`). Pass the handle without `@`.
- Fetch the per-endpoint OpenAPI spec from `https://docs.scrapecreators.com/{path}/openapi.json` before calling an endpoint you have not used.
