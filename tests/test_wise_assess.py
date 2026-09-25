"""Offline contract tests for Wise's read-only assessment slice."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest

from agile_po_agent.config import Settings
from agile_po_agent.jira import JiraClient
from agile_po_agent.wise_assess import (
    Assessment,
    AssessmentInput,
    Claim,
    ClaimKind,
    Conflict,
    Evidence,
    EvidenceKind,
    JevTrace,
    JiraSnapshot,
    Judgment,
    Scope,
    TypeSafeClaimJudge,
    WiseAssessor,
    WiseState,
    read_scoped_issue,
)
from tests.test_quality import ready_draft

NOW = datetime(2026, 9, 24, tzinfo=timezone.utc)
SCOPE = Scope(installation_id="pilot-install", site="example.atlassian.net", issue_key="SCRUM-42")


def settings(**overrides: Any) -> Settings:
    return Settings(
        typesafe_api_key="test-only",
        jira_base_url="https://example.atlassian.net",
        jira_email="test@example.com",
        jira_api_token="test-only",
        **overrides,
    )


def evidence(
    source_id: str,
    kind: EvidenceKind,
    *,
    version: str | None = "17",
    freshness: str = "current",
    access: str = "available",
    scope: Scope = SCOPE,
) -> Evidence:
    return Evidence(
        scope=scope, source_id=source_id, kind=kind,
        uri=(f"https://{scope.site}/browse/{scope.issue_key}"
             if kind == EvidenceKind.JIRA else f"https://example.atlassian.net/{source_id}"),
        version=version,
        observed_at=NOW, access=access, freshness=freshness,
        finding="A versioned source supports the stated behavior." if access == "available" else "",
    )


def item(
    *,
    sources: list[Evidence] | None = None,
    conflicts: list[Conflict] | None = None,
    normalized: bool = True,
    steps_used: int = 0,
) -> AssessmentInput:
    draft = ready_draft()
    return AssessmentInput(
        snapshot=JiraSnapshot(
            scope=SCOPE, summary=draft.summary, description=draft.to_markdown(),
            issue_type="Task", status="To Do", version="17", updated_at=NOW,
        ),
        evidence=sources if sources is not None else [
            evidence("jira-1", EvidenceKind.JIRA),
            evidence("repo-1", EvidenceKind.REPOSITORY, version="abcdef0123456789"),
        ],
        claims=[Claim(
            claim_id="claim-1", text="Existing behavior limits access to the selected employer",
            kind=ClaimKind.CODE_BEHAVIOR, source_ids=["repo-1"],
        )],
        conflicts=conflicts or [], normalized_draft=draft if normalized else None,
        steps_used=steps_used,
    )


class StubJudge:
    def __init__(self, *, confidence: float = 0.96, relation: str = "supports") -> None:
        self.confidence = confidence
        self.relation = relation
        self.calls = 0

    async def judge(self, claims: list[Claim], evidence: list[Evidence]) -> JevTrace:
        self.calls += 1
        return JevTrace(
            model="jev-test", input_tokens=12, output_tokens=4,
            latency_ms=5, quality_score=3,
            judgments=[Judgment(
                claim_id=claim.claim_id, relation=self.relation,
                confidence=self.confidence,
                probabilities={"supports": 0.96, "contradicts": 0.02, "insufficient": 0.02},
            ) for claim in claims],
        )


@pytest.mark.asyncio
async def test_ready_report_is_versioned_read_only_and_matches_summary() -> None:
    judge = StubJudge()
    report = await WiseAssessor(settings(), judge).assess(item())
    serialized = report.model_dump(by_alias=True, mode="json")
    assert serialized["schema"] == "wise.assessment.v1"
    assert serialized["state"] == "ready"
    assert serialized["jira_changed"] is False
    assert "ready" in report.summary
    assert report.trace and report.trace.model == "jev-test"
    assert judge.calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("freshness,version", [
    ("stale", "abcdef0123456789"), ("unknown", None), ("current", None),
])
async def test_required_code_source_must_be_current_and_versioned(
    freshness: str, version: str | None
) -> None:
    if freshness == "current" and version is None:
        with pytest.raises(ValueError, match="versioned"):
            evidence("repo-1", EvidenceKind.REPOSITORY, version=version, freshness=freshness)
        return
    sources = [evidence("jira-1", EvidenceKind.JIRA), evidence(
        "repo-1", EvidenceKind.REPOSITORY, version=version, freshness=freshness
    )]
    judge = StubJudge()
    report = await WiseAssessor(settings(), judge).assess(item(sources=sources))
    assert report.state == WiseState.NEEDS_EVIDENCE
    assert "repository" in report.missing_evidence[0]
    assert judge.calls == 0


@pytest.mark.asyncio
async def test_absent_required_source_is_named() -> None:
    baseline = item()
    without_repository = AssessmentInput(
        snapshot=baseline.snapshot,
        evidence=[evidence("jira-1", EvidenceKind.JIRA)],
        claims=[Claim(
            claim_id="claim-1", text="Current code restricts access",
            kind=ClaimKind.CODE_BEHAVIOR, source_ids=[],
        )],
        normalized_draft=baseline.normalized_draft,
    )
    report = await WiseAssessor(settings(), StubJudge()).assess(without_repository)
    assert report.state == WiseState.NEEDS_EVIDENCE
    assert report.missing_evidence == ["claim-1: current, versioned repository content"]


@pytest.mark.asyncio
async def test_conflict_beats_missing_check_and_needs_two_cited_sources() -> None:
    conflict = Conflict(
        claim_id="claim-1", source_ids=("jira-1", "repo-1"),
        description="Product and code disagree about access", decision_owner="Product Owner",
    )
    judge = StubJudge()
    report = await WiseAssessor(settings(), judge).assess(
        item(conflicts=[conflict], normalized=False)
    )
    assert report.state == WiseState.NEEDS_DECISION
    assert report.conflicts[0].source_ids == ("jira-1", "repo-1")
    assert report.missing_evidence == [
        "Definition of Ready: normalized_definition_of_ready_available"
    ]
    assert judge.calls == 0
    assert report.trace is None
    assert report.jev_skipped_reason == "human_decision_required"


@pytest.mark.asyncio
async def test_open_decision_skips_jev() -> None:
    judge = StubJudge()
    baseline = item()
    issue = baseline.model_copy(update={"open_decisions": ["Choose the access policy"]})
    report = await WiseAssessor(settings(), judge).assess(issue)
    assert report.state == WiseState.NEEDS_DECISION
    assert report.jev_skipped_reason == "human_decision_required"
    assert judge.calls == 0


@pytest.mark.asyncio
async def test_uncertain_jev_requires_decision() -> None:
    report = await WiseAssessor(settings(), StubJudge(confidence=0.6)).assess(item())
    assert report.state == WiseState.NEEDS_DECISION


@pytest.mark.asyncio
async def test_failed_deterministic_check_skips_jev() -> None:
    judge = StubJudge()
    report = await WiseAssessor(settings(), judge).assess(item(normalized=False))
    assert judge.calls == 0
    assert report.trace is None
    assert report.state == WiseState.NEEDS_EVIDENCE
    assert report.jev_skipped_reason == "missing_evidence_or_failed_check"


@pytest.mark.asyncio
async def test_step_cap_and_denied_source_block() -> None:
    capped = await WiseAssessor(settings(max_steps=3), StubJudge()).assess(item(steps_used=3))
    assert capped.state == WiseState.BLOCKED
    sources = [evidence("jira-1", EvidenceKind.JIRA), evidence(
        "repo-1", EvidenceKind.REPOSITORY, version=None,
        freshness="unknown", access="denied"
    )]
    denied = await WiseAssessor(settings(), StubJudge()).assess(item(sources=sources))
    assert denied.state == WiseState.BLOCKED


@pytest.mark.asyncio
async def test_malformed_jev_response_blocks() -> None:
    judge = TypeSafeClaimJudge(settings(), transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json={"answers": {}})
    ))
    report = await WiseAssessor(settings(), judge).assess(item())
    assert report.state == WiseState.BLOCKED
    assert report.trace is None


@pytest.mark.asyncio
async def test_typesafe_choice_and_score_fixture_is_used() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={
            "model": "jev-1.13.0",
            "answers": {
                "claim_0": {
                    "type": "choice", "choice": "supports", "confidence": 0.96,
                    "probabilities": {
                        "supports": 0.97, "contradicts": 0.0, "insufficient": 0.03,
                    },
                    "stats": {},
                },
                "readiness_quality": {
                    "type": "score", "score": 2.93, "confidence": 0.93,
                    "legend": {
                        "0": "No material support", "1": "Major support gaps",
                        "2": "Minor support gaps", "3": "Each claim directly supported",
                    },
                    "probabilities": {"0": 0.0, "1": 0.01, "2": 0.04, "3": 0.95},
                    "stats": {},
                },
            },
            "usage": {"input_tokens": 507, "output_tokens": 61},
            "request_id": "playground-synthetic-test",
            "evaluation_time_ms": 53.9,
        })

    judge = TypeSafeClaimJudge(settings(), transport=httpx.MockTransport(handler))
    report = await WiseAssessor(settings(), judge).assess(item())
    assert report.state == WiseState.READY
    assert report.trace and report.trace.model == "jev-1.13.0"
    assert len(requests) == 1
    payload = json.loads(requests[0].content)
    assert payload["model"] == "jev-latest"
    assert set(payload["questions"]) == {"claim_0", "readiness_quality"}
    assert payload["state"]["claims"] == [{
        "text": "Existing behavior limits access to the selected employer",
        "source_ids": ["repo-1"],
    }]
    assert payload["state"]["evidence"] == {
        "repo-1": "A versioned source supports the stated behavior."
    }
    assert requests[0].method == "POST"


@pytest.mark.asyncio
async def test_shared_source_is_sent_once_for_multiple_claims() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={
            "model": "jev-1.13.0",
            "answers": {
                **{f"claim_{index}": {
                    "type": "choice", "choice": "supports", "confidence": 0.96,
                    "probabilities": {
                        "supports": 0.97, "contradicts": 0.0, "insufficient": 0.03,
                    },
                } for index in range(3)},
                "readiness_quality": {
                    "type": "score", "score": 2.93, "confidence": 0.93,
                    "legend": {
                        "0": "No material support", "1": "Major support gaps",
                        "2": "Minor support gaps", "3": "Each claim directly supported",
                    },
                    "probabilities": {"0": 0.0, "1": 0.01, "2": 0.04, "3": 0.95},
                },
            },
            "usage": {"input_tokens": 300, "output_tokens": 100},
        })

    claims = [Claim(
        claim_id=f"claim-{index}", text=f"Supported behavior {index}",
        kind=ClaimKind.CODE_BEHAVIOR, source_ids=["repo-1"],
    ) for index in range(3)]
    judge = TypeSafeClaimJudge(settings(), transport=httpx.MockTransport(handler))
    trace = await judge.judge(claims, [evidence(
        "repo-1", EvidenceKind.REPOSITORY, version="abcdef0123456789"
    )])
    assert len(requests) == 1
    payload = json.loads(requests[0].content)
    assert len(payload["state"]["claims"]) == 3
    assert len(payload["state"]["evidence"]) == 1
    assert len(trace.judgments) == 3


@pytest.mark.asyncio
async def test_jev_timeout_blocks() -> None:
    def timeout(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("fixture")

    judge = TypeSafeClaimJudge(settings(), transport=httpx.MockTransport(timeout))
    report = await WiseAssessor(settings(), judge).assess(item())
    assert report.state == WiseState.BLOCKED


def test_other_installation_or_site_cannot_supply_evidence() -> None:
    other_install = SCOPE.model_copy(update={"installation_id": "other-install"})
    sources = [evidence("jira-1", EvidenceKind.JIRA, scope=other_install)]
    with pytest.raises(ValueError, match="scope"):
        item(sources=sources)
    with pytest.raises(ValueError, match="issue site"):
        Evidence(
            scope=SCOPE, source_id="jira-2", kind=EvidenceKind.JIRA,
            uri="https://other.atlassian.net/browse/SCRUM-42", version="17",
            observed_at=NOW, access="available", freshness="current",
            finding="A different tenant's issue must not be admitted.",
        )


def test_versioned_example_matches_assessment_schema() -> None:
    path = Path(__file__).resolve().parents[1] / "examples/wise-assessment-example.json"
    report = Assessment.model_validate_json(path.read_text())
    assert report.state == WiseState.NEEDS_DECISION
    assert report.jira_changed is False
    assert "needs_decision" in report.summary


def test_scoped_jira_read_uses_get_only_and_rejects_wrong_context() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={
            "key": "SCRUM-42", "fields": {
                "summary": "A valid issue", "description": {"type": "doc", "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "Issue context"}]}
                ]},
                "issuetype": {"name": "Task"}, "status": {"name": "To Do"},
                "updated": "2026-09-24T12:00:00Z", "issuelinks": [{"id": "123"}],
            },
        })

    client = JiraClient(settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(PermissionError):
        read_scoped_issue(client, SCOPE, expected_installation_id="other-install")
    assert requests == []
    snapshot = read_scoped_issue(client, SCOPE, expected_installation_id="pilot-install")
    assert snapshot.description == "Issue context"
    assert snapshot.links == ["123"]
    assert len(requests) == 1 and requests[0].method == "GET"


@pytest.mark.asyncio
async def test_read_failure_returns_blocked_without_jira_write() -> None:
    requests: list[httpx.Request] = []

    def missing(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(404)

    client = JiraClient(settings(), transport=httpx.MockTransport(missing))
    report = await WiseAssessor(settings(), StubJudge()).assess_issue(
        client, SCOPE, expected_installation_id="pilot-install",
        evidence=[], claims=[],
    )
    assert report.state == WiseState.BLOCKED
    assert report.jira_changed is False
    assert len(requests) == 1 and requests[0].method == "GET"


@pytest.mark.asyncio
async def test_wrong_installation_blocks_before_network() -> None:
    def unexpected(_: httpx.Request) -> httpx.Response:
        raise AssertionError("wrong installation must not reach Jira")

    client = JiraClient(settings(), transport=httpx.MockTransport(unexpected))
    report = await WiseAssessor(settings(), StubJudge()).assess_issue(
        client, SCOPE, expected_installation_id="another-install",
        evidence=[], claims=[],
    )
    assert report.state == WiseState.BLOCKED
