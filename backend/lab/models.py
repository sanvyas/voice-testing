"""SQLAlchemy models.

Versioning rule: prompt versions are immutable. Each conversation additionally stores a
snapshot of the rendered prompt, scenario and rubric it ran with, so history stays
reproducible after those objects are edited.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Prompt(Base):
    __tablename__ = "prompts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    versions: Mapped[list["PromptVersion"]] = relationship(
        back_populates="prompt", order_by="PromptVersion.version.desc()", cascade="all, delete-orphan"
    )


class PromptVersion(Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (UniqueConstraint("prompt_id", "version", name="uq_prompt_version"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    prompt_id: Mapped[str] = mapped_column(ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    variable_defaults: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    note: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    prompt: Mapped[Prompt] = relationship(back_populates="versions")


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    mood: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    persona: Mapped[str] = mapped_column(Text, nullable=False)  # who the simulated caller is / what happened
    behavior: Mapped[str] = mapped_column(Text, default="", nullable=False)  # how they talk and react
    opening_message: Mapped[str] = mapped_column(Text, nullable=False)
    intensity: Mapped[int] = mapped_column(Integer, default=3, nullable=False)  # 1 (mild) .. 5 (extreme)
    max_turns: Mapped[int] = mapped_column(Integer, default=6, nullable=False)  # user turns
    scripted_turns: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # fixed user lines (optional)
    variables: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class EvalSet(Base):
    __tablename__ = "eval_sets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    pass_threshold: Mapped[float] = mapped_column(Float, default=75.0, nullable=False)  # 0..100
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    params: Mapped[list["EvalParam"]] = relationship(
        back_populates="eval_set", order_by="EvalParam.position", cascade="all, delete-orphan"
    )


class EvalParam(Base):
    __tablename__ = "eval_params"
    __table_args__ = (UniqueConstraint("eval_set_id", "key", name="uq_evalparam_key"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    eval_set_id: Mapped[str] = mapped_column(ForeignKey("eval_sets.id", ondelete="CASCADE"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # llm_judge | rule
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # must pass for the run to pass
    applies_to_moods: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # empty = all moods
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    eval_set: Mapped[EvalSet] = relationship(back_populates="params")


class TestRun(Base):
    """A batch: one prompt version x one rubric x many scenarios."""

    __test__ = False  # not a pytest class
    __tablename__ = "test_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False, index=True)
    prompt_version_id: Mapped[str] = mapped_column(ForeignKey("prompt_versions.id"), nullable=False, index=True)
    eval_set_id: Mapped[str | None] = mapped_column(ForeignKey("eval_sets.id", ondelete="SET NULL"), nullable=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    conversations: Mapped[list["Conversation"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conv_status_created", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # simulated | live | imported
    # live | queued | running | evaluating | completed | error | cancelled
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    verdict: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)  # pass | fail | error
    score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0..100
    verdict_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # transcript is complete
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    mood: Mapped[str] = mapped_column(String(40), default="", nullable=False, index=True)
    prompt_version_id: Mapped[str | None] = mapped_column(ForeignKey("prompt_versions.id"), nullable=True, index=True)
    scenario_id: Mapped[str | None] = mapped_column(ForeignKey("scenarios.id", ondelete="SET NULL"), nullable=True)
    eval_set_id: Mapped[str | None] = mapped_column(ForeignKey("eval_sets.id", ondelete="SET NULL"), nullable=True)
    prompt_label: Mapped[str] = mapped_column(String(200), default="", nullable=False)  # "name v3"
    rendered_prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    variables: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    scenario_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    evalset_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    gen_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    provider: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    model: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # App traffic (mobile/web clients using /api/v1): who sent it and against which release.
    client: Mapped[str] = mapped_column(String(40), default="", server_default="", nullable=False)  # e.g. ios, android, web
    user_ref: Mapped[str] = mapped_column(String(100), default="", server_default="", nullable=False)  # the app's own user id (opaque)
    environment: Mapped[str] = mapped_column(String(20), default="", server_default="", nullable=False, index=True)  # staging | production
    api_key_id: Mapped[str | None] = mapped_column(ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True, index=True)
    deployment_id: Mapped[str | None] = mapped_column(ForeignKey("deployments.id", ondelete="SET NULL"), nullable=True)
    avg_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    run: Mapped[TestRun | None] = relationship(back_populates="conversations")
    turns: Mapped[list["Turn"]] = relationship(
        back_populates="conversation", order_by="Turn.idx", cascade="all, delete-orphan"
    )
    results: Mapped[list["EvalResult"]] = relationship(
        back_populates="conversation", order_by="EvalResult.position", cascade="all, delete-orphan"
    )
    notes: Mapped[list["Note"]] = relationship(
        back_populates="conversation", order_by="Note.created_at", cascade="all, delete-orphan"
    )


class Turn(Base):
    __tablename__ = "turns"
    __table_args__ = (UniqueConstraint("conversation_id", "idx", name="uq_turn_idx"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(12), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)  # assistant turns: time to reply
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    conversation: Mapped[Conversation] = relationship(back_populates="turns")


class Note(Base):
    """A human observation on a call, written while it happens or afterwards. ``after_turn`` is how many messages existed when it was written."""
    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    after_turn: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    conversation: Mapped[Conversation] = relationship(back_populates="notes")


class EvalResult(Base):
    __tablename__ = "eval_results"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    param_key: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)  # pass | fail | skipped | error
    score: Mapped[float | None] = mapped_column(Float, nullable=True)  # normalised 0..1
    raw_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold: Mapped[str] = mapped_column(String(80), default="", nullable=False)  # human text, e.g. ">= 4 / 5"
    reasoning: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evidence: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    conversation: Mapped[Conversation] = relationship(back_populates="results")


class Setting(Base):
    """Key/value settings. Secrets are stored encrypted (see lab/secrets.py), never in plaintext."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class ApiKey(Base):
    """Credentials for client apps (mobile/web) calling /api/v1. Only a hash is stored."""

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False)  # which release this key talks to
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)  # first chars, for recognising a key in the UI
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Deployment(Base):
    """A release: which prompt version, variables and model settings an environment serves.
    The newest active row per environment is live; promoting again (or an older version = rollback) supersedes it."""

    __tablename__ = "deployments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    environment: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # staging | production
    prompt_version_id: Mapped[str] = mapped_column(ForeignKey("prompt_versions.id"), nullable=False)
    variables: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    gen: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # temperature, max_tokens, provider, model
    note: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # test results at promotion time
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    prompt_version: Mapped[PromptVersion] = relationship()


