"""Real AE prose becomes reviewable criteria, never proof of implementation."""
import json
from pathlib import Path

import pytest

from agile_po_agent.wise_collectors import acceptance_criteria_candidates
from agile_po_agent.wise_tool import assess_verified_snapshot


@pytest.mark.parametrize("heading", [
    "Kabul:", "## Kabul kriterleri", "KABUL KRİTERLERİ:",
    "### Kabul ölçütleri", "**Kabul:**", "## Acceptance criteria",
])
def test_multiline_criteria_and_section_boundaries(heading: str) -> None:
    text = (f"{heading}\n- [ ] Tenant sınırı korunur.\n2. Rol reddi doğrulanır.\n"
            "Bağımlılık: DB\nPR henüz yok.")
    criteria = acceptance_criteria_candidates(text)
    assert [item["text"] for item in criteria] == [
        "Tenant sınırı korunur.", "Rol reddi doğrulanır.",
    ]
    assert all(item["verified"] is False and item["human_review_required"] for item in criteria)


def test_prose_without_declared_heading_is_not_an_acceptance_criterion() -> None:
    text = "Kaynak: PR henüz yok.\nKabul kriterleri tartışılacak."
    assert acceptance_criteria_candidates(text) == []
    assert acceptance_criteria_candidates("Kabul:\n\n## Kaynak\nTest geçti.") == []


@pytest.mark.parametrize("text", ["x" * 64001, "Kabul: " + "x" * 2001,
                                      "Kabul:\n" + "- Kriter\n" * 33])
def test_candidate_limits_fail_closed(text: str) -> None:
    with pytest.raises(ValueError, match="limit"):
        acceptance_criteria_candidates(text)


@pytest.mark.asyncio
async def test_actual_ae_task_preserves_criteria_without_claiming_ready() -> None:
    snapshot = json.loads((Path(__file__).parent / "fixtures/ae-scrum-73.json").read_text())
    result = await assess_verified_snapshot(
        {"installationId": "offline-ae", "site": "operoner.atlassian.net",
         "issueKey": "SCRUM-73"}, snapshot,
    )
    criteria = result["acceptance_criteria_candidates"]
    assert len(criteria) == 6
    assert "draft→satırlar→posted" in criteria[0]["text"]
    assert "VAT" in criteria[1]["text"]
    assert "operator/viewer" in criteria[2]["text"]
    assert "rollback" in criteria[3]["text"]
    assert "exact head CI" in criteria[4]["text"]
    assert not any("Bağımlılık" in c["text"] for c in criteria)
    assert result["readiness_interpretation"]["declared_acceptance_criteria_present"] is True
    assert result["readiness_interpretation"]["implementation_completion_assessed"] is False
    assert result["state"] == "needs_evidence"
    assert result["jev_required"] is False and result["jira_changed"] is False
    assert result["jev_skipped_reason"] == "no_claims"
