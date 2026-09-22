import pytest
from pydantic import ValidationError

from agile_po_agent.models import JiraTaskDraft, ProductBrief
from tests.test_quality import ready_draft


def test_valid_product_brief_is_accepted() -> None:
    brief = ProductBrief(
        title="Generate a Jira-ready task",
        problem="Product ideas become vague tasks that require repeated clarification.",
        target_user="Product owners",
        desired_outcome="Produce one reviewable task draft locally.",
        business_value="Reduce refinement time and rework.",
    )
    assert brief.title == "Generate a Jira-ready task"


def test_invalid_product_brief_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ProductBrief(
            title="Short",
            problem="Too short",
            target_user="PO",
            desired_outcome="Short",
            business_value="Short",
        )


def test_valid_jira_task_draft_is_accepted() -> None:
    draft = ready_draft()
    assert isinstance(draft, JiraTaskDraft)


def test_invalid_jira_task_draft_is_rejected() -> None:
    with pytest.raises(ValidationError):
        JiraTaskDraft.model_validate({"summary": "Too short"})
