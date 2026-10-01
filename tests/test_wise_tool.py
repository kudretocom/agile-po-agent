"""Actual deterministic host path; no credentials/model calls required."""
import pytest

from agile_po_agent.wise_tool import assess_verified_snapshot


@pytest.mark.asyncio
async def test_verified_turkish_snapshot_uses_deterministic_gates_without_model_evidence() -> None:
    scope = {"installationId": "fixture", "site": "fixture.atlassian.net", "issueKey": "SCRUM-32"}
    snapshot = {"key": "SCRUM-32", "summary": "Separate tenant and external client grants",
                "description": "## Wise iddiaları\n- code_behavior: Tenant sınırı korunur",
                "issueType": "Task", "status": "Done", "version": "2026-10-01T00:00:00.000+0000"}
    result = await assess_verified_snapshot(scope, snapshot)
    assert result["state"] == "needs_evidence"
    assert result["jira_changed"] is False
    assert result["issue"]["key"] == "SCRUM-32"
    with pytest.raises(ValueError, match="verified issue"):
        await assess_verified_snapshot(scope, {**snapshot, "key": "SCRUM-99"})
