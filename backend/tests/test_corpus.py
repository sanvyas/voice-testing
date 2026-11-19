"""The conversation corpus in /corpus must stay valid: every rule in corpus/validate.py, plus coverage."""
import json
import sys
from collections import Counter
from pathlib import Path

CORPUS = Path(__file__).resolve().parents[2] / "corpus"
sys.path.insert(0, str(CORPUS))
import validate as v  # noqa: E402


def load():
    return [json.loads(line) for line in (CORPUS / "conversations.jsonl").read_text(encoding="utf-8").splitlines()]


def test_every_conversation_passes_the_rules():
    problems = {c["id"]: e for c in load() if (e := v.validate(c))}
    assert not problems, problems


def test_enough_variety():
    convs = load()
    assert len(convs) >= 300
    assert len({c["id"] for c in convs}) == len(convs)
    assert len({tuple(t["text"] for t in c["turns"]) for c in convs}) == len(convs), "duplicate conversations"
    assert {c["lang"] for c in convs} == {"hi", "hing", "en"}
    assert len({c["pack"] for c in convs}) >= 10
    labels = Counter(c["importance"] for c in convs)
    assert all(labels[k] >= 40 for k in ("action", "fyi", "ignore")), labels
    for family in ("order", "enquiry", "complaint", "message", "sales", "noise", "integrity", "safety", "language"):
        assert any(c["family"] == family for c in convs), family


def test_corpus_file_is_current():
    """conversations.jsonl must match what build.py produces (nobody edited one without the other)."""
    sys.path.insert(0, str(CORPUS))
    import build
    built = [json.dumps(c, ensure_ascii=False) for c in build.build()]
    assert built == (CORPUS / "conversations.jsonl").read_text(encoding="utf-8").splitlines()


def test_validator_catches_bad_conversations():
    good = next(c for c in load() if c["lang"] == "en" and c["family"] == "order")
    assert not v.validate(good)
    def bad(edit):
        c = json.loads(json.dumps(good)); edit(c); return v.validate(c)
    assert bad(lambda c: c["turns"][2].update(text="I promise it will be ready tonight. Thank you."))
    assert bad(lambda c: c["turns"][2].update(text="Please tell me your phone number."))
    assert bad(lambda c: c["turns"][2].update(text="That will be 9999 rupees."))
    assert bad(lambda c: c["turns"][2].update(text="I am a GPT assistant."))
    assert bad(lambda c: c["turns"][2].update(text="नमस्ते " + "बहुत " * 40))
