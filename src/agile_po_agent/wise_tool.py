"""Internal deterministic tool host; caller supplies its freshly verified Jira read.

No model arguments, OAuth tokens, environment secrets or remote calls are accepted.
JEV remains disabled until the concrete bounded provider authorization is supplied.
"""
import re
from datetime import datetime, timezone
from typing import Any

from agile_po_agent.config import Settings
from agile_po_agent.wise_assess import (
    AssessmentInput,
    Evidence,
    EvidenceKind,
    JiraSnapshot,
    Judge,
    Scope,
    WiseAssessor,
)
from agile_po_agent.wise_collectors import _adf_markdown, _declared_claims, _normalized_draft
from agile_po_agent.wise_evidence import turkish_candidates


class OfflineJudge:
    called = False
    async def judge(self, claims: Any, evidence: Any) -> Any:
        self.called = True
        raise RuntimeError("Live JEV execution has not been authorized")


async def assess_verified_snapshot(
    scope: dict[str, Any], snapshot: dict[str, Any], judge: Judge | None = None,
    additional_evidence: list[Evidence] | None = None,
) -> dict[str, Any]:
    """Only expose over a private service binding behind FIT/user access checks."""
    verified = Scope(installation_id=scope["installationId"], site=scope["site"],
                     issue_key=scope["issueKey"])
    if snapshot["key"] != verified.issue_key:
        raise ValueError("Snapshot differs from verified issue")
    description = _adf_markdown(snapshot.get("description"))
    if not description.strip():
        description = "No Jira description evidence supplied."
    item = JiraSnapshot(scope=verified, summary=snapshot["summary"], description=description,
                        issue_type=snapshot["issueType"], status=snapshot["status"],
                        version=snapshot["version"],
                        updated_at=datetime.fromisoformat(
                            re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2",
                                   snapshot["version"].replace("Z", "+00:00"))))
    evidence = Evidence(scope=verified, source_id="jira-issue", kind=EvidenceKind.JIRA,
                        uri=f"https://{verified.site}/browse/{verified.issue_key}",
                        version=item.version, observed_at=datetime.now(timezone.utc),
                        access="available", freshness="current", finding=description)
    gate = judge if judge is not None else OfflineJudge()
    report = await WiseAssessor(Settings(), gate).assess(AssessmentInput(
        snapshot=item, evidence=[evidence, *(additional_evidence or [])],
        claims=_declared_claims(description, "jira-issue"),
        normalized_draft=_normalized_draft(item),
    ))
    result = report.model_dump(mode="json", by_alias=True)
    result["claim_candidates"] = (turkish_candidates(description)
                                  if not _declared_claims(description, "jira-issue") else [])
    result["jev_required"] = isinstance(gate, OfflineJudge) and gate.called
    return result
