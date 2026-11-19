"""Expand situations x businesses x languages into labelled conversations.

    python3 build.py        # writes conversations.jsonl, SAMPLE.md, STATS.md (and fails if any conversation breaks a rule)

Everything is deterministic: the same inputs always give the same file.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import skeletons_a, skeletons_b, skeletons_c  # noqa: E402,F401  (importing registers the situations)
from packs import CALLERS, PACK_BY_ID, PACKS  # noqa: E402
from sk import ALL  # noqa: E402
from validate import validate  # noqa: E402

LANGS = ["hi", "hing", "en"]
PER_SKELETON = 6
GREETING = {
    "hi": "नमस्ते, मैं Munshi हूँ, {shop} का AI सहायक। बताइए, कैसे मदद करूँ?",
    "hing": "Namaste, main Munshi hoon, {shop} ka AI assistant. Bataiye, kaise madad karun?",
    "en": "Hello, I am Munshi, the AI assistant of {shop}. How can I help you?",
}
PER_UNIT_HI = {"किलो", "लीटर", "पीस", "प्लेट", "महीना"}
SLOT = re.compile(r"\{(\w+)\}")


def price_text(item, lang):
    _, _, price, u_hi, u_en, _, _ = item
    if lang == "hi":
        return f"₹{price} {u_hi}" if u_hi == "से शुरू" else (f"₹{price} प्रति {u_hi}" if u_hi in PER_UNIT_HI else f"₹{price}")
    return f"₹{price} onwards" if u_en == "onwards" else (f"₹{price} per {u_en}" if u_en else f"₹{price}")


def kb_for(pack, lang):
    i = 0 if lang == "hi" else 1
    return dict(
        shop=pack["shop"][i], owner=pack["owner"][i], addr=pack["addr"][i], hours=pack["hours"][i], delivery=pack["delivery"][i], rule=pack["rule"][i], extra=pack["extra"][i],
        items=[dict(name=it[i], price=price_text(it, lang), unit=it[3 + i]) for it in pack["items"] if it[2] > 0],
    )


def fill(skel, pack, lang, k):
    """Return the filled lines, or None when this business cannot play this situation (e.g. no delivery, no prices)."""
    lines = skel[lang]
    need = set(SLOT.findall(" ".join(lines)))
    i = 0 if lang == "hi" else 1
    items = pack["items"]
    n = len(items)
    chosen = None
    for off in range(n):
        it = items[(k + off) % n]
        if ({"price", "price2"} & need and it[2] <= 0) or ("qty" in need and not it[5]):
            continue
        chosen = it
        break
    if chosen is None:
        return None
    second = None
    for off in range(1, n + 1):
        it = items[(items.index(chosen) + off) % n]
        if it is not chosen and (it[2] > 0 or not ({"price2"} & need)):
            second = it
            break
    if "item2" in need or "price2" in need:
        if second is None or second[2] <= 0:
            return None
    base = k * 3 + len(skel["id"])
    caller = next(c for c in (CALLERS[(base + d) % len(CALLERS)] for d in range(len(CALLERS))) if c[0] not in pack["owner"][0] and c[1] not in pack["owner"][1])
    slots = dict(
        shop=pack["shop"][i], owner=pack["owner"][i], c=caller[i], item=chosen[i], price=price_text(chosen, lang), qty=chosen[5 + i], unlisted=pack["unlisted"][i],
        hours=pack["hours"][i], addr=pack["addr"][i], delivery=pack["delivery"][i], rule=pack["rule"][i], extra=pack["extra"][i],
        item2=second[i] if second else "", price2=price_text(second, lang) if second else "",
    )
    for name in need:
        if name not in slots:
            raise KeyError(f"{skel['id']}: unknown slot {{{name}}}")
        if not slots[name]:
            return None
    out = []
    for ln in lines:
        role, text = ln.split(": ", 1)
        out.append(dict(role="assistant" if role == "M" else "caller", text=SLOT.sub(lambda m: slots[m.group(1)], text)))
    return out


def build():
    convs = []
    for idx, skel in enumerate(ALL):
        eligible = [PACK_BY_ID[p] for p in skel["packs"]] if skel["packs"] else list(PACKS)
        start = (idx * 3) % len(eligible)
        made = 0
        for j in range(len(eligible)):
            if made >= PER_SKELETON:
                break
            pack = eligible[(start + j) % len(eligible)]
            lang = LANGS[(idx + made) % 3]
            turns = fill(skel, pack, lang, idx + j)
            if turns is None:
                continue
            turns.insert(0, dict(role="assistant", text=GREETING[lang].format(shop=pack["shop"][0 if lang == "hi" else 1])))
            convs.append(dict(
                id=f"{skel['id']}-{pack['id']}-{lang}", lang=lang, pack=pack["id"], kind=pack["kind"], family=skel["family"], importance=skel["importance"], category=skel["category"],
                needs_owner=skel["importance"] == "action", end=skel["end"], must=skel["must"], no=skel["no"], kb=kb_for(pack, lang), turns=turns,
            ))
            made += 1
    return convs


def sample(convs):
    pick = {}
    for c in convs:
        pick.setdefault((c["family"], c["lang"]), c)
    lines = ["# Sample conversations", "", "Generated examples, not recordings of real calls. `C` is the caller, `M` is Munshi.", ""]
    for c in list(pick.values())[:18]:
        lines += [f"## {c['id']}", f"*{c['kind']}, {c['lang']}, {c['family']}. Label: **{c['importance']}** / {c['category']}. A good reply: {', '.join(c['must'])}*", ""]
        lines += [f"- **{'M' if t['role'] == 'assistant' else 'C'}:** {t['text']}" for t in c["turns"]] + [""]
    return "\n".join(lines)


def stats(convs):
    def table(title, counter):
        return [f"## {title}", ""] + [f"- {k}: {v}" for k, v in sorted(counter.items())] + [""]
    words = [len(t["text"].split()) for c in convs for t in c["turns"] if t["role"] == "assistant"]
    out = [f"# Corpus stats", "", f"Conversations: **{len(convs)}**. Munshi turns: {len(words)}, average {sum(words) / len(words):.1f} words, longest {max(words)}.", ""]
    out += table("By label (what the owner sees)", Counter(c["importance"] for c in convs))
    out += table("By language", Counter(c["lang"] for c in convs))
    out += table("By business", Counter(c["pack"] for c in convs))
    out += table("By family", Counter(c["family"] for c in convs))
    out += table("Behaviour tags exercised", Counter(t for c in convs for t in c["must"]))
    return "\n".join(out)


if __name__ == "__main__":
    convs = build()
    bad = {c["id"]: e for c in convs if (e := validate(c))}
    if bad:
        for k, v in bad.items():
            print(k, "->", "; ".join(v))
        sys.exit(f"{len(bad)} conversations break the rules")
    ids = [c["id"] for c in convs]
    assert len(ids) == len(set(ids)), "duplicate ids"
    (HERE / "conversations.jsonl").write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in convs) + "\n", encoding="utf-8")
    (HERE / "SAMPLE.md").write_text(sample(convs), encoding="utf-8")
    (HERE / "STATS.md").write_text(stats(convs), encoding="utf-8")
    print(len(convs), "conversations written")
