"""Strict versioned Jira collectors; independent of FIT/crypto/runtime hosting."""
from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from agile_po_agent.models import JiraTaskDraft
from agile_po_agent.wise_assess import Claim, ClaimKind


def _declared_claims(description: str, source_id: str) -> list[Claim]:
    """Only explicit, typed pilot claims are assessed; never infer them from prose."""

    matches = list(re.finditer(r"(?im)^## Wise (?:claims|iddiaları)\s*$", description))
    if len(matches) != 1:
        return []
    match = matches[0]
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
        if len(claims) >= 32 or len(declared.group(2)) > 2000:
            return []
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


