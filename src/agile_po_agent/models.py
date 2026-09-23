"""Validated domain models shared across generation, evaluation, and publishing."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Worker(str, Enum):
    RESEARCH = "research"
    WRITE = "write"
    REVISE = "revise"
    FINISH = "finish"
    ESCALATE = "escalate"


class ActionDecision(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class NoulInterpretation(str, Enum):
    NO = "no"
    UNCERTAIN = "uncertain"
    YES = "yes"


class ProductBrief(BaseModel):
    title: str = Field(min_length=5, max_length=160)
    problem: str = Field(min_length=20)
    target_user: str = Field(min_length=3)
    desired_outcome: str = Field(min_length=10)
    business_value: str = Field(min_length=10)
    constraints: list[str] = Field(default_factory=list)
    known_context: list[str] = Field(default_factory=list)
    non_goals: list[str] = Field(default_factory=list)
    source_links: list[str] = Field(default_factory=list)
    repository: str | None = None


class AcceptanceCriterion(BaseModel):
    given: str = Field(min_length=3)
    when: str = Field(min_length=3)
    then: str = Field(min_length=3)
    evidence: str = Field(min_length=3)

    def to_markdown(self) -> str:
        return (
            f"- [ ] **Given** {self.given}, **when** {self.when}, "
            f"**then** {self.then}. Evidence: {self.evidence}."
        )


class JiraTaskDraft(BaseModel):
    summary: str = Field(min_length=8, max_length=120)
    issue_type: Literal["Story", "Task", "Bug"] = "Story"
    context: str = Field(min_length=30)
    user_story: str | None = None
    desired_outcome: str = Field(min_length=15)
    business_value: str = Field(min_length=15)
    scope: list[str] = Field(min_length=1)
    non_goals: list[str] = Field(min_length=1)
    acceptance_criteria: list[AcceptanceCriterion] = Field(min_length=2)
    test_plan: list[str] = Field(min_length=1)
    dependencies: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    rollout: list[str] = Field(default_factory=list)
    success_metrics: list[str] = Field(min_length=1)
    open_questions: list[str] = Field(default_factory=list)
    repository: str | None = None
    labels: list[str] = Field(default_factory=lambda: ["ai-drafted", "needs-review"])

    @field_validator("scope", "non_goals", "test_plan", "success_metrics")
    @classmethod
    def reject_blank_items(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("list items must not be blank")
        return value

    def to_markdown(self) -> str:
        sections = [
            "## Context",
            self.context,
            "## Desired outcome",
            self.desired_outcome,
            "## Business value",
            self.business_value,
            "## Scope",
            *[f"- {item}" for item in self.scope],
            "## Non-goals",
            *[f"- {item}" for item in self.non_goals],
            "## Acceptance criteria",
            *[criterion.to_markdown() for criterion in self.acceptance_criteria],
            "## Test plan",
            *[f"- [ ] {item}" for item in self.test_plan],
            "## Dependencies",
            *([f"- {item}" for item in self.dependencies] or ["- None identified"]),
            "## Risks",
            *([f"- {item}" for item in self.risks] or ["- None identified"]),
            "## Rollout",
            *([f"- {item}" for item in self.rollout] or ["- Standard reviewed release"]),
            "## Success metrics",
            *[f"- {item}" for item in self.success_metrics],
            "## Open questions",
            *([f"- {item}" for item in self.open_questions] or ["- None"]),
        ]
        if self.user_story:
            sections[2:2] = ["## User story", self.user_story]
        return "\n\n".join(sections).strip() + "\n"


class DefinitionOfReadyResult(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    passed: bool
    checks: dict[str, bool]
    failures: list[str]


class DeliveryEvidence(BaseModel):
    tests_passed: bool = False
    lint_passed: bool = False
    typecheck_passed: bool = False
    unresolved_blockers: int = Field(default=0, ge=0)
    human_approved: bool = False


class ShippingDecision(BaseModel):
    passed: bool
    failures: list[str]


class JevDecision(BaseModel):
    next_worker: Worker
    next_worker_probabilities: dict[Worker, float]
    next_worker_confidence: float = Field(ge=0.0, le=1.0)
    needs_web_research: float = Field(ge=0.0, le=1.0)
    needs_repository_files: float = Field(ge=0.0, le=1.0)
    brief_sufficient: float = Field(ge=0.0, le=1.0)
    ready_to_ship: float = Field(ge=0.0, le=1.0)
    quality_score: float
    quality_normalized: float = Field(ge=0.0, le=1.0)
    quality_legend: dict[str, str]
    quality_probabilities: dict[str, float]
    quality_confidence: float = Field(ge=0.0, le=1.0)
    allow_action: ActionDecision
    allow_action_probabilities: dict[ActionDecision, float]
    allow_action_confidence: float = Field(ge=0.0, le=1.0)


class JevUsage(BaseModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class JevEvaluation(BaseModel):
    model: str = Field(min_length=1)
    decision: JevDecision
    usage: JevUsage
    latency_ms: float = Field(ge=0.0)


class JevDecisionTrace(BaseModel):
    step: int = Field(ge=0)
    evaluation: JevEvaluation
    needs_web_research: NoulInterpretation
    needs_repository_files: NoulInterpretation
