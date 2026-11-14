#!/usr/bin/env bash
# Usage: read_post.sh <instagram post/reel URL> <output dir>
# Public posts only. Writes caption.txt, info.json, comments.txt, video.mp4, sheet.png. Stops on any refusal.
set -u
URL="$1"; OUT="$2"; mkdir -p "$OUT"; cd "$OUT" || exit 1
export PATH="$HOME/.local/bin:$PATH"
SC=$(printf '%s' "$URL" | sed -E 's#.*/(p|reel|reels|tv)/([^/?]+).*#\2#')
curl -sS -m 30 "https://www.instagram.com/p/$SC/embed/captioned/" -o embed.html || echo "embed: failed"
python3 -I - <<'PY'
import re,html
s=open("embed.html",encoding="utf8",errors="ignore").read()
m=re.search(r'class="Caption".*?</div>\s*</div>',s,re.S)
t=html.unescape(re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',m.group(0)))) if m else "NO CAPTION (embed refused or changed)"
open("caption.txt","w").write(t); print("CAPTION:",t[:600])
PY
yt-dlp --no-playlist --write-info-json --skip-download -o info "$URL" >/dev/null 2>&1 && mv info.info.json info.json 2>/dev/null
python3 -I - <<'PY'
import json,os
if os.path.exists("info.json"):
    d=json.load(open("info.json")); print("uploader:",d.get("uploader"),"| likes:",d.get("like_count"),"| comments:",d.get("comment_count"),"| time:",d.get("timestamp"))
    open("comments.txt","w").write("\n".join(f'{c.get("author")}: {c.get("text")}' for c in d.get("comments") or []))
    print("comments fetched:",len(d.get("comments") or []))
else: print("yt-dlp metadata: refused")
PY
yt-dlp --no-playlist -f 'worst[ext=mp4]/worst' -o 'video.%(ext)s' "$URL" >/dev/null 2>&1 || echo "video: blocked (CDN host not allowed or login needed)"
[ -f video.mp4 ] && ffmpeg -loglevel error -y -i video.mp4 -vf "fps=1/3,scale=420:-1,tile=3x3" -frames:v 1 sheet.png && echo "frames: sheet.png (view it)"
