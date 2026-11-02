"""Request schemas (response bodies are plain dicts built in service.py)."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from . import rules
from .templating import extract_variables

IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
KEY_RE = re.compile(r"^[a-z0-9_]{1,60}$")
ProviderName = Literal["groq", "sarvam", "custom"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _check_values(values: dict[str, str]) -> dict[str, str]:
    if len(values) > 50:
        raise ValueError("At most 50 variables")
    out = {}
    for key, val in values.items():
        if not IDENT_RE.match(key):
            raise ValueError(f"Variable name '{key}' must be letters, digits and underscores, not starting with a digit")
        val = "" if val is None else str(val)
        if len(val) > 4000:
            raise ValueError(f"Value for '{key}' is longer than 4000 characters")
        out[key] = val
    return out


def _slug_mood(value: str) -> str:
    value = re.sub(r"\s+", "_", value.strip().lower())
    if not re.match(r"^[a-z0-9_\-]{1,40}$", value):
        raise ValueError("Mood must be 1-40 letters, digits, '-' or '_'")
    return value


# --- prompts ---------------------------------------------------------------------

class PromptCreate(Strict):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    content: str = Field(min_length=1, max_length=20000)
    variable_defaults: dict[str, str] = Field(default_factory=dict)
    note: str = Field(default="", max_length=500)

    @field_validator("variable_defaults")
    @classmethod
    def _vars(cls, v):
        return _check_values(v)

    @model_validator(mode="after")
    def _known(self):
        unknown = set(self.variable_defaults) - set(extract_variables(self.content))
        if unknown:
            raise ValueError("Defaults given for variables not used in the prompt: " + ", ".join(sorted(unknown)))
        return self


class PromptVersionCreate(Strict):
    content: str = Field(min_length=1, max_length=20000)
    variable_defaults: dict[str, str] = Field(default_factory=dict)
    note: str = Field(default="", max_length=500)

    @field_validator("variable_defaults")
    @classmethod
    def _vars(cls, v):
        return _check_values(v)

    @model_validator(mode="after")
    def _known(self):
        unknown = set(self.variable_defaults) - set(extract_variables(self.content))
        if unknown:
            raise ValueError("Defaults given for variables not used in the prompt: " + ", ".join(sorted(unknown)))
        return self


class PromptUpdate(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class RenderPreview(Strict):
    content: str = Field(max_length=20000)
    variables: dict[str, str] = Field(default_factory=dict)

    @field_validator("variables")
    @classmethod
    def _vars(cls, v):
        return _check_values(v)


# --- scenarios -------------------------------------------------------------------

class ScenarioIn(Strict):
    name: str = Field(min_length=1, max_length=120)
    mood: str
    persona: str = Field(min_length=1, max_length=4000)
    behavior: str = Field(default="", max_length=4000)
    opening_message: str = Field(min_length=1, max_length=2000)
    intensity: int = Field(default=3, ge=1, le=5)
    max_turns: int = Field(default=6, ge=1, le=20)
    scripted_turns: list[str] = Field(default_factory=list, max_length=19)
    variables: dict[str, str] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("mood")
    @classmethod
    def _mood(cls, v):
        return _slug_mood(v)

    @field_validator("variables")
    @classmethod
    def _vars(cls, v):
        return _check_values(v)

    @field_validator("scripted_turns")
    @classmethod
    def _script(cls, v):
        cleaned = [s.strip() for s in v]
        if any(not s or len(s) > 2000 for s in cleaned):
            raise ValueError("Scripted turns must be non-empty and under 2000 characters")
        return cleaned

    @field_validator("tags")
    @classmethod
    def _tags(cls, v):
        cleaned = [t.strip().lower() for t in v if t.strip()]
        if any(len(t) > 40 for t in cleaned):
            raise ValueError("Tags must be under 40 characters")
        return list(dict.fromkeys(cleaned))


# --- evaluation ------------------------------------------------------------------

class EvalParamIn(Strict):
    key: str
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    kind: Literal["llm_judge", "rule"]
    config: dict
    weight: float = Field(default=1.0, gt=0, le=100)
    required: bool = False
    applies_to_moods: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("key")
    @classmethod
    def _key(cls, v):
        if not KEY_RE.match(v):
            raise ValueError("Key must be 1-60 chars of a-z, 0-9 and underscore")
        return v

    @field_validator("applies_to_moods")
    @classmethod
    def _moods(cls, v):
        return [_slug_mood(m) for m in v]

    @model_validator(mode="after")
    def _config(self):
        if self.kind == "rule":
            self.config = rules.validate_rule_config(self.config)
        else:
            criteria = str(self.config.get("criteria", "")).strip()
            if len(criteria) < 10 or len(criteria) > 4000:
                raise ValueError("A judge parameter needs 'criteria' of 10-4000 characters")
            try:
                scale = int(self.config.get("scale_max", 5))
                min_score = float(self.config.get("min_score", 4))
            except (TypeError, ValueError):
                raise ValueError("'scale_max' and 'min_score' must be numbers") from None
            if not 3 <= scale <= 10:
                raise ValueError("'scale_max' must be between 3 and 10")
            if not 1 <= min_score <= scale:
                raise ValueError(f"'min_score' must be between 1 and {scale}")
            guidance = str(self.config.get("guidance", "")).strip()
            if len(guidance) > 4000:
                raise ValueError("'guidance' is limited to 4000 characters")
            self.config = {"criteria": criteria, "scale_max": scale, "min_score": min_score, "guidance": guidance}
        return self


class EvalSetIn(Strict):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    pass_threshold: float = Field(default=75.0, ge=0, le=100)
    params: list[EvalParamIn] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def _unique(self):
        keys = [p.key for p in self.params]
        dupes = {k for k in keys if keys.count(k) > 1}
        if dupes:
            raise ValueError("Duplicate parameter keys: " + ", ".join(sorted(dupes)))
        return self


# --- runs & conversations --------------------------------------------------------

class GenOptions(Strict):
    temperature: float | None = Field(default=None, ge=0, le=2)   # None = use the saved setting
    max_tokens: int | None = Field(default=None, ge=50, le=2000)  # None = use the saved setting
    provider: ProviderName | None = None
    model: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def _model_needs_provider(self):
        if self.model and not self.provider:
            raise ValueError("Choose a provider to use a specific model")
        return self


class RunCreate(GenOptions):
    name: str = Field(default="", max_length=160)
    prompt_version_id: str
    eval_set_id: str
    scenario_ids: list[str] = Field(min_length=1, max_length=60)
    repeats: int = Field(default=1, ge=1, le=10)
    variables: dict[str, str] = Field(default_factory=dict)
    max_turns: int | None = Field(default=None, ge=1, le=20)

    @field_validator("variables")
    @classmethod
    def _vars(cls, v):
        return _check_values(v)


class LiveCreate(GenOptions):
    prompt_version_id: str
    variables: dict[str, str] = Field(default_factory=dict)
    scenario_id: str | None = None
    mood: str | None = None
    title: str = Field(default="", max_length=200)

    @field_validator("variables")
    @classmethod
    def _vars(cls, v):
        return _check_values(v)

    @field_validator("mood")
    @classmethod
    def _mood(cls, v):
        return _slug_mood(v) if v else v


class LiveTurn(Strict):
    content: str = Field(min_length=1, max_length=4000)


class LiveFinish(Strict):
    eval_set_id: str


class ImportedTurn(Strict):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12000)
    latency_ms: int | None = Field(default=None, ge=0, le=600000)


class ImportConversation(Strict):
    title: str = Field(default="Imported conversation", max_length=200)
    mood: str = ""
    eval_set_id: str
    system_prompt: str = Field(default="", max_length=20000)
    turns: list[ImportedTurn] = Field(min_length=2, max_length=80)

    @field_validator("mood")
    @classmethod
    def _mood(cls, v):
        return _slug_mood(v) if v else v

    @model_validator(mode="after")
    def _shape(self):
        if self.turns[0].role != "user":
            raise ValueError("The first turn must be from the user")
        if not any(t.role == "assistant" for t in self.turns):
            raise ValueError("The transcript needs at least one assistant turn")
        return self


class ReevaluateRequest(Strict):
    eval_set_id: str | None = None
