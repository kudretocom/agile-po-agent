import httpx
import pytest

from agile_po_agent.config import Settings
from agile_po_agent.jira import JiraClient
from tests.test_quality import ready_draft


def settings() -> Settings:
    return Settings(
        jira_base_url="https://example.atlassian.net",
        jira_email="test@example.com",
        jira_api_token="test-only",
    )


def test_preview_is_read_only() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("dry-run must not send a request")

    client = JiraClient(settings(), transport=httpx.MockTransport(handler))
    preview = client.preview(ready_draft(), issue_key="TEST-1")
    assert preview["mode"] == "update"
    assert preview["issue_key"] == "TEST-1"


def test_update_requires_confirmation() -> None:
    client = JiraClient(settings())
    with pytest.raises(PermissionError, match="confirmation"):
        client.update("TEST-1", ready_draft())

