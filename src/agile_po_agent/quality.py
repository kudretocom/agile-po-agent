"""Deterministic product and delivery gates."""

from agile_po_agent.models import (
    DefinitionOfReadyResult,
    DeliveryEvidence,
    JiraTaskDraft,
    ShippingDecision,
)


class DefinitionOfReadyEvaluator:
    """Score properties that should not depend on another model opinion."""

    def __init__(self, threshold: float = 0.8) -> None:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")
        self.threshold = threshold

    def evaluate(self, draft: JiraTaskDraft) -> DefinitionOfReadyResult:
        checks = {
            "actionable_summary": len(draft.summary.split()) >= 3,
            "context_present": len(draft.context) >= 30,
            "outcome_present": len(draft.desired_outcome) >= 15,
            "scope_present": bool(draft.scope),
            "non_goals_present": bool(draft.non_goals),
            "acceptance_criteria_testable": all(
                criterion.evidence.strip() and criterion.then.strip()
                for criterion in draft.acceptance_criteria
            ),
            "multiple_acceptance_criteria": len(draft.acceptance_criteria) >= 2,
            "test_plan_present": bool(draft.test_plan),
            "success_metrics_present": bool(draft.success_metrics),
        }
        failures = [name for name, passed in checks.items() if not passed]
        score = sum(checks.values()) / len(checks)
        return DefinitionOfReadyResult(
            score=score,
            passed=score >= self.threshold and not failures,
            checks=checks,
            failures=failures,
        )


class ShippingGate:
    """Combine model judgement with non-negotiable delivery evidence."""

    def __init__(self, ready_threshold: float = 0.8, quality_threshold: float = 0.7) -> None:
        self.ready_threshold = ready_threshold
        self.quality_threshold = quality_threshold

    def evaluate(
        self,
        *,
        ready_to_ship: float,
        quality_normalized: float,
        evidence: DeliveryEvidence,
        side_effect_requested: bool = False,
        human_authorized: bool = False,
    ) -> ShippingDecision:
        failures: list[str] = []
        if ready_to_ship < self.ready_threshold:
            failures.append("ready_to_ship_below_threshold")
        if quality_normalized < self.quality_threshold:
            failures.append("quality_below_threshold")
        if not evidence.tests_passed:
            failures.append("tests_failed_or_missing")
        if not evidence.lint_passed:
            failures.append("lint_failed_or_missing")
        if not evidence.typecheck_passed:
            failures.append("typecheck_failed_or_missing")
        if evidence.unresolved_blockers:
            failures.append("unresolved_blockers")
        if side_effect_requested and not human_authorized:
            failures.append("human_authorization_missing")
        return ShippingDecision(passed=not failures, failures=failures)


def normalize_score(raw_score: float, number_of_levels: int) -> float:
    """Normalize a zero-based ordered rubric without hiding invalid API output."""

    if number_of_levels < 2:
        raise ValueError("a score rubric needs at least two levels")
    maximum = float(number_of_levels - 1)
    if not 0.0 <= raw_score <= maximum:
        raise ValueError("raw score is outside the declared rubric")
    return raw_score / maximum
