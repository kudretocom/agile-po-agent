"""AutoGen structured-output and model compatibility checks without network calls."""

from types import SimpleNamespace

import pytest

from agile_po_agent.autogen_agent import AutoGenProductOwner, _extract_draft
from agile_po_agent.config import Settings
from tests.test_quality import ready_draft


def test_structured_output_extraction_accepts_model_instance_without_live_call() -> None:
    draft = ready_draft()
    extracted = _extract_draft([SimpleNamespace(content=draft)])
    assert extracted == draft


def test_structured_output_extraction_accepts_json_without_live_call() -> None:
    draft = ready_draft()
    extracted = _extract_draft([SimpleNamespace(content=draft.model_dump_json())])
    assert extracted == draft


def test_structured_output_extraction_rejects_missing_output() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        _extract_draft([SimpleNamespace(content="not a task")])


@pytest.mark.asyncio
async def test_gpt_6_sol_client_has_explicit_capabilities() -> None:
    owner = AutoGenProductOwner(
        Settings(openai_api_key="test-only", openai_cheap_model="gpt-6-sol")
    )
    client = owner._model_client()
    try:
        assert client.model_info["structured_output"] is True
        assert client.model_info["family"] == "unknown"
    finally:
        await client.close()
