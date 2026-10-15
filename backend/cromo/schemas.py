"""Pydantic schemas for every structured model output (validated before use)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Verdict = Literal["FOSSIL", "FENCE", "ACTIVE", "UNKNOWN"]
Stance = Literal["reason", "status", "counter", "context"]
Purpose = Literal["origin", "status", "counter"]


class _Base(BaseModel):
    model_config = {"extra": "ignore"}


def _clip(v: str, n: int) -> str:
    return (v or "")[:n]


# --- ingestion ----------------------------------------------------------------
class MetadataOut(_Base):
    doc_type: str = "other"
    date: str | None = None
    title: str | None = None
    language: str = "en"
    reference_numbers: list[str] = Field(default_factory=list)
    referenced_documents: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)
    regulations: list[str] = Field(default_factory=list)
    people: list[str] = Field(default_factory=list)
    summary: str = ""
    suspicious_instructions: bool = False

    @field_validator("summary")
    @classmethod
    def _s(cls, v):
        return _clip(v, 400)


# --- investigation --------------------------------------------------------------
class ReadEvidence(_Base):
    passage_id: str
    relevant: bool = True
    stance: Stance = "context"
    claim: str = ""
    quote: str = ""
    entities: list[str] = Field(default_factory=list)

    @field_validator("claim")
    @classmethod
    def _c(cls, v):
        return _clip(v, 300)

    @field_validator("quote")
    @classmethod
    def _q(cls, v):
        return _clip(v, 400)


class FollowQuery(_Base):
    query: str
    purpose: Purpose = "status"


class FollowUp(_Base):
    open_refs: list[str] = Field(default_factory=list)
    queries: list[FollowQuery] = Field(default_factory=list)


class ReadOut(_Base):
    evidence: list[ReadEvidence] = Field(default_factory=list)
    follow_up: FollowUp = Field(default_factory=FollowUp)
    suspicious_passages: list[str] = Field(default_factory=list)


class ChainClaim(_Base):
    claim: str
    evidence: list[str] = Field(default_factory=list)


class Dependency(_Base):
    name: str
    type: str = "other"
    holds: bool | None = None
    evidence: list[str] = Field(default_factory=list)
    note: str = ""


class Counter(_Base):
    claim: str
    evidence: list[str] = Field(default_factory=list)
    resolved: bool = False
    resolution: str = ""


class ConcludeOut(_Base):
    verdict: Verdict
    reason: str = ""
    origin_year: int | None = None
    origin_evidence: list[str] = Field(default_factory=list)
    chain: list[ChainClaim] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)
    counter_evidence: list[Counter] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


# --- change check / tripwires ---------------------------------------------------
ChangeAction = Literal["remove", "shorten", "reduce", "increase", "modify", "substitute_material",
                       "switch_supplier", "replace_equipment", "other"]


class ChangeParseOut(_Base):
    targets: list[str] = Field(default_factory=list)
    action: ChangeAction = "other"
    subject: str = ""
    from_value: str = ""
    to_value: str = ""
    summary: str = ""


Effect = Literal["fence_dependency_removed", "fence_still_required", "fossil_reactivated", "becomes_fossil",
                 "review_required", "no_effect"]


class TripwireEffect(_Base):
    step_id: str
    effect: Effect
    explanation: str = ""
    evidence: list[str] = Field(default_factory=list)


class TripwireOut(_Base):
    effects: list[TripwireEffect] = Field(default_factory=list)


# --- trials ---------------------------------------------------------------------
class TrialPlanOut(_Base):
    title: str
    objective: str
    scope: str
    duration: str
    measurements: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    rollback: str = ""
    risks: list[str] = Field(default_factory=list)
    approvals: list[str] = Field(default_factory=list)


# --- ask ------------------------------------------------------------------------
class AskClaim(_Base):
    text: str
    evidence: list[str] = Field(default_factory=list)


class AskOut(_Base):
    answer: str
    claims: list[AskClaim] = Field(default_factory=list)
    related_steps: list[str] = Field(default_factory=list)
    insufficient_evidence: bool = False


class VeteranQuestionsOut(_Base):
    questions: list[str] = Field(default_factory=list)
    who_to_ask: list[str] = Field(default_factory=list)


class StepMatchOut(_Base):
    step_id: str | None = None
    is_question_about_step: bool = False
