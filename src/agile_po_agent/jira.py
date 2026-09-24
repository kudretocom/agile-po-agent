"""Guarded Jira Cloud REST adapter."""

from typing import Any
from urllib.parse import quote, urlsplit

import httpx

from agile_po_agent.config import Settings
from agile_po_agent.models import JiraTaskDraft


class JiraClient:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        if not settings.jira_base_url or not settings.jira_email or not settings.jira_api_token:
            raise ValueError("JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN are required")
        self.settings = settings
        self._transport = transport

    def read_issue(self, issue_key: str) -> dict[str, Any]:
        """Fetch one issue for Wise without invoking any write endpoint."""

        if not issue_key or not issue_key.replace("-", "").isalnum():
            raise ValueError("a Jira issue key is required")
        with self._client() as client:
            response = client.get(
                f"/rest/api/3/issue/{quote(issue_key, safe='')}",
                params={"fields": "summary,description,issuetype,status,updated,issuelinks"},
            )
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict) or payload.get("key") != issue_key:
            raise ValueError("Jira returned an unexpected issue")
        return payload

    def preview(self, draft: JiraTaskDraft, *, issue_key: str | None = None) -> dict[str, Any]:
        return {
            "mode": "update" if issue_key else "create",
            "issue_key": issue_key,
            "fields": {
                "summary": draft.summary,
                "description": draft.to_markdown(),
                "issue_type": draft.issue_type,
                "labels": draft.labels,
            },
        }

    def update(self, issue_key: str, draft: JiraTaskDraft, *, confirm: bool = False) -> None:
        if not confirm:
            raise PermissionError("Jira update requires explicit confirmation")
        payload = {
            "fields": {
                "summary": draft.summary,
                "description": _markdown_adf(draft.to_markdown()),
                "labels": draft.labels,
            }
        }
        with self._client() as client:
            response = client.put(f"/rest/api/3/issue/{issue_key}", json=payload)
            response.raise_for_status()

    def create(self, project_key: str, draft: JiraTaskDraft, *, confirm: bool = False) -> str:
        if not confirm:
            raise PermissionError("Jira creation requires explicit confirmation")
        payload = {
            "fields": {
                "project": {"key": project_key},
                "issuetype": {"name": draft.issue_type},
                "summary": draft.summary,
                "description": _markdown_adf(draft.to_markdown()),
                "labels": draft.labels,
            }
        }
        with self._client() as client:
            response = client.post("/rest/api/3/issue", json=payload)
            response.raise_for_status()
            issue_key = response.json().get("key")
        if not isinstance(issue_key, str):
            raise ValueError("Jira response did not contain an issue key")
        return issue_key

    def _client(self) -> httpx.Client:
        assert self.settings.jira_base_url
        assert self.settings.jira_email
        assert self.settings.jira_api_token
        parts = urlsplit(self.settings.jira_base_url)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            raise ValueError("JIRA_BASE_URL must be an HTTPS site URL")
        return httpx.Client(
            base_url=self.settings.jira_base_url.rstrip("/"),
            auth=(self.settings.jira_email, self.settings.jira_api_token),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            transport=self._transport,
            timeout=30.0,
        )


def _markdown_adf(markdown: str) -> dict[str, Any]:
    """Render lossless-enough paragraphs for an MVP without pretending Markdown is ADF."""

    content = []
    for line in markdown.splitlines():
        text = line.strip()
        if not text:
            continue
        content.append(
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        )
    return {"version": 1, "type": "doc", "content": content}
