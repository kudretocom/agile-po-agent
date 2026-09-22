"""Bounded orchestration for drafting and refinement."""

from pydantic import BaseModel

from agile_po_agent.autogen_agent import AutoGenProductOwner
from agile_po_agent.config import Settings
from agile_po_agent.models import DefinitionOfReadyResult, JiraTaskDraft, ProductBrief
from agile_po_agent.quality import DefinitionOfReadyEvaluator


class DraftOutcome(BaseModel):
    draft: JiraTaskDraft
    readiness: DefinitionOfReadyResult
    steps: int
    terminal_reason: str


class ProductOwnerOrchestrator:
    """Application code owns iteration and termination, never the model."""

    def __init__(self, settings: Settings, product_owner: AutoGenProductOwner) -> None:
        self.settings = settings
        self.product_owner = product_owner
        self.readiness = DefinitionOfReadyEvaluator(settings.ready_threshold)

    async def create_draft(self, brief: ProductBrief) -> DraftOutcome:
        draft = await self.product_owner.draft(brief)
        result = self.readiness.evaluate(draft)
        steps = 1
        while not result.passed and steps < self.settings.max_steps:
            draft = await self.product_owner.revise(draft, result.failures)
            result = self.readiness.evaluate(draft)
            steps += 1
        reason = "definition_of_ready_passed" if result.passed else "max_steps_reached"
        return DraftOutcome(draft=draft, readiness=result, steps=steps, terminal_reason=reason)

