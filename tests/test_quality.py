from agile_po_agent.models import AcceptanceCriterion, DeliveryEvidence, JiraTaskDraft
from agile_po_agent.quality import DefinitionOfReadyEvaluator, ShippingGate, normalize_score


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


def test_definition_of_ready_passes_complete_draft() -> None:
    result = DefinitionOfReadyEvaluator().evaluate(ready_draft())
    assert result.passed
    assert result.score == 1.0


def test_shipping_gate_requires_tests_and_thresholds() -> None:
    result = ShippingGate().evaluate(
        ready_to_ship=0.95,
        quality_normalized=0.9,
        evidence=DeliveryEvidence(
            tests_passed=True,
            lint_passed=True,
            typecheck_passed=False,
            human_approved=True,
        ),
    )
    assert not result.passed
    assert "typecheck_failed_or_missing" in result.failures


def test_normalize_score_rejects_out_of_range_value() -> None:
    try:
        normalize_score(3.4, 4)
    except ValueError as error:
        assert "outside" in str(error)
    else:
        raise AssertionError("invalid score should fail closed")


def test_shipping_gate_requires_human_approval() -> None:
    result = ShippingGate().evaluate(
        ready_to_ship=0.95,
        quality_normalized=0.9,
        evidence=DeliveryEvidence(
            tests_passed=True,
            lint_passed=True,
            typecheck_passed=True,
        ),
    )
    assert not result.passed
    assert "human_approval_missing" in result.failures


def test_definition_of_ready_returns_every_named_failure() -> None:
    draft = ready_draft().model_copy(
        update={
            "summary": "Too vague",
            "context": "Missing context",
            "scope": [],
            "test_plan": [],
        }
    )

    result = DefinitionOfReadyEvaluator().evaluate(draft)

    assert not result.passed
    assert result.failures == [
        "actionable_summary",
        "context_present",
        "scope_present",
        "test_plan_present",
    ]
