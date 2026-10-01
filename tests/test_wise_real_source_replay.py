"""Minimized real-work source replay; not a live Forge/Jira/OpenAI A2A test."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agile_po_agent.config import Settings
from agile_po_agent.wise_assess import (
    AssessmentInput,
    Evidence,
    EvidenceKind,
    Scope,
    WiseAssessor,
    snapshot_from_jira,
)
from agile_po_agent.wise_rovo import _declared_claims, _normalized_draft
from tests.test_wise_rovo import NeverJudge


@pytest.mark.asyncio
async def test_minimized_scrum32_does_not_turn_done_or_jev_score_into_ready() -> None:
    fixture = json.loads((Path(__file__).parents[1] / "examples"
                          / "wise-scrum32-minimal-replay.json").read_text())
    assert fixture["content_complete"] is False
    assert fixture["live_a2a"] is False
    scope = Scope(**fixture["scope"])
    snapshot = snapshot_from_jira(scope, fixture["issue"])
    judge = NeverJudge()
    report = await WiseAssessor(Settings(), judge).assess(AssessmentInput(
        snapshot=snapshot,
        normalized_draft=_normalized_draft(snapshot),
        claims=_declared_claims(snapshot.description, "jira-issue"),
        evidence=[Evidence(
            scope=scope, source_id="jira-issue", kind=EvidenceKind.JIRA,
            uri=fixture["source_uri"], version=fixture["source_updated"],
            observed_at=datetime.now(timezone.utc), access="available", freshness="current",
            finding=f"Minimized source excerpt for: {snapshot.summary}",
        )],
    ))
    assert snapshot.status == "Done"
    assert report.state.value == fixture["expected"]["state"]
    assert report.jira_changed is False
    assert judge.calls == 0
    assert any("repository" in gap for gap in report.missing_evidence)
    assert report.checks["normalized_definition_of_ready_available"] is False
