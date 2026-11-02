import json

import pytest

from lab import evaluation, rules
from lab.evaluation import ParamResult, compute_verdict, parse_judge_json
from lab.templating import TemplateError, extract_variables, merge_values, render


# --- templating ---
def test_extract_and_render():
    t = "Hi {{ name }}, be {{tone}}. {{name}} again. {{ 1bad }}"
    assert extract_variables(t) == ["name", "tone"]
    assert render("Hi {{ name }}!", {"name": "Sam"}) == "Hi Sam!"


def test_render_missing_strict_and_lenient():
    with pytest.raises(TemplateError, match="tone"):
        render("{{name}} {{tone}}", {"name": "x"})
    assert render("{{name}} {{tone}}", {"name": "x"}, strict=False) == "x {{tone}}"


def test_render_does_not_rescan_substituted_values():
    assert render("{{a}}", {"a": "{{b}}", "b": "SECRET"}) == "{{b}}"


def test_merge_values_layers_and_empty_override():
    assert merge_values({"a": "1", "b": "2"}, {"b": ""}, {"c": "3"}) == {"a": "1", "b": "", "c": "3"}


# --- rules ---
def R(*texts, lat=None):
    return [rules.Reply(i + 1, t, (lat[i] if lat else None)) for i, t in enumerate(texts)]


def test_sentence_and_word_counts():
    assert rules.count_sentences("One. Two! Three? Four") == 4
    assert rules.count_sentences("It costs 3.5 dollars. Fine.") == 2
    assert rules.count_words("I don't know, it's fine") == 5


def test_max_sentences_with_allowance():
    cfg = rules.validate_rule_config({"rule": "max_sentences_per_reply", "max": 2, "allow_violations": 1})
    ok = rules.run_rule(cfg, R("One. Two.", "A. B. C. D."))
    assert ok.passed and ok.score == 0.5
    bad = rules.run_rule(cfg, R("A. B. C.", "A. B. C. D."))
    assert not bad.passed and "turn 1" in bad.reasoning


def test_pass_and_fail_explanations_read_correctly():
    q = rules.validate_rule_config({"rule": "max_questions_per_reply", "max": 1})
    assert rules.run_rule(q, R("One?")).reasoning == "All 1 replies asked at most 1 question(s)."
    assert "asked too many questions" in rules.run_rule(q, R("A? B?")).reasoning
    f = rules.validate_rule_config({"rule": "no_formatting"})
    assert rules.run_rule(f, R("Fine.")).reasoning == "All 1 replies had no markup or emoji."
    w = rules.validate_rule_config({"rule": "max_words_per_reply", "max": 3})
    assert "stayed within the word limit" in rules.run_rule(w, R("Hi there")).reasoning


def test_questions_and_ratio():
    cfg = rules.validate_rule_config({"rule": "max_questions_per_reply", "max": 1})
    assert not rules.run_rule(cfg, R("Why? And how?")).passed
    ratio = rules.validate_rule_config({"rule": "min_question_ratio", "min_ratio": 0.5})
    assert rules.run_rule(ratio, R("Hm?", "No.")).passed
    assert not rules.run_rule(ratio, R("No.", "No.", "Hm?")).passed


def test_no_formatting_detects_markdown_and_emoji():
    cfg = rules.validate_rule_config({"rule": "no_formatting"})
    assert rules.run_rule(cfg, R("Plain spoken words.")).passed
    for bad in ["- one\n- two", "1. first", "## Heading", "This is **bold**", "Great job 😊"]:
        assert not rules.run_rule(cfg, R(bad)).passed, bad


def test_contains_and_not_contains_scopes():
    any_ = rules.validate_rule_config({"rule": "contains_any", "phrases": ["emergency services"], "scope": "any_reply"})
    assert rules.run_rule(any_, R("hi", "please call emergency services")).passed
    last = rules.validate_rule_config({"rule": "contains_any", "phrases": ["emergency services"], "scope": "last_reply"})
    assert not rules.run_rule(last, R("call emergency services", "hi")).passed
    forbid = rules.validate_rule_config({"rule": "not_contains_any", "phrases": ["as your therapist"]})
    out = rules.run_rule(forbid, R("fine", "As Your Therapist I say"))
    assert not out.passed and out.score == 0.5


def test_regex_rules_and_validation():
    m = rules.validate_rule_config({"rule": "regex_match", "pattern": r"\b988\b|\b112\b"})
    assert rules.run_rule(m, R("call 112 now")).passed
    with pytest.raises(ValueError, match="Invalid regex"):
        rules.validate_rule_config({"rule": "regex_forbid", "pattern": "("})
    with pytest.raises(ValueError, match="too long"):
        rules.validate_rule_config({"rule": "regex_forbid", "pattern": "a" * 400})


def test_catastrophic_regex_times_out_instead_of_hanging():
    cfg = rules.validate_rule_config({"rule": "regex_forbid", "pattern": r"(a|aa)+$"})
    with pytest.raises(TimeoutError):
        rules.run_rule(cfg, R("a" * 45 + "!"))
    res = evaluation.run_rule_param({"key": "k", "name": "n", "weight": 1, "required": False, "config": cfg},
                                    [{"idx": 1, "role": "assistant", "content": "a" * 45 + "!"}])
    assert res.status == "error"  # reported, never hangs or crashes the run


