"""Bind operator-approved source references to the entire verified caller scope."""
from __future__ import annotations

import json
from typing import Any

import httpx

from agile_po_agent.wise_assess import Evidence, Scope
from agile_po_agent.wise_evidence import VersionedCollectors


async def collect_source_plan(scope: dict[str, Any], plan_json: str, *, github_token: str = "",
                              user_token: str = "", enabled: bool = False,
                              transport: httpx.AsyncBaseTransport | None = None) -> list[Evidence]:
    if not enabled:
        return []
    if len(plan_json.encode()) > 16_000:
        raise ValueError("Source plan exceeds limit")
    plan = json.loads(plan_json)
    fields = ["installationId", "cloudId", "site", "principal", "issueKey"]
    if not isinstance(plan, dict) or any(plan.get(field) != scope.get(field) for field in fields):
        raise PermissionError("Source plan differs from verified caller scope")
    github = plan.get("github", [])
    confluence = plan.get("confluence", [])
    if (not isinstance(github, list) or not isinstance(confluence, list)
            or len(github) + len(confluence) > 3):
        raise ValueError("At most three explicit source references")
    verified = Scope(installation_id=scope["installationId"], site=scope["site"],
                     issue_key=scope["issueKey"])
    collector = VersionedCollectors(verified, scope["cloudId"], enabled=True, transport=transport,
                                   repos={item["repo"] for item in github},
                                   pages={item["page"] for item in confluence})
    evidence = []
    for index, ref in enumerate(github):
        if ref.get("kind") == "file":
            item = await collector.github_file(
                ref["repo"], ref["commit"], ref["path"], github_token,
            )
        elif ref.get("kind") == "ci":
            item = await collector.github_checks(ref["repo"], ref["commit"], github_token)
        else:
            raise ValueError("Unsupported source reference")
        item.source_id = f"repository-{index}"
        evidence.append(item)
    for index, ref in enumerate(confluence):
        item = await collector.confluence_page(ref["page"], ref["version"], user_token)
        item.source_id = f"product-page-{index}"
        evidence.append(item)
    return evidence
