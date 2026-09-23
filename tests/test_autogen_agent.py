"""OpenAI model compatibility checks without network calls."""

import pytest

from agile_po_agent.autogen_agent import AutoGenProductOwner
from agile_po_agent.config import Settings


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
