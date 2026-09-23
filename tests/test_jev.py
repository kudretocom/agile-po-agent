import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import httpx
import pytest

from agile_po_agent.config import Settings
from agile_po_agent.jev import JevEvaluationError, TypeSafeJevClient
from agile_po_agent.models import ActionDecision, Worker

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "jev-systemone-response.json"


def fixture_response() -> dict[str, Any]:
    value = json.loads(FIXTURE_PATH.read_text())
    assert isinstance(value, dict)
    return value


def client(transport: httpx.AsyncBaseTransport | None = None) -> TypeSafeJevClient:
    return TypeSafeJevClient(
        Settings(
            typesafe_api_key="test-only",
            typesafe_api_url="https://example.invalid/v1/systemone",
        ),
        transport=transport,
    )


@pytest.mark.asyncio
async def test_jev_parses_official_contract_fixture_and_sends_atomic_questions() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert set(payload) == {"model", "state", "questions"}
        assert payload["model"] == "jev-latest"
        assert payload["questions"]["needs_web_research"]["type"] == "noul"
        assert payload["questions"]["needs_repository_files"]["type"] == "noul"
        assert "needs_web_or_files" not in payload["questions"]
        assert payload["questions"]["quality"]["criteria"] == client().QUALITY_LEVELS
        assert request.headers["Authorization"] == "Bearer test-only"
        return httpx.Response(200, json=fixture_response())

    evaluation = await client(httpx.MockTransport(handler)).evaluate({"brief": "test"})

    assert evaluation.model == "jev-1.13.0"
    assert evaluation.usage.input_tokens == 412
    assert evaluation.decision.next_worker is Worker.WRITE
    assert evaluation.decision.allow_action is ActionDecision.ASK
    assert evaluation.decision.needs_web_research == 0.1
    assert evaluation.decision.needs_repository_files == 0.9
    assert evaluation.decision.quality_score == pytest.approx(2.38)
    assert evaluation.decision.quality_normalized == pytest.approx(2.38 / 3)
    assert evaluation.decision.quality_legend["3"] == "ready for implementation"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda value: value["answers"]["needs_web_research"].update(noul=True),
            "numeric",
        ),
        (
            lambda value: value["answers"]["next_worker"].update(type="noul"),
            "wrong type",
        ),
        (
            lambda value: value["answers"]["next_worker"]["probabilities"].update(
                write=0.5
            ),
            "sum to 1",
        ),
        (
            lambda value: value["answers"]["quality"]["legend"].update(
                {"3": "invented"}
            ),
            "requested rubric",
        ),
        (
            lambda value: value["answers"]["quality"].update(score=1.5),
            "probability-weighted rubric",
        ),
        (
            lambda value: value["answers"].update(extra={"type": "noul", "noul": 0.5}),
            "answer set",
        ),
    ],
)
def test_jev_rejects_malformed_contract_fields(
    mutation: Any, message: str
) -> None:
    payload = deepcopy(fixture_response())
    mutation(payload)
    with pytest.raises(JevEvaluationError, match=message):
        client()._parse(payload)


def test_jev_accepts_provider_rounded_score_distribution() -> None:
    payload = fixture_response()
    payload["answers"]["quality"].update(
        score=0.31,
        probabilities={"0": 0.76, "1": 0.18, "2": 0.03, "3": 0.03},
        confidence=0.69,
    )

    evaluation = client()._parse(payload)

    assert evaluation.decision.quality_score == pytest.approx(0.31)
    assert evaluation.decision.quality_normalized == pytest.approx(0.31 / 3)


@pytest.mark.asyncio
async def test_jev_sanitizes_http_errors_without_exposing_credentials_or_body() -> None:
    secret = "non-production-test-secret"

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": secret})

    protected_client = TypeSafeJevClient(
        Settings(
            typesafe_api_key=secret,
            typesafe_api_url="https://example.invalid/v1/systemone",
        ),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(JevEvaluationError) as captured:
        await protected_client.evaluate({})
    assert secret not in str(captured.value)
    assert "401" in str(captured.value)


@pytest.mark.asyncio
async def test_jev_timeout_fails_closed_with_sanitized_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("upstream detail", request=request)

    with pytest.raises(JevEvaluationError, match="timed out"):
        await client(httpx.MockTransport(handler)).evaluate({})


@pytest.mark.parametrize(
    "url",
    [
        "http://api.typesafe.ai/v1/systemone",
        "https://user:pass@example.invalid/v1/systemone",
        "https://example.invalid/v1/systemone?key=secret",
    ],
)
def test_jev_rejects_unsafe_endpoint_configuration(url: str) -> None:
    with pytest.raises(ValueError, match="TYPESAFE_API_URL"):
        TypeSafeJevClient(Settings(typesafe_api_key="test-only", typesafe_api_url=url))
