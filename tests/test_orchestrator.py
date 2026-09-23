from typing import Any

import pytest

from agile_po_agent.config import Settings
from agile_po_agent.models import (
    AcceptanceCriterion,
    ActionDecision,
    DeliveryEvidence,
    JevDecision,
    JevEvaluation,
    JevUsage,
    JiraTaskDraft,
    ProductBrief,
    Worker,
)
from agile_po_agent.orchestrator import (
    OrchestrationContext,
    ProductOwnerOrchestrator,
)


def brief() -> ProductBrief:
    return ProductBrief(
        title="Draft a bounded product task",
        problem="The current product brief needs a safe, reviewable implementation path.",
        target_user="product owner",
        desired_outcome="Produce one evidence-gated task draft.",
        business_value="Reduce avoidable refinement and delivery rework.",
        repository="example/repository",
    )


def ready_draft() -> JiraTaskDraft:
    return JiraTaskDraft(
        summary="Generate a Jira-ready product task",
        context="Product briefs need consistent refinement before engineering can start delivery.",
        desired_outcome="Create one validated and reviewable implementation task.",
        business_value="Reduce refinement time and prevent avoidable rework.",
        scope=["Load a local brief", "Render one structured task"],
        non_goals=["Write to Jira"],
        acceptance_criteria=[
            AcceptanceCriterion(
                given="a valid brief",
                when="generation runs",
                then="a structured task is returned",
                evidence="schema validation passes",
            ),
            AcceptanceCriterion(
                given="an invalid draft",
                when="quality evaluation runs",
                then="named failures are returned",
                evidence="unit test assertion",
            ),
        ],
        test_plan=["Run unit tests"],
        success_metrics=["All quality checks pass"],
    )


def evaluation(
    worker: Worker,
    *,
    web: float = 0.1,
    repository: float = 0.1,
    brief_sufficient: float = 0.9,
    ready_to_ship: float = 0.9,
    quality: float = 2.7,
    quality_confidence: float = 0.9,
    action: ActionDecision = ActionDecision.ASK,
    action_confidence: float = 0.9,
) -> JevEvaluation:
    worker_probabilities = {item: 0.0 for item in Worker}
    worker_probabilities[worker] = 1.0
    action_probabilities = {item: 0.0 for item in ActionDecision}
    action_probabilities[action] = 1.0
    return JevEvaluation(
        model="jev-1.13.0",
        usage=JevUsage(input_tokens=100, output_tokens=20),
        latency_ms=12.0,
        decision=JevDecision(
            next_worker=worker,
            next_worker_probabilities=worker_probabilities,
            next_worker_confidence=0.9,
            needs_web_research=web,
            needs_repository_files=repository,
            brief_sufficient=brief_sufficient,
            ready_to_ship=ready_to_ship,
            quality_score=quality,
            quality_normalized=quality / 3,
            quality_legend={
                "0": "not actionable",
                "1": "major refinement required",
                "2": "minor refinement required",
                "3": "ready for implementation",
            },
            quality_probabilities={"0": 0.0, "1": 0.0, "2": 0.3, "3": 0.7},
            quality_confidence=quality_confidence,
            allow_action=action,
            allow_action_probabilities=action_probabilities,
            allow_action_confidence=action_confidence,
        ),
    )


class FakeOwner:
    def __init__(self) -> None:
        self.draft_calls = 0
        self.revise_calls = 0

    async def draft(self, _: ProductBrief) -> JiraTaskDraft:
        self.draft_calls += 1
        return ready_draft()

    async def revise(self, draft: JiraTaskDraft, _: list[str]) -> JiraTaskDraft:
        self.revise_calls += 1
        return draft


class FakeJev:
    def __init__(self, values: list[JevEvaluation]) -> None:
        self.values = list(values)
        self.states: list[dict[str, Any]] = []

    async def evaluate(self, state: dict[str, Any]) -> JevEvaluation:
        self.states.append(state)
        return self.values.pop(0)