# --- AI call assistant (product) -------------------------------------------------------

class Business(Base):
    """One customer of the platform. Everything below (contacts, calls, board, settings) belongs to exactly one business."""
    __tablename__ = "businesses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # paused businesses are not answered by the AI
    phone_number: Mapped[str] = mapped_column(String(20), default="", nullable=False, index=True)  # the Plivo number that forwards to this business (E.164)
    key_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)  # sha256 of the owner's private link key
    key_enc: Mapped[str | None] = mapped_column(Text, nullable=True)  # the same key, encrypted, so the admin can show the link again
    settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # profile, knowledge window, budget, prompt overrides
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Contact(Base):
    """Someone the owner knows. ``always_ring`` contacts are never answered by the assistant."""
    __tablename__ = "contacts"
    __table_args__ = (UniqueConstraint("business_id", "phone", name="uq_contact_business_phone"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)  # E.164, e.g. +919876543210
    always_ring: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    note: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Call(Base):
    __tablename__ = "calls"
    __table_args__ = (Index("ix_calls_started", "started_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(12), nullable=False)  # test (in the browser) | phone
    handled_by: Mapped[str] = mapped_column(String(12), default="assistant", nullable=False)  # assistant | owner (always-ring contact)
    status: Mapped[str] = mapped_column(String(12), default="live", nullable=False, index=True)  # live | done
    caller_number: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    caller_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True)
    provider_call_id: Mapped[str | None] = mapped_column(String(80), nullable=True, unique=True)  # Plivo CallUUID
    importance: Mapped[str] = mapped_column(String(10), default="", nullable=False, index=True)  # action | fyi | ignore
    category: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    action_items: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # [{id, text, done}]
    callback_number: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    language: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    summary_error: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # the owner has dealt with it
    duration_s: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # usage counters for the cost estimate, silent-turn counter
    cost: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # estimated cost in rupees, by part
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    turns: Mapped[list["CallTurn"]] = relationship(back_populates="call", order_by="CallTurn.idx", cascade="all, delete-orphan")
    notes: Mapped[list["CallNote"]] = relationship(back_populates="call", order_by="CallNote.created_at", cascade="all, delete-orphan")


class CallTurn(Base):
    __tablename__ = "call_turns"
    __table_args__ = (UniqueConstraint("call_id", "idx", name="uq_call_turn_idx"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, index=True)
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(12), nullable=False)  # caller | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    call: Mapped[Call] = relationship(back_populates="turns")


class CallNote(Base):
    """The owner's own observation on a call, written live or later."""
    __tablename__ = "call_notes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    after_turn: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    call: Mapped[Call] = relationship(back_populates="notes")


class BoardItem(Base):
    """One line of "Today's board": what the owner is willing to have the assistant say about price and stock."""
    __tablename__ = "board_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    price: Mapped[str] = mapped_column(String(40), default="", nullable=False)  # as the owner writes it, e.g. "Rs 450"
    status: Mapped[str] = mapped_column(String(12), default="in_stock", nullable=False)  # in_stock | sold_out | ask
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # when the owner last said "this is still true"


class WaMessage(Base):
    """A WhatsApp message in the thread with one person: sent by Munshi (AI) or by the owner. Only messages that really went out are kept."""
    __tablename__ = "wa_messages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # the other person, E.164
    call_id: Mapped[str | None] = mapped_column(ForeignKey("calls.id", ondelete="SET NULL"), nullable=True)
    sender: Mapped[str] = mapped_column(String(10), nullable=False)  # ai | owner | customer
    text: Mapped[str] = mapped_column(Text, nullable=False)
    provider_id: Mapped[str] = mapped_column(String(120), default="", nullable=False)  # Meta message id
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)


class AuditEntry(Base):
    """What changed in the portal or app configuration, and when. A plain trail, not security logging."""
    __tablename__ = "audit_entries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    business_id: Mapped[str | None] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), nullable=True, index=True)  # empty for platform-wide changes
    area: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # business | board | prompts | integrations | budget | system
    summary: Mapped[str] = mapped_column(String(300), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
