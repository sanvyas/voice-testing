"""Replay corpus callers against a live Munshi agent and check what it says.

    python3 replay.py https://your-host --pack kirana [--limit 40] [--out report.md]

Creates a throwaway business through the admin API (needs open access or an admin token in MUNSHI_ADMIN_TOKEN), plays each conversation's
caller lines in order, validates every reply with validate.py, compares the call notes' label with the corpus label, then deletes the business.
Nothing here uses real customer data. It spends real LLM quota, so it paces itself.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from packs import PACK_BY_ID  # noqa: E402
from validate import validate  # noqa: E402


class Api:
    def __init__(self, base, token=""):
        self.base, self.token, self.key, self.business = base.rstrip("/"), token, "", ""

    def call(self, method, path, body=None, owner=False, retries=4):
        headers = {"content-type": "application/json"}
        if self.token:
            headers["authorization"] = "Bearer " + self.token
        if owner:
            headers["x-business-key"] = self.key
        data = json.dumps(body).encode() if body is not None else None
        for attempt in range(retries):
            req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=90) as r:
                    raw = r.read()
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as e:
                text = e.read().decode("utf-8", "replace")[:300]
                if e.code in (429, 502, 503) and attempt < retries - 1:
                    time.sleep(20 * (attempt + 1))
                    continue
                raise RuntimeError(f"{method} {path} -> {e.code} {text}") from None


def setup(api, pack):
    p = pack
    made = api.call("POST", "/api/assistant/admin/businesses", dict(name=p["shop"][1] + " (replay test, delete me)", owner_name=p["owner"][1].replace(" ji", "")))
    api.business = made["id"]
    api.name = made["name"]
    api.key = made["link"].split("?k=")[1]
    saved = api.call("PUT", "/api/assistant/profile", dict(
        business_name=p["shop"][1], owner_name=p["owner"][1].replace(" ji", ""), about=f"A {p['kind']}.", hours=p["hours"][1], address=p["addr"][1], mode="board", ui_lang="en",
        faq="\n".join(x for x in (p["delivery"][1] and "Delivery: " + p["delivery"][1], p["extra"][1]) if x), rules=p["rule"][1], languages=["hi", "en"]), owner=True)
    api.name = saved.get("business_name") or api.name
    api.names = [saved.get("business_name", ""), saved.get("owner_name", "")]
    for it in p["items"]:
        if it[2] > 0:
            unit = f"/{it[4]}" if it[4] and it[4] != "onwards" else ""
            api.call("POST", "/api/assistant/board", dict(name=it[1], price=f"Rs {it[2]}{unit}", status="in_stock"), owner=True)


def _strip(text, names):
    """The shop's and owner's names are typed by the owner in any script, so they are not held to the language rules."""
    for n in sorted(filter(None, names), key=len, reverse=True):
        text = text.replace(n, "NAME")
    return text.replace("NAME जी", "NAME").replace("NAME", "")


def play(api, conv, number, pause):
    started = api.call("POST", "/api/assistant/calls", dict(caller_number=number), owner=True)
    cid = started["call"]["id"]
    turns = [dict(role="assistant", text=started["greeting"])]
    ended = False
    callers = [t["text"] for t in conv["turns"] if t["role"] == "caller"]
    for line in callers:
        time.sleep(pause)
        try:
            r = api.call("POST", f"/api/assistant/calls/{cid}/turns", dict(content=line), owner=True)
        except RuntimeError as e:
            turns.append(dict(role="caller", text=line))
            turns.append(dict(role="assistant", text=f"[ERROR {e}]"))
            break
        turns += [dict(role="caller", text=line), dict(role="assistant", text=r["assistant"]["content"])]
        if r["ended"]:
            ended = True
            break
    time.sleep(pause)
    try:
        done = api.call("POST", f"/api/assistant/calls/{cid}/end", owner=True)
    except RuntimeError as e:
        done = {"error": str(e)}
    detail = api.call("GET", f"/api/assistant/calls/{cid}", owner=True)
    return turns, ended, detail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--pack", default="kirana")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--families", default="")
    ap.add_argument("--pause", type=float, default=5)
    ap.add_argument("--out", default=str(HERE / "REPLAY.md"))
    ap.add_argument("--keep", action="store_true", help="do not delete the throwaway business")
    a = ap.parse_args()
    convs = [json.loads(x) for x in open(HERE / "conversations.jsonl", encoding="utf-8")]
    convs = [c for c in convs if c["pack"] == a.pack and (not a.families or c["family"] in a.families.split(","))]
    if a.limit:
        convs = convs[: a.limit]
    pack = PACK_BY_ID[a.pack]
    api = Api(a.base, os.environ.get("MUNSHI_ADMIN_TOKEN", ""))
    setup(api, pack)
    rows, md = [], []
    try:
        for n, c in enumerate(convs):
            turns, ended, detail = play(api, c, f"+91 96000 8{n:04d}", a.pause)
            clean_turns = [dict(t, text=_strip(t["text"], api.names)) for t in turns]
            probe = dict(c, turns=clean_turns, must=[], end=ended, lang="hi" if c["lang"] in ("hi", "hing") else "en")  # Hinglish callers are answered in Devanagari on purpose, so the voice reads it right
            issues = [i for i in validate(probe) if not i.startswith("turn 0") and "unfilled slot" not in i]
            if not any(t["role"] == "caller" for t in turns[1:]):
                issues.append("no turns played")
            got = detail.get("importance")
            label_ok = got == c["importance"]
            rows.append(dict(id=c["id"], lang=c["lang"], family=c["family"], want=c["importance"], got=got, ended=ended, issues=issues, label_ok=label_ok, summary=detail.get("summary"), turns=turns))
            if issues or not label_ok:
                for t in turns:
                    print("      ", "M" if t["role"] == "assistant" else "C", t["text"][:160].replace("\n", " "), flush=True)
                print("       issues:", "; ".join(issues)[:300], "| notes:", detail.get("summary"), flush=True)
            print(f"{c['id']:42} want={c['importance']:6} got={str(got):6} ended={ended!s:5} issues={len(issues)}", flush=True)
    finally:
        if not a.keep and api.business:
            try:
                api.call("POST", f"/api/assistant/admin/businesses/{api.business}/delete", dict(confirm_name=api.name))
                print("throwaway business deleted")
            except Exception as e:  # noqa: BLE001
                print("COULD NOT DELETE the throwaway business:", e)
    ok_labels = sum(r["label_ok"] for r in rows)
    clean = sum(not r["issues"] for r in rows)
    md += [f"# Live replay: {a.pack}", "", f"{len(rows)} conversations. Label matches: **{ok_labels}/{len(rows)}**. No rule broken: **{clean}/{len(rows)}**.", ""]
    for r in rows:
        flag = "ok" if r["label_ok"] and not r["issues"] else "CHECK"
        md += [f"## {flag} {r['id']}", f"label want `{r['want']}`, got `{r['got']}`; ended by the agent: {r['ended']}; notes: {r['summary']}", ""]
        if r["issues"]:
            md += ["Problems: " + "; ".join(r["issues"]), ""]
        md += [f"- **{'M' if t['role'] == 'assistant' else 'C'}:** {t['text']}" for t in r["turns"]] + [""]
    Path(a.out).write_text("\n".join(md), encoding="utf-8")
    print(f"label matches {ok_labels}/{len(rows)}, rule-clean {clean}/{len(rows)}; report: {a.out}")


if __name__ == "__main__":
    main()
