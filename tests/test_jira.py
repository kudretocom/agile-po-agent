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


def test_confirmed_update_uses_only_mocked_transport() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(204)

    client = JiraClient(settings(), transport=httpx.MockTransport(handler))
    client.update("TEST-1", ready_draft(), confirm=True)

    assert len(requests) == 1
    assert requests[0].method == "PUT"
    assert requests[0].url.path == "/rest/api/3/issue/TEST-1"


def test_confirmed_create_uses_only_mocked_transport() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(201, json={"key": "TEST-2"})

    client = JiraClient(settings(), transport=httpx.MockTransport(handler))
    assert client.create("TEST", ready_draft(), confirm=True) == "TEST-2"
    assert len(requests) == 1
    assert requests[0].method == "POST"