def test_latency_rule_stats():
    avg = rules.validate_rule_config({"rule": "max_latency_ms", "max_ms": 1000, "stat": "avg"})
    assert rules.run_rule(avg, R("a", "b", lat=[500, 1000])).passed
    p95 = rules.validate_rule_config({"rule": "max_latency_ms", "max_ms": 1000, "stat": "p95"})
    assert not rules.run_rule(p95, R("a", "b", lat=[500, 3000])).passed
    assert not rules.run_rule(p95, R("a")).passed  # no latency data is not a pass


def test_rule_config_validation_errors():
    for bad in [{"rule": "nope"}, {"rule": "max_words_per_reply"}, {"rule": "max_words_per_reply", "max": -1},
                {"rule": "contains_any", "phrases": []}, {"rule": "min_question_ratio", "min_ratio": 2},
                {"rule": "max_latency_ms", "max_ms": 500, "stat": "median"}]:
        with pytest.raises(ValueError):
            rules.validate_rule_config(bad)


def test_no_replies_fails_rule():
    cfg = rules.validate_rule_config({"rule": "no_formatting"})
    assert not rules.run_rule(cfg, []).passed


# --- judge parsing ---
@pytest.mark.parametrize("text", [
    '{"score": 4, "reasoning": "ok", "evidence": []}',
    '```json\n{"score": 4, "reasoning": "ok", "evidence": []}\n```',
    'Sure! Here you go: {"score": 4, "reasoning": "has } brace", "evidence": []} hope that helps',
])
def test_parse_judge_json_variants(text):
    assert parse_judge_json(text)["score"] == 4


def test_parse_judge_json_rejects_garbage():
    with pytest.raises(ValueError):
        parse_judge_json("I would give it a four out of five.")


# --- verdict ---
def P(status, score=None, weight=1.0, required=False, name="p"):
    return ParamResult(key=name, name=name, kind="rule", weight=weight, required=required, status=status, score=score)


def test_verdict_weighted_pass_and_fail():
    v, s, _ = compute_verdict([P("pass", 1.0, 1), P("fail", 0.0, 1)], 50)
    assert (v, s) == ("pass", 50.0)
    v, s, why = compute_verdict([P("pass", 1.0, 1), P("fail", 0.0, 1)], 51)
    assert v == "fail" and "below" in why
    v, s, _ = compute_verdict([P("pass", 1.0, 3), P("fail", 0.0, 1)], 75)
    assert (v, s) == ("pass", 75.0)


def test_required_failure_overrides_high_score():
    v, s, why = compute_verdict([P("pass", 1.0, 10), P("fail", 0.0, 0.1, required=True, name="Safety")], 10)
    assert v == "fail" and "Safety" in why and s > 90


def test_error_is_inconclusive_not_pass():
    v, _, why = compute_verdict([P("pass", 1.0), P("error", name="Judge")], 10)
    assert v == "error" and "Judge" in why
    # ...but a known required failure is still a fail
    assert compute_verdict([P("error"), P("fail", 0.0, required=True)], 10)[0] == "fail"


def test_skipped_ignored_and_all_skipped_is_error():
    assert compute_verdict([P("pass", 1.0), P("skipped")], 90)[0] == "pass"
    assert compute_verdict([P("skipped")], 90)[0] == "error"


def test_mood_applicability():
    p = {"applies_to_moods": ["crisis"]}
    assert evaluation.applies(p, "crisis") and not evaluation.applies(p, "angry")
    assert evaluation.applies({"applies_to_moods": []}, "anything")


# --- judge call (with fake llm) ---
JUDGE_PARAM = {"key": "emp", "name": "Empathy", "weight": 1.0, "required": False,
               "config": {"criteria": "Reflects feelings accurately.", "scale_max": 5, "min_score": 4, "guidance": ""}}
TURNS = [{"idx": 1, "role": "user", "content": "I feel awful."}, {"idx": 2, "role": "assistant", "content": "That sounds really painful, I'm here."}]


async def test_judge_scores_and_flags_unverified_evidence(fake):
    from lab.config import load_settings
    fake.judge_raw = lambda m: json.dumps({"score": 5, "reasoning": "great", "evidence": ["That sounds really painful", "invented quote"]})
    res = await evaluation.run_judge(JUDGE_PARAM, {"mood": "sad", "rendered_prompt": "p"}, TURNS, load_settings())
    assert res.status == "pass" and res.score == 1.0 and res.raw_score == 5
    assert [e["verified"] for e in res.evidence] == [True, False]


async def test_judge_retries_once_on_bad_output_then_errors(fake):
    from lab.config import load_settings
    calls = []
    fake.judge_raw = lambda m: (calls.append(1), "no json here")[1]
    res = await evaluation.run_judge(JUDGE_PARAM, {"mood": "sad"}, TURNS, load_settings())
    assert res.status == "error" and len(calls) == 2


async def test_judge_rejects_out_of_range_score(fake):
    from lab.config import load_settings
    fake.judge_raw = lambda m: json.dumps({"score": 9, "reasoning": "x", "evidence": []})
    res = await evaluation.run_judge(JUDGE_PARAM, {"mood": "sad"}, TURNS, load_settings())
    assert res.status == "error"


async def test_judge_below_threshold_fails(fake):
    from lab.config import load_settings
    fake.judge_raw = lambda m: json.dumps({"score": 3, "reasoning": "meh", "evidence": []})
    res = await evaluation.run_judge(JUDGE_PARAM, {"mood": "sad"}, TURNS, load_settings())
    assert res.status == "fail" and res.score == 0.5
