"""Read-only Wise assessment with evidence gates and narrow TypeSafe judgments."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from enum import Enum
from time import perf_counter
from typing import Any, Protocol
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from agile_po_agent.config import Settings
from agile_po_agent.jira import JiraClient
from agile_po_agent.models import JiraTaskDraft
from agile_po_agent.quality import DefinitionOfReadyEvaluator


class WiseState(str, Enum):
    BLOCKED = "blocked"
    NEEDS_DECISION = "needs_decision"
    NEEDS_EVIDENCE = "needs_evidence"
    READY = "ready"


class ClaimKind(str, Enum):
    ISSUE = "issue"
    CODE_BEHAVIOR = "code_behavior"
    PRODUCT_POLICY = "product_policy"
    EXTERNAL_FACT = "external_fact"


class EvidenceKind(str, Enum):
    JIRA = "jira"
    REPOSITORY = "repository"
    PRODUCT_DOCUMENT = "product_document"
    EXTERNAL = "external"


class Scope(BaseModel):
    installation_id: str = Field(min_length=1)
    site: str = Field(min_length=1)
    issue_key: str = Field(pattern=r"^[A-Z][A-Z0-9]+-\d+$")

    @model_validator(mode="after")
    def canonical_site(self) -> Scope:
        parts = urlsplit(f"https://{self.site}")
        if (parts.hostname != self.site or parts.path or parts.query or parts.fragment
                or not self.site.endswith(".atlassian.net")):
            raise ValueError("site must be a bare Atlassian hostname")
        return self


class JiraSnapshot(BaseModel):
    scope: Scope
    summary: str = Field(min_length=1)
    description: str = Field(min_length=1)
    issue_type: str = Field(min_length=1)
    status: str = Field(min_length=1)
    version: str = Field(min_length=1)
    updated_at: datetime
    links: list[str] = Field(default_factory=list)

    @field_validator("updated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("updated_at must include a timezone")
        return value


class Evidence(BaseModel):
    scope: Scope
    source_id: str = Field(min_length=1)
    kind: EvidenceKind
    uri: str = Field(min_length=1)
    version: str | None = None
    observed_at: datetime
    access: str = Field(pattern=r"^(available|missing|denied)$")
    freshness: str = Field(pattern=r"^(current|stale|unknown)$")
    finding: str = ""

    @model_validator(mode="after")
    def validate_reference(self) -> Evidence:
        parts = urlsplit(self.uri)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            raise ValueError("evidence URI must be HTTPS without credentials")
        if (self.kind in {EvidenceKind.JIRA, EvidenceKind.PRODUCT_DOCUMENT}
                and parts.hostname != self.scope.site):
            raise ValueError("Atlassian evidence must belong to the issue site")
        if self.kind == EvidenceKind.JIRA and parts.path not in {
            f"/browse/{self.scope.issue_key}",
            f"/rest/api/3/issue/{self.scope.issue_key}",
        }:
            raise ValueError("Jira evidence must refer to the scoped issue")
        if self.kind == EvidenceKind.REPOSITORY and self.version:
            if len(self.version) < 7 or len(self.version) > 64:
                raise ValueError("repository version must be a commit SHA")
            if any(c not in "0123456789abcdefABCDEF" for c in self.version):
                raise ValueError("repository version must be a commit SHA")
        if self.access == "available" and not self.finding.strip():
            raise ValueError("available evidence needs a finding, not merely a link")
        if self.freshness == "current" and (self.access != "available" or not self.version):
            raise ValueError("current evidence must be available and versioned")
        return self

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value


class Claim(BaseModel):
    claim_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    kind: ClaimKind
    source_ids: list[str] = Field(default_factory=list)


class Conflict(BaseModel):
    claim_id: str
    source_ids: tuple[str, str]
    description: str = Field(min_length=1)
    decision_owner: str = "Product Owner"
    chosen_rule: str | None = None
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    rationale: str | None = None
    source_versions: dict[str, str] = Field(default_factory=dict)
    follow_up_issue: str | None = None

    @property
    def is_resolved(self) -> bool:
        return bool(
            self.chosen_rule and self.resolved_by and self.resolved_at
            and self.rationale and set(self.source_ids) == set(self.source_versions)
        )


class EvidencePolicy(BaseModel):
    required: dict[ClaimKind, EvidenceKind] = Field(
        default_factory=lambda: {
            ClaimKind.ISSUE: EvidenceKind.JIRA,
            ClaimKind.CODE_BEHAVIOR: EvidenceKind.REPOSITORY,
            ClaimKind.PRODUCT_POLICY: EvidenceKind.PRODUCT_DOCUMENT,
            ClaimKind.EXTERNAL_FACT: EvidenceKind.EXTERNAL,
        }
    )

    @model_validator(mode="after")
    def cover_every_claim_kind(self) -> EvidencePolicy:
        if set(self.required) != set(ClaimKind):
            raise ValueError("evidence policy must cover every claim kind")
        return self


class AssessmentInput(BaseModel):
    snapshot: JiraSnapshot
    evidence: list[Evidence]
    claims: list[Claim]
    conflicts: list[Conflict] = Field(default_factory=list)
    normalized_draft: JiraTaskDraft | None = None
    open_decisions: list[str] = Field(default_factory=list)
    steps_used: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_scope_and_refs(self) -> AssessmentInput:
        scope = self.snapshot.scope
        ids = [item.source_id for item in self.evidence]
        if len(ids) != len(set(ids)):
            raise ValueError("source IDs must be unique")
        if any(item.scope != scope for item in self.evidence):
            raise ValueError("evidence scope differs from issue scope")
        if len({item.claim_id for item in self.claims}) != len(self.claims):
            raise ValueError("claim IDs must be unique")
        if any(not set(claim.source_ids) <= set(ids) for claim in self.claims):
            raise ValueError("claim cites an unknown source")
        for conflict in self.conflicts:
            if conflict.claim_id not in {claim.claim_id for claim in self.claims}:
                raise ValueError("conflict refers to an unknown claim")
            if len(set(conflict.source_ids)) != 2 or not set(conflict.source_ids) <= set(ids):
                raise ValueError("conflict requires two distinct source IDs")
            if not set(conflict.source_versions) <= set(conflict.source_ids):
                raise ValueError("conflict resolution has an unknown source")
            if any(
                next(item for item in self.evidence if item.source_id == source_id).version
                != version
                for source_id, version in conflict.source_versions.items()
            ):
                raise ValueError("conflict resolution references changed source versions")
        if self.normalized_draft and self.normalized_draft.summary != self.snapshot.summary:
            raise ValueError("normalized draft must match the issue summary")
        return self


class Judgment(BaseModel):
    claim_id: str
    relation: str = Field(pattern=r"^(supports|contradicts|insufficient)$")
    confidence: float = Field(ge=0, le=1)
    probabilities: dict[str, float]


class JevTrace(BaseModel):
    model: str
    judgments: list[Judgment]
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    latency_ms: float = Field(ge=0)
    quality_score: float = Field(default=0, ge=0, le=3)


class Assessment(BaseModel):
    schema_name: str = Field(default="wise.assessment.v1", alias="schema")
    run_id: str
    issue: dict[str, str]
    operation: str = "assess"
    state: WiseState
    reason: str
    next_actions: list[str] = Field(max_length=3)
    evidence: list[Evidence]
    checks: dict[str, bool]
    conflicts: list[Conflict]
    missing_evidence: list[str]
    jira_changed: bool = False
    trace: JevTrace | None = None

    @property
    def summary(self) -> str:
        return f"{self.issue['key']} · {self.state.value}: {self.reason} Jira changed: No."


class Judge(Protocol):
    async def judge(self, claims: list[Claim], evidence: list[Evidence]) -> JevTrace: ...


class TypeSafeClaimJudge:
    """Batch claim-to-evidence Choice questions; never ask JEV to authorize a write."""

    OPTIONS = {"supports", "contradicts", "insufficient"}
    QUALITY_LEVELS = [
        "No material support", "Major support gaps", "Minor support gaps",
        "Each claim directly supported",
    ]

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        if not settings.typesafe_api_key:
            raise ValueError("TYPESAFE_API_KEY is required")
        parts = urlsplit(settings.typesafe_api_url)
        if (parts.scheme != "https" or not parts.hostname or parts.username
                or parts.password or parts.query or parts.fragment):
            raise ValueError("TYPESAFE_API_URL must be an HTTPS endpoint")
        self.settings = settings
        self.transport = transport

    async def judge(self, claims: list[Claim], evidence: list[Evidence]) -> JevTrace:
        by_id = {item.source_id: item for item in evidence}
        questions: dict[str, dict[str, Any]] = {
            f"claim_{index}": {
                "type": "choice",
                "instructions": (
                    "Does the quoted evidence substantiate the claim? Judge only the supplied "
                    "source findings, not the truth of missing sources."
                ),
                "criteria": {
                    "supports": "The findings directly support the specific claim.",
                    "contradicts": "The findings materially oppose the specific claim.",
                    "insufficient": "The findings do not settle the specific claim.",
                },
            }
            for index, _ in enumerate(claims)
        }
        questions["readiness_quality"] = {
            "type": "score",
            "instructions": "Rate how strongly the cited findings support the claims as a whole.",
            "criteria": self.QUALITY_LEVELS,
        }
        state = {
            f"claim_{index}": {
                "claim": claim.text,
                "evidence": [
                    {"source_id": source_id, "finding": by_id[source_id].finding}
                    for source_id in claim.source_ids
                ],
            }
            for index, claim in enumerate(claims)
        }
        for index in range(len(claims)):
            questions[f"claim_{index}"]["instructions"] += (
                f" Evaluate `claim_{index}.claim` against `claim_{index}.evidence`."
            )
        started = perf_counter()
        try:
            async with httpx.AsyncClient(
                transport=self.transport, timeout=self.settings.typesafe_timeout_seconds
            ) as client:
                response = await client.post(
                    self.settings.typesafe_api_url,
                    json={
                        "model": self.settings.typesafe_model,
                        "state": state,
                        "questions": questions,
                    },
                    headers={"Authorization": f"Bearer {self.settings.typesafe_api_key}"},
                )
            response.raise_for_status()
            if len(response.content) > self.settings.typesafe_max_response_bytes:
                raise ValueError("JEV response exceeded size limit")
            payload = response.json()
            if (not isinstance(payload, dict)
                    or not {"model", "answers", "usage"} <= set(payload)):
                raise ValueError("malformed JEV envelope")
            answers, usage = payload["answers"], payload["usage"]
            if not isinstance(answers, dict) or set(answers) != set(questions):
                raise ValueError("malformed JEV answers")
            if (not isinstance(usage, dict) or not isinstance(payload["model"], str)
                    or not payload["model"]):
                raise ValueError("malformed JEV metadata")
            judgments = []
            for index, claim in enumerate(claims):
                answer = answers[f"claim_{index}"]
                if not isinstance(answer, dict) or answer.get("type") != "choice":
                    raise ValueError("malformed JEV choice")
                probabilities = answer.get("probabilities")
                if not isinstance(probabilities, dict) or set(probabilities) != self.OPTIONS:
                    raise ValueError("malformed JEV probabilities")
                if any(
                    isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or not 0 <= value <= 1
                    for value in probabilities.values()
                ) or not math.isclose(sum(probabilities.values()), 1, abs_tol=0.03):
                    raise ValueError("invalid JEV probabilities")
                choice = answer.get("choice")
                if choice not in self.OPTIONS or probabilities[choice] < max(
                    probabilities.values()
                ):
                    raise ValueError("invalid JEV choice")
                confidence = answer.get("confidence")
                if (isinstance(confidence, bool) or not isinstance(confidence, (int, float))
                        or not math.isfinite(confidence) or not 0 <= confidence <= 1):
                    raise ValueError("invalid JEV confidence")
                judgments.append(
                    Judgment(
                        claim_id=claim.claim_id,
                        relation=choice,
                        confidence=float(confidence),
                        probabilities=probabilities,
                    )
                )
            quality = answers["readiness_quality"]
            if not isinstance(quality, dict) or quality.get("type") != "score":
                raise ValueError("malformed JEV score")
            quality_score = quality.get("score")
            if (isinstance(quality_score, bool) or not isinstance(quality_score, (int, float))
                    or not math.isfinite(quality_score) or not 0 <= quality_score <= 3):
                raise ValueError("invalid JEV score")
            expected_legend = {
                str(index): level for index, level in enumerate(self.QUALITY_LEVELS)
            }
            if quality.get("legend") != expected_legend:
                raise ValueError("invalid JEV score legend")
            score_probabilities = quality.get("probabilities")
            if (not isinstance(score_probabilities, dict)
                    or set(score_probabilities) != set(expected_legend)
                    or any(
                        isinstance(value, bool) or not isinstance(value, (int, float))
                        or not math.isfinite(value) or not 0 <= value <= 1
                        for value in score_probabilities.values()
                    )):
                raise ValueError("invalid JEV score probabilities")
            if not math.isclose(sum(score_probabilities.values()), 1, abs_tol=0.03):
                raise ValueError("invalid JEV score distribution")
            expected_score = sum(
                index * score_probabilities[str(index)] for index in range(4)
            )
            if not math.isclose(quality_score, expected_score, abs_tol=0.04):
                raise ValueError("JEV score contradicts its distribution")
            score_confidence = quality.get("confidence")
            if (isinstance(score_confidence, bool)
                    or not isinstance(score_confidence, (int, float))
                    or not math.isfinite(score_confidence)
                    or not 0 <= score_confidence <= 1):
                raise ValueError("invalid JEV score confidence")
            input_tokens = usage.get("input_tokens")
            output_tokens = usage.get("output_tokens")
            if (not isinstance(input_tokens, int) or isinstance(input_tokens, bool)
                    or input_tokens < 0 or not isinstance(output_tokens, int)
                    or isinstance(output_tokens, bool) or output_tokens < 0):
                raise ValueError("invalid JEV usage")
            return JevTrace(
                model=payload["model"], judgments=judgments,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=(perf_counter() - started) * 1000,
                quality_score=quality_score,
            )
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise RuntimeError("JEV evaluation failed or returned invalid data") from error


class WiseAssessor:
    def __init__(self, settings: Settings, judge: Judge, policy: EvidencePolicy | None = None):
        self.settings = settings
        self.judge = judge
        self.policy = policy or EvidencePolicy()

    async def assess_issue(
        self,
        client: JiraClient,
        scope: Scope,
        *,
        expected_installation_id: str,
        evidence: list[Evidence],
        claims: list[Claim],
        normalized_draft: JiraTaskDraft | None = None,
        conflicts: list[Conflict] | None = None,
        open_decisions: list[str] | None = None,
    ) -> Assessment:
        """Load a live issue, then assess; operational failures return Blocked."""

        try:
            snapshot = read_scoped_issue(
                client, scope, expected_installation_id=expected_installation_id
            )
            item = AssessmentInput(
                snapshot=snapshot, evidence=evidence, claims=claims,
                normalized_draft=normalized_draft, conflicts=conflicts or [],
                open_decisions=open_decisions or [],
            )
        except (httpx.HTTPError, PermissionError, ValueError, ValidationError):
            return Assessment(
                run_id=f"run-{uuid4().hex}",
                issue={"site": scope.site, "key": scope.issue_key, "version": "unknown",
                       "installation_id": scope.installation_id},
                state=WiseState.BLOCKED,
                reason="Jira snapshot or scoped evidence could not be verified",
                next_actions=["Check access and installation context, then retry the read."],
                evidence=[], checks={}, conflicts=[], missing_evidence=[],
            )
        return await self.assess(item)

    async def assess(self, item: AssessmentInput) -> Assessment:
        snapshot = item.snapshot
        by_id = {e.source_id: e for e in item.evidence}
        checks: dict[str, bool] = {}
        if item.normalized_draft:
            checks = DefinitionOfReadyEvaluator(self.settings.ready_threshold).evaluate(
                item.normalized_draft
            ).checks
        else:
            checks["normalized_definition_of_ready_available"] = False
        missing: list[str] = []
        blocked: list[str] = []
        jira_sources = [e for e in item.evidence if e.kind == EvidenceKind.JIRA]
        if not any(e.access == "available" and e.freshness == "current"
                   and e.version == snapshot.version for e in jira_sources):
            blocked.append("Current versioned Jira snapshot evidence is unavailable")
        for claim in item.claims:
            required = self.policy.required[claim.kind]
            cited = [by_id[source_id] for source_id in claim.source_ids]
            matching = [source for source in cited if source.kind == required]
            if any(source.access == "denied" for source in matching):
                blocked.append(f"Access denied to required {required.value} for {claim.claim_id}")
            elif not any(source.access == "available" and source.freshness == "current"
                         for source in matching):
                missing.append(f"{claim.claim_id}: current, versioned {required.value} content")
        if any(e.access == "denied" for e in item.evidence):
            blocked.append("Evidence access denied")
        if item.steps_used >= self.settings.max_steps:
            blocked.append("Assessment step cap reached")
        if not item.claims:
            missing.append("At least one explicit claim with cited evidence")
        check_gaps = [
            f"Definition of Ready: {name}" for name, ok in checks.items() if not ok
        ]
        trace: JevTrace | None = None
        if not blocked and not missing and item.claims:
            try:
                trace = await self.judge.judge(item.claims, item.evidence)
                if {j.claim_id for j in trace.judgments} != {c.claim_id for c in item.claims}:
                    raise ValueError("JEV did not assess every claim")
            except (RuntimeError, ValueError):
                blocked.append("JEV unavailable or response invalid; retry safely")
        unresolved = [c for c in item.conflicts if not c.is_resolved]
        uncertain = bool(trace and any(
            judgment.confidence < self.settings.jev_choice_confidence_threshold
            or judgment.relation == "contradicts"
            for judgment in trace.judgments
        ))
        insufficient = bool(trace and any(
            judgment.relation == "insufficient" for judgment in trace.judgments
        ))
        if trace and trace.quality_score / 3 < self.settings.quality_threshold:
            insufficient = True
        missing.extend(check_gaps)
        if blocked:
            state, reason = WiseState.BLOCKED, blocked[0]
            actions = [
                "Retry after resolving the blocker; contact the service owner if needed."
            ]
        elif unresolved or item.open_decisions or uncertain:
            state, reason = WiseState.NEEDS_DECISION, (
                unresolved[0].description if unresolved else
                item.open_decisions[0] if item.open_decisions else
                "TypeSafe judgment is uncertain or identifies a contradiction"
            )
            actions = ["Product Owner reviews the cited sources and records the decision."]
        elif missing or insufficient:
            state, reason = WiseState.NEEDS_EVIDENCE, (
                missing[0] if missing else "TypeSafe found the cited evidence insufficient"
            )
            actions = ["Collect the named current, versioned evidence and reassess."]
        else:
            state, reason = WiseState.READY, "All required evidence and readiness checks passed"
            actions = ["Hand the issue to development for review."]
        return Assessment(
            run_id=f"run-{uuid4().hex}",
            issue={"site": snapshot.scope.site, "key": snapshot.scope.issue_key,
                   "version": snapshot.version, "installation_id": snapshot.scope.installation_id},
            state=state, reason=reason, next_actions=actions,
            evidence=item.evidence, checks=checks, conflicts=item.conflicts,
            missing_evidence=missing, trace=trace,
        )


def snapshot_from_jira(scope: Scope, raw: dict[str, Any]) -> JiraSnapshot:
    """Validate only the fields Wise needs; never infer missing issue data."""

    if raw.get("key") != scope.issue_key or not isinstance(raw.get("fields"), dict):
        raise ValueError("Jira issue does not match request scope")
    fields = raw["fields"]
    description = fields.get("description")
    if isinstance(description, dict):
        description = _adf_text(description)
    links = fields.get("issuelinks") or []
    issue_type = fields.get("issuetype")
    status = fields.get("status")
    if not isinstance(issue_type, dict) or not isinstance(status, dict):
        raise ValueError("Jira issue type or status is missing")
    if not isinstance(links, list):
        raise ValueError("Jira issue links are malformed")
    issue_type_name = issue_type.get("name")
    status_name = status.get("name")
    if not isinstance(issue_type_name, str) or not isinstance(status_name, str):
        raise ValueError("Jira issue type or status is malformed")
    return JiraSnapshot(
        scope=scope, summary=fields.get("summary"), description=description,
        issue_type=issue_type_name, status=status_name,
        version=str(raw.get("version") or fields.get("updated") or ""),
        updated_at=fields.get("updated"),
        links=[str(link.get("id")) for link in links if isinstance(link, dict)],
    )


def _adf_text(node: Any) -> str:
    if not isinstance(node, dict):
        return ""
    chunks = [node["text"]] if isinstance(node.get("text"), str) else []
    for child in node.get("content", []):
        chunks.append(_adf_text(child))
    return " ".join(chunk for chunk in chunks if chunk)


def read_scoped_issue(
    client: JiraClient, scope: Scope, *, expected_installation_id: str
) -> JiraSnapshot:
    """Bind tenant identity before the only network read; do not trust model-supplied site."""

    configured = urlsplit(client.settings.jira_base_url or "").hostname
    if configured != scope.site or scope.installation_id != expected_installation_id:
        raise PermissionError("requested site/install differs from the authorized Jira context")
    return snapshot_from_jira(scope, client.read_issue(scope.issue_key))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
