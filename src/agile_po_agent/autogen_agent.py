"""AutoGen-backed product-owner drafting service."""

import json
from collections.abc import Sequence

from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

from agile_po_agent.config import Settings
from agile_po_agent.models import JiraTaskDraft, ProductBrief
from agile_po_agent.prompts import PO_SYSTEM_PROMPT, draft_task_prompt, revise_task_prompt


class AutoGenProductOwner:
    """Use a fresh bounded AssistantAgent session for each generation call."""

    def __init__(self, settings: Settings) -> None:
        api_key = settings.openai_api_key
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for AutoGen generation")
        self.settings = settings
        self._api_key = api_key

    async def draft(self, brief: ProductBrief) -> JiraTaskDraft:
        return await self._run(draft_task_prompt(brief.model_dump_json(indent=2)))

    async def revise(self, draft: JiraTaskDraft, failures: list[str]) -> JiraTaskDraft:
        return await self._run(revise_task_prompt(draft.model_dump_json(indent=2), failures))

    async def _run(self, task: str) -> JiraTaskDraft:
        client = OpenAIChatCompletionClient(
            model=self.settings.openai_cheap_model,
            api_key=self._api_key,
        )
        agent = AssistantAgent(
            name="agile_product_owner",
            description="Creates small, testable, outcome-oriented Agile Jira work items.",
            model_client=client,
            system_message=PO_SYSTEM_PROMPT,
            output_content_type=JiraTaskDraft,
            max_tool_iterations=1,
        )
        try:
            result = await agent.run(task=task)
            return _extract_draft(result.messages)
        finally:
            await client.close()


def _extract_draft(messages: Sequence[object]) -> JiraTaskDraft:
    if not messages:
        raise ValueError("AutoGen returned no messages")
    for message in reversed(messages):
        content = getattr(message, "content", None)
        if isinstance(content, JiraTaskDraft):
            return content
        if isinstance(content, str):
            try:
                return JiraTaskDraft.model_validate_json(content)
            except (ValueError, json.JSONDecodeError):
                continue
        if isinstance(content, dict):
            return JiraTaskDraft.model_validate(content)
    raise ValueError("AutoGen returned an unsupported structured-output shape")
