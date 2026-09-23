"""Bounded orchestration for drafting, Jev decisions, and deterministic gates."""

from typing import Any, Protocol

from pydantic import BaseModel

from agile_po_agent.config import Settings
from agile_po_agent.models import (
    ActionDecision,
    DefinitionOfReadyResult,
    DeliveryEvidence,
    JevDecisionTrace,
    JevEvaluation,
    JiraTaskDraft,
    NoulInterpretation,
    ProductBrief,
    ShippingDecision,
    Worker,
)
from agile_po_agent.quality import DefinitionOfReadyEvaluator, ShippingGate


class ProductOwner(Protocol):
    async def draft(self, brief: ProductBrief) -> JiraTaskDraft: ...

    async def revise(self, draft: JiraTaskDraft, failures: list[str]) -> JiraTaskDraft: ...


class JevEvaluator(Protocol):
    async def evaluate(self, state: dict[str, Any]) -> JevEvaluation: ...


class OrchestrationContext(BaseModel):
    """Evidence acquisition completed outside Jev and supplied explicitly by code."""

    web_research_complete: bool = False
    repository_files_loaded: bool = False


class DraftOutcome(BaseModel):
    draft: JiraTaskDraft | None
    readiness: DefinitionOfReadyResult | None
    steps: int
    terminal_reason: str
    decision_trace: list[JevDecisionTrace]