@pytest.mark.asyncio
async def test_orchestrator_uses_jev_write_then_finish_with_bounded_trace() -> None:
    owner = FakeOwner()
    jev = FakeJev(
        [
            evaluation(Worker.WRITE, repository=0.9),
            evaluation(Worker.FINISH, repository=0.9),
        ]
    )
    orchestrator = ProductOwnerOrchestrator(Settings(), owner, jev)

    outcome = await orchestrator.create_draft(
        brief(),
        context=OrchestrationContext(repository_files_loaded=True),
    )

    assert outcome.terminal_reason == "definition_of_ready_passed"
    assert outcome.steps == 1
    assert len(outcome.decision_trace) == 2
    assert owner.draft_calls == 1
    assert owner.revise_calls == 0
    assert jev.states[0]["jira_write_authorized"] is False


@pytest.mark.asyncio
async def test_orchestrator_keeps_web_and_repository_requirements_independent() -> None:
    owner = FakeOwner()
    orchestrator = ProductOwnerOrchestrator(
        Settings(), owner, FakeJev([evaluation(Worker.WRITE, web=0.1, repository=0.9)])
    )

    outcome = await orchestrator.create_draft(brief())

    assert outcome.terminal_reason == "required_context_missing:repository_files"
    assert outcome.draft is None
    assert owner.draft_calls == 0


@pytest.mark.asyncio
async def test_orchestrator_does_not_coerce_uncertain_noul() -> None:
    owner = FakeOwner()
    orchestrator = ProductOwnerOrchestrator(
        Settings(), owner, FakeJev([evaluation(Worker.WRITE, web=0.5)])
    )

    outcome = await orchestrator.create_draft(
        brief(), context=OrchestrationContext(web_research_complete=True)
    )

    assert outcome.terminal_reason == "context_requirements_uncertain"
    assert owner.draft_calls == 0


@pytest.mark.asyncio
async def test_finish_recommendation_cannot_override_quality_gate() -> None:
    owner = FakeOwner()
    jev = FakeJev(
        [
            evaluation(Worker.WRITE),
            evaluation(Worker.FINISH, quality=1.0),
            evaluation(Worker.FINISH),
        ]
    )
    orchestrator = ProductOwnerOrchestrator(Settings(max_steps=3), owner, jev)

    outcome = await orchestrator.create_draft(brief())

    assert outcome.terminal_reason == "definition_of_ready_passed"
    assert owner.revise_calls == 1
    assert outcome.steps == 2


@pytest.mark.asyncio
async def test_orchestrator_stops_at_configured_decision_bound() -> None:
    owner = FakeOwner()
    orchestrator = ProductOwnerOrchestrator(
        Settings(max_steps=2),
        owner,
        FakeJev([evaluation(Worker.WRITE), evaluation(Worker.WRITE)]),
    )

    outcome = await orchestrator.create_draft(brief())

    assert outcome.terminal_reason == "max_steps_reached"
    assert outcome.steps == 2
    assert owner.draft_calls == 1
    assert owner.revise_calls == 1


def test_shipping_requires_human_and_delivery_evidence_even_when_jev_allows() -> None:
    owner = FakeOwner()
    orchestrator = ProductOwnerOrchestrator(
        Settings(), owner, FakeJev([])
    )
    jev_allows = evaluation(Worker.FINISH, action=ActionDecision.ALLOW)

    without_human = orchestrator.assess_shipping(
        jev_allows,
        DeliveryEvidence(
            tests_passed=True,
            lint_passed=True,
            typecheck_passed=True,
            unresolved_blockers=0,
            human_approved=False,
        ),
    )
    fully_approved = orchestrator.assess_shipping(
        jev_allows,
        DeliveryEvidence(
            tests_passed=True,
            lint_passed=True,
            typecheck_passed=True,
            unresolved_blockers=0,
            human_approved=True,
        ),
    )

    assert not without_human.passed
    assert "human_approval_missing" in without_human.failures
    assert fully_approved.passed


def test_ambiguous_jev_permission_fails_closed() -> None:
    orchestrator = ProductOwnerOrchestrator(Settings(), FakeOwner(), FakeJev([]))
    result = orchestrator.assess_shipping(
        evaluation(
            Worker.FINISH,
            action=ActionDecision.ALLOW,
            action_confidence=0.4,
        ),
        DeliveryEvidence(
            tests_passed=True,
            lint_passed=True,
            typecheck_passed=True,
            human_approved=True,
        ),
    )

    assert not result.passed
    assert "jev_action_uncertain" in result.failures
