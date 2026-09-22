import httpx
import pytest

from agile_po_agent.config import Settings
from agile_po_agent.jev import TypeSafeJevClient
from agile_po_agent.models import ActionDecision, Worker


@pytest.mark.asyncio
async def test_jev_parses_atomic_decisions() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = __import__("json").loads(request.content)
        assert "needs_web_research" in payload["questions"]
        assert "needs_repository_files" in payload["questions"]
        assert "needs_web_or_files" not in payload["questions"]
        return httpx.Response(
            200,
            json={
                "answers": {
                    "next_worker": {"choice": "write"},
                    "needs_web_research": {"noul": 0.1},
                    "needs_repository_files": {"noul": 0.9},
                    "brief_sufficient": {"noul": 0.85},
                    "ready_to_ship": {"noul": 0.81},
                    "quality": {"score": 2.4},
                    "allow_action": {"choice": "ask"},
                }
            },
        )

    settings = Settings(
        typesafe_api_key="test-only",
        typesafe_api_url="https://example.invalid/systemone",
    )
    client = TypeSafeJevClient(settings, transport=httpx.MockTransport(handler))
    decision = await client.evaluate({"brief": "test"})

    assert decision.next_worker is Worker.WRITE
    assert decision.allow_action is ActionDecision.ASK
    assert decision.needs_web_research == 0.1
    assert decision.needs_repository_files == 0.9
    assert decision.quality_normalized == pytest.approx(0.8)


@pytest.mark.asyncio
async def test_jev_rejects_boolean_noul() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "answers": {
                    "next_worker": {"choice": "finish"},
                    "needs_web_research": {"noul": True},
                    "needs_repository_files": {"noul": 0.0},
                    "brief_sufficient": {"noul": 1.0},
                    "ready_to_ship": {"noul": 1.0},
                    "quality": {"score": 3.0},
                    "allow_action": {"choice": "allow"},
                }
            },
        )

    client = TypeSafeJevClient(
        Settings(typesafe_api_key="test-only", typesafe_api_url="https://example.invalid"),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ValueError, match="numeric"):
        await client.evaluate({})