class ProductOwnerOrchestrator:
    """Application code owns bounded transitions, gates, and termination."""

    def __init__(
        self,
        settings: Settings,
        product_owner: ProductOwner,
        jev: JevEvaluator,
    ) -> None:
        self.settings = settings
        self.product_owner = product_owner
        self.jev = jev
        self.readiness = DefinitionOfReadyEvaluator(settings.ready_threshold)
        self.shipping = ShippingGate(settings.ready_threshold, settings.quality_threshold)

    async def create_draft(
        self,
        brief: ProductBrief,
        *,
        context: OrchestrationContext | None = None,
    ) -> DraftOutcome:
        supplied_context = context or OrchestrationContext()
        draft: JiraTaskDraft | None = None
        readiness: DefinitionOfReadyResult | None = None
        traces: list[JevDecisionTrace] = []
        generation_steps = 0

        for decision_step in range(self.settings.max_steps):
            evaluation = await self.jev.evaluate(
                self._state(brief, supplied_context, draft, readiness, decision_step)
            )
            web_need = self.interpret_noul(evaluation.decision.needs_web_research)
            repository_need = self.interpret_noul(
                evaluation.decision.needs_repository_files
            )
            traces.append(
                JevDecisionTrace(
                    step=decision_step,
                    evaluation=evaluation,
                    needs_web_research=web_need,
                    needs_repository_files=repository_need,
                )
            )

            context_reason = self._context_terminal_reason(
                web_need, repository_need, supplied_context
            )
            if context_reason:
                return self._outcome(
                    draft, readiness, generation_steps, context_reason, traces
                )

            decision = evaluation.decision
            if decision.next_worker_confidence < self.settings.jev_choice_confidence_threshold:
                return self._outcome(
                    draft, readiness, generation_steps, "jev_worker_uncertain", traces
                )
            if decision.next_worker is Worker.ESCALATE:
                return self._outcome(
                    draft, readiness, generation_steps, "jev_escalated", traces
                )
            if decision.next_worker is Worker.RESEARCH:
                return self._outcome(
                    draft, readiness, generation_steps, "research_worker_required", traces
                )
            if decision.next_worker is Worker.FINISH:
                if draft is None or readiness is None:
                    return self._outcome(
                        draft, readiness, generation_steps, "invalid_finish_transition", traces
                    )
                finish_failures = self._finish_failures(evaluation, readiness)
                if not finish_failures:
                    return self._outcome(
                        draft,
                        readiness,
                        generation_steps,
                        "definition_of_ready_passed",
                        traces,
                    )
                draft = await self.product_owner.revise(draft, finish_failures)
            elif decision.next_worker is Worker.WRITE:
                if draft is None:
                    draft = await self.product_owner.draft(brief)
                else:
                    failures = readiness.failures if readiness else ["draft_state_missing"]
                    draft = await self.product_owner.revise(draft, failures)
            elif decision.next_worker is Worker.REVISE:
                if draft is None or readiness is None:
                    return self._outcome(
                        draft, readiness, generation_steps, "invalid_revise_transition", traces
                    )
                draft = await self.product_owner.revise(
                    draft, readiness.failures or ["jev_requested_revision"]
                )
            else:  # pragma: no cover - Worker is exhaustive; protects future enum additions.
                return self._outcome(
                    draft, readiness, generation_steps, "unsupported_worker", traces
                )

            generation_steps += 1
            readiness = self.readiness.evaluate(draft)

        return self._outcome(
            draft, readiness, generation_steps, "max_steps_reached", traces
        )

    def assess_shipping(
        self,
        evaluation: JevEvaluation,
        evidence: DeliveryEvidence,
    ) -> ShippingDecision:
        """Combine Jev advice with code-owned evidence and human authorization."""

        decision = evaluation.decision
        result = self.shipping.evaluate(
            ready_to_ship=decision.ready_to_ship,
            quality_normalized=decision.quality_normalized,
            evidence=evidence,
        )
        failures = list(result.failures)
        if decision.allow_action is not ActionDecision.ALLOW:
            failures.append("jev_action_not_allowed")
        if decision.allow_action_confidence < self.settings.jev_choice_confidence_threshold:
            failures.append("jev_action_uncertain")
        return ShippingDecision(passed=not failures, failures=failures)

    def interpret_noul(self, probability: float) -> NoulInterpretation:
        if probability <= self.settings.noul_no_threshold:
            return NoulInterpretation.NO
        if probability >= self.settings.noul_yes_threshold:
            return NoulInterpretation.YES
        return NoulInterpretation.UNCERTAIN

    def _finish_failures(
        self,
        evaluation: JevEvaluation,
        readiness: DefinitionOfReadyResult,
    ) -> list[str]:
        failures = list(readiness.failures)
        decision = evaluation.decision
        if self.interpret_noul(decision.brief_sufficient) is not NoulInterpretation.YES:
            failures.append("brief_sufficiency_not_confirmed")
        if decision.quality_normalized < self.settings.quality_threshold:
            failures.append("quality_below_threshold")
        if decision.quality_confidence < self.settings.jev_choice_confidence_threshold:
            failures.append("quality_uncertain")
        return failures

    @staticmethod
    def _context_terminal_reason(
        web_need: NoulInterpretation,
        repository_need: NoulInterpretation,
        context: OrchestrationContext,
    ) -> str | None:
        if (
            web_need is NoulInterpretation.UNCERTAIN
            or repository_need is NoulInterpretation.UNCERTAIN
        ):
            return "context_requirements_uncertain"
        missing: list[str] = []
        if web_need is NoulInterpretation.YES and not context.web_research_complete:
            missing.append("web_research")
        if (
            repository_need is NoulInterpretation.YES
            and not context.repository_files_loaded
        ):
            missing.append("repository_files")
        return f"required_context_missing:{','.join(missing)}" if missing else None

    @staticmethod
    def _state(
        brief: ProductBrief,
        context: OrchestrationContext,
        draft: JiraTaskDraft | None,
        readiness: DefinitionOfReadyResult | None,
        decision_step: int,
    ) -> dict[str, Any]:
        return {
            "brief": brief.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json") if draft else None,
            "deterministic_readiness": (
                readiness.model_dump(mode="json") if readiness else None
            ),
            "evidence_context": context.model_dump(mode="json"),
            "decision_step": decision_step,
            "bounded_side_effect": "draft_or_revise_only",
            "jira_write_authorized": False,
        }

    @staticmethod
    def _outcome(
        draft: JiraTaskDraft | None,
        readiness: DefinitionOfReadyResult | None,
        steps: int,
        terminal_reason: str,
        traces: list[JevDecisionTrace],
    ) -> DraftOutcome:
        return DraftOutcome(
            draft=draft,
            readiness=readiness,
            steps=steps,
            terminal_reason=terminal_reason,
            decision_trace=traces,
        )
