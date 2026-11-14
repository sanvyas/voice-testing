---
name: instagram-post-reader
description: Read ONE public Instagram post or reel from its URL (instagram.com/p/..., /reel/..., /tv/...): caption, author, date, counts, thumbnail, the video file, and a spoken-word transcript. Use when the user shares an Instagram post or reel link and wants to know what it says or shows, how it is pitched, its hook, captions or script. For the account itself (bio, followers) use instagram-reader. Free, open source, no key.
---

# Instagram post reader (yt-dlp + Instagram's public embed page + Whisper)

No single free tool returns a whole Instagram post. Combine three, in this order, and report what each one returned.

Rules: public posts only. No login with the user's real account, no password in chat, no spoofed app headers or crawler user-agents, no retry loops when Instagram asks for a login. If every step is refused, say so and ask the user for the caption or a screen recording.

## 0. Setup (once per container)
```bash
uv tool install yt-dlp     # MIT/Unlicense, https://github.com/yt-dlp/yt-dlp
```
Network must allow `www.instagram.com`; the video file comes from `*.cdninstagram.com` (allow it, or skip step 2).

## 1. Caption, author, counts: Instagram's own embed page
Instagram serves every public post at its embed address, the same page websites use to embed posts. Fetch it with a normal request (default client, no header tricks):
```bash
curl -sS -m 30 "https://www.instagram.com/p/<SHORTCODE>/embed/captioned/" -o post.html
```
`<SHORTCODE>` is the part after `/p/` or `/reel/`. Read the caption, username and comment count from the HTML (community-documented, not an official API; Instagram can change it). Treat the result as unverified until it shows the real caption.

## 2. Metadata and video: yt-dlp
```bash
D=$(mktemp -d) && cd "$D" && yt-dlp --no-playlist --write-info-json --skip-download "<POST_URL>"   # metadata only
yt-dlp --no-playlist -f "worst[ext=mp4]/worst" -o video.%(ext)s "<POST_URL>"                      # small video for transcript
```
`info.json` has description (caption), uploader, timestamp, like/comment counts and duration when Instagram allows it. "login required" or "rate-limit reached" means stop; do not hunt for workarounds.

## 3. Transcript of what is said (reels)
Needs the video from step 2 and a Whisper service. The project already uses Groq Whisper (`whisper-large-v3-turbo`, host `console.groq.com` / `api.groq.com`; GROQ key via the environment). Extract audio (`ffmpeg -i video.mp4 -vn -ac 1 -ar 16000 audio.mp3`) and send it to the transcription endpoint, or run local `faster-whisper`. Label the language and say the transcript is machine-made.

## 4. Looking at what is on screen
Take 5 to 8 frames (`ffmpeg -i video.mp4 -vf fps=1/3 f_%02d.png`) and view them to describe visuals, text overlays, hook and branding. Say which frames you actually viewed.

## Report
For every post state: what you read (caption / counts / transcript / frames), what was blocked, and never invent numbers, captions or comments. Comments: yt-dlp's info.json can include a sample of top-level comments (12 of 22 on the test reel); say it is a sample.

## Helper
`bash .claude/skills/instagram-post-reader/read_post.sh "<POST_URL>" <outdir>` runs steps 1, 2 and 4 and prints what it got.

## Whole profile ("every post")
There is no free, login-free way to LIST a profile's posts: Instaloader redirects to the login page and yt-dlp's profile extractor is marked broken. Do not work around it. Ways to get the list:
1. The user pastes the post/reel links (or the account's top 5 to 20); run `read_post.sh` on each, then summarise the set (hooks, topics, formats, branding).
2. `scrapecreators-api` if its key is valid (lists posts and reels with counts).
3. A throwaway account's cookies exported by the user, used with Instaloader `--load-cookies`.
Transcripts need a Whisper service; if no key is available, say the audio was not transcribed (many reels are text-on-screen with music only).

## Verified
Tested on a public reel: caption, counts, 12 comments and the video (after allowing the exact CDN hosts `scontent-*.cdninstagram.com` shown in the yt-dlp error) all came through; profile listing did not.
