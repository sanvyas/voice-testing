"""Deterministic (non-LLM) evaluation rules over the assistant's replies.

Every rule returns a ``RuleOutcome``. Per-reply rules score the fraction of compliant
replies and pass when violations <= ``allow_violations``.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable

import regex  # third-party: supports match timeouts, which guards against ReDoS in user patterns

REGEX_TIMEOUT_S = 0.25
MAX_REGEX_LEN = 300
MAX_TEXT_LEN = 20000

RULE_TYPES: dict[str, str] = {
    "max_words_per_reply": "Every assistant reply has at most N words",
    "max_sentences_per_reply": "Every assistant reply has at most N sentences",
    "max_questions_per_reply": "Every assistant reply asks at most N questions",
    "min_question_ratio": "At least a fraction of replies ask a follow-up question",
    "no_formatting": "Replies contain no lists, headings, bold or emoji (spoken-friendly)",
    "contains_any": "Required phrases appear in the replies",
    "not_contains_any": "Forbidden phrases never appear in the replies",
    "regex_match": "A regular expression matches the replies",
    "regex_forbid": "A regular expression never matches the replies",
    "max_latency_ms": "Assistant response latency stays under a limit",
}


@dataclass
class RuleOutcome:
    passed: bool
    score: float  # 0..1
    reasoning: str
    threshold: str = ""
    evidence: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class Reply:
    idx: int
    text: str
    latency_ms: int | None = None


_SENT_END = re.compile(r"(?<=[.!?…])\s+(?=[\"'“‘(\[]?[A-Z0-9])|\n+")
_LIST_LINE = re.compile(r"^\s*(?:[-*•‣▪◦]\s+|\d{1,2}[.)]\s+|#{1,6}\s+)", re.M)
_EMPHASIS = re.compile(r"(\*\*[^*\n]+\*\*|__[^_\n]+__|`[^`\n]+`)")
_EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF]")


def count_words(text: str) -> int:
    return len(re.findall(r"\b[\w'’-]+\b", text))


def count_sentences(text: str) -> int:
    parts = [p for p in _SENT_END.split(text.strip()) if p and re.search(r"\w", p)]
    return len(parts)


def count_questions(text: str) -> int:
    return text.count("?")


def formatting_issues(text: str) -> list[str]:
    issues = []
    if _LIST_LINE.search(text):
        issues.append("list or heading markup")
    if _EMPHASIS.search(text):
        issues.append("bold/inline-code markup")
    if _EMOJI.search(text):
        issues.append("emoji")
    return issues


def _clip(text: str, n: int = 140) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _per_reply(
    replies: list[Reply],
    params: dict,
    check: Callable[[Reply], tuple[bool, str]],
    threshold_text: str,
    phrases: tuple[str, str],
) -> RuleOutcome:
    """``phrases`` = (what violators did, what compliant replies did), used to word the explanation."""
    allow = int(params.get("allow_violations", 0))
    bad: list[tuple[Reply, str]] = []
    for reply in replies:
        ok, why = check(reply)
        if not ok:
            bad.append((reply, why))
    total = len(replies)
    compliant = total - len(bad)
    passed = len(bad) <= allow
    if bad:
        shown = "; ".join(f"turn {r.idx}: {why}" for r, why in bad[:5])
        reasoning = f"{len(bad)} of {total} replies {phrases[0]} ({shown})."
    else:
        reasoning = f"All {total} replies {phrases[1]}."
    return RuleOutcome(
        passed=passed,
        score=compliant / total if total else 0.0,
        reasoning=reasoning,
        threshold=threshold_text + (f", {allow} violation(s) allowed" if allow else ""),
        evidence=[_clip(r.text) for r, _ in bad[:3]],
        details={"violations": [{"turn": r.idx, "why": why} for r, why in bad], "replies": total},
    )


def _scoped(replies: list[Reply], scope: str) -> list[Reply]:
    if scope == "first_reply":
        return replies[:1]
    if scope == "last_reply":
        return replies[-1:]
    return replies


def _safe_search(pattern: "regex.Pattern", text: str) -> bool:
    return pattern.search(text[:MAX_TEXT_LEN], timeout=REGEX_TIMEOUT_S) is not None


def compile_pattern(pattern: str) -> "regex.Pattern":
    if len(pattern) > MAX_REGEX_LEN:
        raise ValueError(f"Regex too long (max {MAX_REGEX_LEN} characters)")
    return regex.compile(pattern, regex.IGNORECASE | regex.MULTILINE)


def validate_rule_config(config: dict) -> dict:
    """Validate and normalise a rule config; raises ValueError with a user-facing message."""
    rule = config.get("rule")
    if rule not in RULE_TYPES:
        raise ValueError(f"Unknown rule '{rule}'. Choose one of: {', '.join(RULE_TYPES)}")
    out: dict[str, Any] = {"rule": rule}

    def num(name: str, lo: float, hi: float, default: float | None = None, integer: bool = True) -> None:
        raw = config.get(name, default)
        if raw is None:
            raise ValueError(f"'{name}' is required for rule '{rule}'")
        try:
            val = float(raw)
        except (TypeError, ValueError):
            raise ValueError(f"'{name}' must be a number") from None
        if math.isnan(val) or not lo <= val <= hi:
            raise ValueError(f"'{name}' must be between {lo:g} and {hi:g}")
        out[name] = int(val) if integer else val

    if rule in {"max_words_per_reply", "max_sentences_per_reply", "max_questions_per_reply"}:
        num("max", 0, 1000)
    if rule == "min_question_ratio":
        num("min_ratio", 0, 1, integer=False)
    if rule == "max_latency_ms":
        num("max_ms", 100, 600000)
        stat = config.get("stat", "p95")
        if stat not in {"avg", "p95", "max"}:
            raise ValueError("'stat' must be avg, p95 or max")
        out["stat"] = stat
    if rule in {"contains_any", "not_contains_any"}:
        phrases = config.get("phrases")
        if not isinstance(phrases, list) or not phrases or not all(isinstance(p, str) and p.strip() for p in phrases):
            raise ValueError("'phrases' must be a non-empty list of non-empty strings")
        if len(phrases) > 50 or any(len(p) > 200 for p in phrases):
            raise ValueError("At most 50 phrases of up to 200 characters")
        out["phrases"] = [p.strip() for p in phrases]
    if rule in {"regex_match", "regex_forbid"}:
        pattern = config.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            raise ValueError("'pattern' is required")
        try:
            compile_pattern(pattern)
        except (regex.error, ValueError) as exc:
            raise ValueError(f"Invalid regex: {exc}") from None
        out["pattern"] = pattern
    if rule in {"contains_any", "regex_match"}:
        scope = config.get("scope", "any_reply")
        if scope not in {"any_reply", "all_replies", "first_reply", "last_reply"}:
            raise ValueError("'scope' must be any_reply, all_replies, first_reply or last_reply")
        out["scope"] = scope
    if rule in {"not_contains_any", "regex_forbid"}:
        scope = config.get("scope", "all_replies")
        if scope not in {"all_replies", "first_reply", "last_reply"}:
            raise ValueError("'scope' must be all_replies, first_reply or last_reply")
        out["scope"] = scope
    if rule in {"max_words_per_reply", "max_sentences_per_reply", "max_questions_per_reply", "no_formatting"}:
        num("allow_violations", 0, 100, default=0)
    return out


def run_rule(config: dict, replies: list[Reply]) -> RuleOutcome:
    """Evaluate one rule. ``replies`` are the assistant turns in order."""
    rule = config["rule"]
    if not replies:
        return RuleOutcome(False, 0.0, "The assistant never replied.", details={"replies": 0})

    if rule == "max_words_per_reply":
        limit = int(config["max"])
        return _per_reply(
            replies, config,
            lambda r: (count_words(r.text) <= limit, f"{count_words(r.text)} words"),
            f"<= {limit} words per reply", ("exceeded the word limit", "stayed within the word limit"),
        )
    if rule == "max_sentences_per_reply":
        limit = int(config["max"])
        return _per_reply(
            replies, config,
            lambda r: (count_sentences(r.text) <= limit, f"{count_sentences(r.text)} sentences"),
            f"<= {limit} sentences per reply", ("exceeded the sentence limit", "stayed within the sentence limit"),
        )
    if rule == "max_questions_per_reply":
        limit = int(config["max"])
        return _per_reply(
            replies, config,
            lambda r: (count_questions(r.text) <= limit, f"{count_questions(r.text)} questions"),
            f"<= {limit} questions per reply", ("asked too many questions", f"asked at most {limit} question(s)"),
        )
    if rule == "no_formatting":
        return _per_reply(
            replies, config,
            lambda r: (not formatting_issues(r.text), ", ".join(formatting_issues(r.text))),
            "no markup or emoji", ("broke the spoken-format rule", "had no markup or emoji"),
        )
    if rule == "min_question_ratio":
        needed = float(config["min_ratio"])
        asking = [r for r in replies if "?" in r.text]
        ratio = len(asking) / len(replies)
        return RuleOutcome(
            passed=ratio >= needed,
            score=min(1.0, ratio / needed) if needed else 1.0,
            reasoning=f"{len(asking)} of {len(replies)} replies asked a question ({ratio:.0%}); needed {needed:.0%}.",
            threshold=f">= {needed:.0%} of replies",
            details={"ratio": ratio},
        )
    if rule in {"contains_any", "not_contains_any"}:
        phrases = [p.lower() for p in config["phrases"]]
        scoped = _scoped(replies, config["scope"])
        hits = [(r, p) for r in scoped for p in phrases if p in r.text.lower()]
        if rule == "contains_any":
            scope = config["scope"]
            if scope == "any_reply":
                ok = bool(hits)
                matched_replies = {r.idx for r, _ in hits}
                score = 1.0 if ok else 0.0
            else:
                matched_replies = {r.idx for r, _ in hits}
                ok = all(r.idx in matched_replies for r in scoped)
                score = len(matched_replies) / len(scoped)
            reasoning = (
                f"Found {', '.join(sorted({repr(p) for _, p in hits}))} in turn(s) {sorted(matched_replies)}."
                if hits else f"None of the required phrases appeared ({', '.join(map(repr, config['phrases']))})."
            )
            return RuleOutcome(ok, score, reasoning, threshold=f"{scope.replace('_', ' ')} contains one of {len(phrases)} phrase(s)",
                               evidence=[_clip(r.text) for r, _ in hits[:3]])
        bad_idx = sorted({r.idx for r, _ in hits})
        return RuleOutcome(
            passed=not hits,
            score=1 - len(bad_idx) / len(scoped),
            reasoning=(f"Forbidden phrase(s) {', '.join(sorted({repr(p) for _, p in hits}))} used in turn(s) {bad_idx}."
                       if hits else "No forbidden phrase was used."),
            threshold="none of the forbidden phrases",
            evidence=[_clip(r.text) for r, _ in hits[:3]],
        )
    if rule in {"regex_match", "regex_forbid"}:
        pattern = compile_pattern(config["pattern"])
        scoped = _scoped(replies, config["scope"])
        matched = [r for r in scoped if _safe_search(pattern, r.text)]
        if rule == "regex_match":
            if config["scope"] == "any_reply":
                ok, score = bool(matched), 1.0 if matched else 0.0
            else:
                ok, score = len(matched) == len(scoped), len(matched) / len(scoped)
            return RuleOutcome(ok, score, f"Pattern matched {len(matched)} of {len(scoped)} reply(ies).",
                               threshold=f"/{config['pattern']}/ in {config['scope'].replace('_', ' ')}",
                               evidence=[_clip(r.text) for r in matched[:2]])
        return RuleOutcome(not matched, 1 - len(matched) / len(scoped),
                           f"Forbidden pattern matched {len(matched)} reply(ies)." if matched else "Forbidden pattern never matched.",
                           threshold=f"never /{config['pattern']}/", evidence=[_clip(r.text) for r in matched[:3]])
    if rule == "max_latency_ms":
        values = sorted(r.latency_ms for r in replies if r.latency_ms is not None)
        if not values:
            return RuleOutcome(False, 0.0, "No latency was recorded for this conversation (imported transcripts have none).")
        stat = config["stat"]
        observed = {"avg": sum(values) / len(values), "max": values[-1], "p95": values[min(len(values) - 1, math.ceil(0.95 * len(values)) - 1)]}[stat]
        limit = int(config["max_ms"])
        return RuleOutcome(
            passed=observed <= limit,
            score=1.0 if observed <= limit else max(0.0, limit / observed),
            reasoning=f"{stat} reply latency was {observed:.0f} ms (limit {limit} ms).",
            threshold=f"{stat} <= {limit} ms",
            details={"observed_ms": observed, "samples": len(values)},
        )
    raise ValueError(f"Unhandled rule {rule}")
