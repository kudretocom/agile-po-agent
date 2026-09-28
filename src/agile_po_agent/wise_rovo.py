"""Non-production, read-only Rovo A2A 1.0 adapter for Wise Assess.

The FIT and the invoking user's OAuth token are different credentials. The FIT
authenticates the invocation; only the user token may read that user's Jira issue.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlsplit
from uuid import UUID, uuid4

import httpx
import jwt
from pydantic import ValidationError

from agile_po_agent.config import Settings
from agile_po_agent.models import JiraTaskDraft
from agile_po_agent.wise_assess import (
    Assessment,
    AssessmentInput,
    Claim,
    ClaimKind,
    Evidence,
    EvidenceKind,
    Judge,
    Scope,
    WiseAssessor,
    WiseState,
    snapshot_from_jira,
)

_JWKS_URL = "https://forge.cdn.prod.atlassian-dev.net/.well-known/jwks.json"
_ISSUE_KEY = re.compile(r"^[A-Z][A-Z0-9]+-[0-9]+$")
_ALLOWED_INVOCATIONS = {"ISSUE_ASSIGNMENT", "ISSUE_COMMENT_MENTION"}
_MAX_BODY = 256_000


@dataclass(frozen=True)
class ForgeContext:
    installation_id: str
    cloud_id: str
    site: str
    principal: str


class FitVerifier:
    """Verify the Forge signature and bind the exact application/endpoint context."""

    def __init__(
        self, app_id: str, endpoint_key: str, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        if not app_id.startswith("ari:cloud:ecosystem::app/") or not endpoint_key:
            raise ValueError("Forge app ID and endpoint key must be configured")
        self.app_id = app_id
        self.endpoint_key = endpoint_key
        self.transport = transport

    async def verify(self, token: str) -> ForgeContext:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                raise ValueError("unsupported FIT header")
            async with httpx.AsyncClient(transport=self.transport, timeout=5.0) as client:
                response = await client.get(_JWKS_URL)
                response.raise_for_status()
            if len(response.content) > 100_000:
                raise ValueError("JWKS too large")
            keys = response.json().get("keys")
            if not isinstance(keys, list):
                raise ValueError("invalid JWKS")
            matching = [key for key in keys if isinstance(key, dict)
                        and key.get("kid") == header["kid"] and key.get("kty") == "RSA"]
            if len(matching) != 1:
                raise ValueError("FIT signing key not found")
            key = jwt.PyJWK.from_dict(matching[0]).key
            claims = jwt.decode(
                token, key, algorithms=["RS256"], audience=self.app_id,
                issuer="forge/invocation-token",
                options={"require": ["exp", "iat", "nbf", "iss", "aud"]},
            )
            app, context = claims["app"], claims["context"]
            if not isinstance(app, dict) or not isinstance(context, dict):
                raise ValueError("FIT context missing")
            if app.get("id") != self.app_id or not isinstance(app.get("module"), dict):
                raise ValueError("FIT app mismatch")
            if app["module"].get("key") != self.endpoint_key:
                raise ValueError("FIT endpoint mismatch")
            installation_id = app.get("installationId")
            cloud_id = context.get("cloudId")
            principal = claims.get("principal")
            site_url = context.get("siteUrl")
            if (not isinstance(installation_id, str) or not installation_id
                    or not isinstance(cloud_id, str) or not cloud_id
                    or not isinstance(principal, str) or not principal
                    or not isinstance(site_url, str) or not site_url):
                raise ValueError("FIT identity missing")
            UUID(cloud_id)
            site = urlsplit(site_url)
            if (site.scheme != "https" or not site.hostname
                    or not site.hostname.endswith(".atlassian.net")
                    or site.path not in ("", "/") or site.query or site.fragment
                    or site.username or site.password or site.port):
                raise ValueError("FIT site invalid")
            return ForgeContext(installation_id, cloud_id, site.hostname, principal)
        except (jwt.PyJWTError, KeyError, TypeError, ValueError, httpx.HTTPError) as error:
            raise PermissionError("Forge invocation could not be verified") from error


def _issue_from_message(message: Any, context: ForgeContext) -> tuple[str, str]:
    if not isinstance(message, dict) or message.get("role") != "ROLE_USER":
        raise ValueError("expected a Jira user message")
    parts = message.get("parts")
    if (not isinstance(parts, list) or not isinstance(message.get("messageId"), str)
            or not message["messageId"]):
        raise ValueError("message parts or ID missing")
    data_parts = [part["data"] for part in parts if isinstance(part, dict)
                  and isinstance(part.get("data"), dict)]
    if len(data_parts) != 1:
        raise ValueError("one structured Jira context is required")
    data = data_parts[0]
    if data.get("invocationType") not in _ALLOWED_INVOCATIONS:
        raise ValueError("invocation surface is not enabled for this pilot")
    if data.get("userAccountId") != context.principal:
        raise PermissionError("message principal differs from verified invocation")
    issue = data.get("issue")
    if not isinstance(issue, dict) or not isinstance(issue.get("fields"), dict):
        raise ValueError("work item context is required")
    key = issue["fields"].get("key")
    if not isinstance(key, str) or not _ISSUE_KEY.fullmatch(key):
        raise ValueError("invalid work item key")
    return key, message["messageId"]


def _declared_claims(description: str, source_id: str) -> list[Claim]:
    """Only explicit, typed pilot claims are assessed; never infer them from prose."""

    match = re.search(r"(?im)^## Wise claims\s*$", description)
    if not match:
        return []
    section = re.split(r"(?m)^## ", description[match.end():], maxsplit=1)[0]
    claims: list[Claim] = []
    for line in section.splitlines():
        if not line.strip():
            continue
        declared = re.fullmatch(r"- (issue|code_behavior|product_policy|external_fact): (.+)",
                                line.strip())
        if not declared:
            return []
        kind = ClaimKind(declared.group(1))
        claims.append(Claim(
            claim_id=f"claim-{len(claims) + 1}", text=declared.group(2), kind=kind,
            source_ids=[source_id] if kind == ClaimKind.ISSUE else [],
        ))
    return claims


def _adf_markdown(value: Any) -> str:
    """Preserve only the headings and lists needed for the strict pilot contract."""

    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""

    def plain(node: Any) -> str:
        if not isinstance(node, dict):
            return ""
        text_value = node.get("text")
        own = text_value if isinstance(text_value, str) else ""
        children = node.get("content")
        if not isinstance(children, list):
            return own
        return own + "".join(plain(child) for child in children)

    lines: list[str] = []
    children = value.get("content")
    if not isinstance(children, list):
        return ""
    for node in children:
        if not isinstance(node, dict):
            continue
        kind = node.get("type")
        if kind == "heading":
            attrs = node.get("attrs")
            level = attrs.get("level", 2) if isinstance(attrs, dict) else 2
            if level == 2:
                lines.append(f"## {plain(node)}")
        elif kind == "paragraph":
            lines.append(plain(node))
        elif kind in ("bulletList", "orderedList"):
            items = node.get("content")
            for child in items if isinstance(items, list) else []:
                if isinstance(child, dict) and child.get("type") == "listItem":
                    lines.append(f"- {plain(child)}")
    return "\n".join(lines)


def _normalized_draft(snapshot: Any) -> JiraTaskDraft | None:
    """Accept the existing JiraTaskDraft template only; never fill missing fields."""

    if snapshot.issue_type not in ("Story", "Task", "Bug"):
        return None
    parts = re.split(r"(?m)^## ([^\n]+)\s*$", snapshot.description)
    sections = {parts[index].strip().lower(): parts[index + 1].strip()
                for index in range(1, len(parts) - 1, 2)}

    def bullets(name: str, prefix: str = "- ") -> list[str]:
        return [line.removeprefix(prefix).strip() for line in sections.get(name, "").splitlines()
                if line.startswith(prefix)]

    criteria: list[dict[str, str]] = []
    for line in sections.get("acceptance criteria", "").splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(
            r"- \[ \] \*\*Given\*\* (.+), \*\*when\*\* (.+), "
            r"\*\*then\*\* (.+)\. Evidence: (.+)\.", line.strip()
        )
        if not match:
            return None
        criteria.append({
            "given": match.group(1), "when": match.group(2),
            "then": match.group(3), "evidence": match.group(4),
        })
    try:
        return JiraTaskDraft.model_validate({
            "summary": snapshot.summary, "issue_type": snapshot.issue_type,
            "context": sections.get("context"),
            "desired_outcome": sections.get("desired outcome"),
            "business_value": sections.get("business value"),
            "scope": bullets("scope"), "non_goals": bullets("non-goals"),
            "acceptance_criteria": criteria,
            "test_plan": bullets("test plan", "- [ ] "),
            "success_metrics": bullets("success metrics"),
            "user_story": sections.get("user story"),
        })
    except ValidationError:
        return None


def _task_text(report: Assessment) -> str:
    actions = " ".join(report.next_actions[:3])
    return (
        f"{report.issue['key']} · {report.state.value}: {report.reason}\n"
        f"Next: {actions}\nJira changed: No."
    )


def _task(report: Assessment) -> dict[str, Any]:
    task_id, context_id = str(uuid4()), str(uuid4())
    return {
        "id": task_id,
        "contextId": context_id,
        "status": {
            "state": "TASK_STATE_COMPLETED",
            "message": {
                "role": "ROLE_AGENT", "parts": [{"text": _task_text(report)}],
                "messageId": str(uuid4()), "taskId": task_id, "contextId": context_id,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "artifacts": [{
            "artifactId": str(uuid4()), "name": "wise.assessment.v1",
            "parts": [{"data": report.model_dump(by_alias=True, mode="json")}],
        }],
    }


def _rejected_task(reason: str) -> dict[str, Any]:
    task_id, context_id = str(uuid4()), str(uuid4())
    return {
        "id": task_id, "contextId": context_id,
        "status": {
            "state": "TASK_STATE_REJECTED",
            "message": {
                "role": "ROLE_AGENT", "parts": [{"text": reason}],
                "messageId": str(uuid4()), "taskId": task_id, "contextId": context_id,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }


class RovoPilot:
    """Bounded A2A endpoint; no Jira mutation methods or background task execution."""

    def __init__(
        self, verifier: FitVerifier, settings: Settings, judge: Judge,
        jira_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.verifier = verifier
        self.assessor = WiseAssessor(settings, judge)
        self.jira_transport = jira_transport
        self._tasks: dict[tuple[str, str, str, str], tuple[str, str, str, dict[str, Any]]] = {}
        self._messages: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    async def handle(self, headers: dict[str, str], payload: Any) -> tuple[int, dict[str, Any]]:
        authorization = headers.get("authorization", "")
        if not authorization.startswith("Bearer "):
            return 401, {"error": "Forge invocation required"}
        try:
            context = await self.verifier.verify(authorization.removeprefix("Bearer "))
        except PermissionError:
            return 401, {"error": "Forge invocation could not be verified"}
        if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
            return 400, {"error": "invalid JSON-RPC request"}
        request_id = payload.get("id")
        if not isinstance(request_id, (str, int)) or isinstance(request_id, bool):
            return 400, {"error": "JSON-RPC request ID required"}
        method = payload.get("method")
        if method == "GetTask":
            task_id = payload.get("params", {}).get("id") if isinstance(
                payload.get("params"), dict
            ) else None
            if not isinstance(task_id, str):
                return 200, _rpc_error(request_id, -32001, "Task not found")
            stored = self._tasks.get((context.installation_id, context.cloud_id,
                                      context.site, task_id))
            if not stored or stored[0] != context.principal:
                return 200, _rpc_error(request_id, -32001, "Task not found")
            user_token = headers.get("x-forge-oauth-user", "")
            issue_scope = Scope(installation_id=context.installation_id,
                                site=context.site, issue_key=stored[1])
            if not user_token or not await self._version_matches(
                issue_scope, context.cloud_id, user_token, stored[2]
            ):
                return 200, _rpc_error(request_id, -32001, "Task not available")
            return 200, _rpc_result(request_id, stored[3])
        if method != "SendMessage":
            return 200, _rpc_error(request_id, -32601, "Method not found")
        params = payload.get("params")
        try:
            if not isinstance(params, dict):
                raise ValueError("message parameters required")
            issue_key, message_id = _issue_from_message(params.get("message"), context)
        except (PermissionError, ValueError):
            return 200, _rpc_error(request_id, -32602, "Invalid Jira invocation context")
        message_key = (context.installation_id, context.cloud_id,
                       context.principal, message_id)
        user_token = headers.get("x-forge-oauth-user", "")
        if not user_token:
            return 200, _rpc_result(request_id, {"task": _rejected_task(
                "Cannot assess without the invoking user's Jira access token. "
                "Retry after access is available."
            )})
        duplicate = self._messages.get(message_key)
        if duplicate:
            if duplicate["issue_key"] != issue_key:
                return 200, _rpc_error(request_id, -32602, "Message ID reused for another issue")
            issue_scope = Scope(installation_id=context.installation_id,
                                site=context.site, issue_key=issue_key)
            if await self._version_matches(
                issue_scope, context.cloud_id, user_token, duplicate["version"]
            ):
                return 200, _rpc_result(request_id, {"task": duplicate["task"]})
            self._messages.pop(message_key, None)
        scope = Scope(
            installation_id=context.installation_id, site=context.site, issue_key=issue_key
        )
        report = await self._assess(scope, context.cloud_id, user_token)
        task = _task(report)
        self._tasks[(context.installation_id, context.cloud_id,
                     context.site, task["id"])] = (
                         context.principal, issue_key, report.issue["version"], task
                     )
        self._messages[message_key] = {
            "issue_key": issue_key, "version": report.issue["version"], "task": task,
        }
        if len(self._tasks) > 256:
            self._tasks.pop(next(iter(self._tasks)))
        if len(self._messages) > 256:
            self._messages.pop(next(iter(self._messages)))
        return 200, _rpc_result(request_id, {"task": task})

    async def _assess(self, scope: Scope, cloud_id: str, user_token: str) -> Assessment:
        try:
            raw = await self._fetch_issue(scope, cloud_id, user_token)
            snapshot = snapshot_from_jira(scope, raw)
            description = _adf_markdown(raw["fields"].get("description"))
            if description:
                snapshot = snapshot.model_copy(update={"description": description})
            source_id = "jira-issue"
            jira_evidence = Evidence(
                scope=scope, source_id=source_id, kind=EvidenceKind.JIRA,
                uri=f"https://{scope.site}/browse/{scope.issue_key}", version=snapshot.version,
                observed_at=datetime.now(timezone.utc), access="available", freshness="current",
                finding=f"Issue summary: {snapshot.summary}",
            )
            item = AssessmentInput(
                snapshot=snapshot, evidence=[jira_evidence],
                claims=_declared_claims(snapshot.description, source_id),
                normalized_draft=_normalized_draft(snapshot),
            )
            return await self.assessor.assess(item)
        except (httpx.HTTPError, ValueError, ValidationError):
            return Assessment(
                run_id=f"run-{uuid4().hex}",
                issue={"site": scope.site, "key": scope.issue_key, "version": "unknown",
                       "installation_id": scope.installation_id},
                state=WiseState.BLOCKED, reason="Jira issue could not be read or verified",
                next_actions=["Check access to this issue and retry."],
                evidence=[], checks={}, conflicts=[], missing_evidence=[],
                jev_skipped_reason="jira_read_or_scope_failed",
            )

    async def _fetch_issue(self, scope: Scope, cloud_id: str,
                           user_token: str) -> dict[str, Any]:
        async with httpx.AsyncClient(
            base_url=f"https://api.atlassian.com/ex/jira/{cloud_id}",
            transport=self.jira_transport, timeout=15.0,
            headers={"Authorization": f"Bearer {user_token}", "Accept": "application/json"},
        ) as client:
            response = await client.get(
                f"/rest/api/3/issue/{quote(scope.issue_key, safe='')}",
                params={"fields": "summary,description,issuetype,status,updated,issuelinks"},
            )
            response.raise_for_status()
            raw = response.json()
        if not isinstance(raw, dict):
            raise ValueError("invalid Jira response")
        return raw

    async def _version_matches(self, scope: Scope, cloud_id: str,
                               user_token: str, version: str) -> bool:
        if version == "unknown":
            return False
        try:
            raw = await self._fetch_issue(scope, cloud_id, user_token)
            return snapshot_from_jira(scope, raw).version == version
        except (httpx.HTTPError, ValueError, ValidationError):
            return False

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http" or scope.get("path") != "/a2a/json-rpc":
            await _send_json(send, 404, {"error": "not found"})
            return
        if scope.get("method") != "POST":
            await _send_json(send, 405, {"error": "method not allowed"})
            return
        body = bytearray()
        while True:
            event = await receive()
            if event["type"] != "http.request":
                return
            body.extend(event.get("body", b""))
            if len(body) > _MAX_BODY:
                await _send_json(send, 413, {"error": "request too large"})
                return
            if not event.get("more_body", False):
                break
        headers = {name.decode("latin1").lower(): value.decode("latin1")
                   for name, value in scope.get("headers", [])}
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            await _send_json(send, 400, {"error": "invalid JSON"})
            return
        status, result = await self.handle(headers, payload)
        await _send_json(send, status, result)


def _rpc_result(request_id: str | int, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _rpc_error(request_id: str | int, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


async def _send_json(send: Any, status: int, result: dict[str, Any]) -> None:
    body = json.dumps(result, separators=(",", ":")).encode("utf-8")
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json")]})
    await send({"type": "http.response.body", "body": body})
