"""TypeSafe Jev decision gateway with strict response validation."""

from typing import Any

import httpx

from agile_po_agent.config import Settings
from agile_po_agent.models import ActionDecision, JevDecision, Worker
from agile_po_agent.quality import normalize_score


class TypeSafeJevClient:
    """Ask atomic questions; application code interprets and thresholds answers."""

    QUALITY_LEVELS = [
        "not actionable",
        "major refinement required",
        "minor refinement required",
        "ready for implementation",
    ]

    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        api_key = settings.typesafe_api_key
        api_url = settings.typesafe_api_url
        if not api_key or not api_url:
            raise ValueError("TYPESAFE_API_KEY and TYPESAFE_API_URL are required")
        self.settings = settings
        self._api_key = api_key
        self._api_url = api_url
        self._transport = transport

    async def evaluate(self, state: dict[str, Any]) -> JevDecision:
        payload = {
            "model": self.settings.typesafe_model,
            "state": state,
            "questions": {
                "next_worker": {
                    "type": "choice",
                    "instructions": "Which bounded worker should run next?",
                    "criteria": {worker.value: None for worker in Worker},
                },
                "needs_web_research": {
                    "type": "noul",
                    "instructions": "Does this task require current external web research?",
                },
                "needs_repository_files": {
                    "type": "noul",
                    "instructions": "Does this task require repository-file evidence?",
                },
                "brief_sufficient": {
                    "type": "noul",
                    "instructions": "Is the brief sufficient to draft a testable work item?",
                },
                "ready_to_ship": {
                    "type": "noul",
                    "instructions": "Is this work item ready for its next approved side effect?",
                },
                "quality": {
                    "type": "score",
                    "instructions": "Rate the work item's implementation readiness.",
                    "criteria": self.QUALITY_LEVELS,
                },
                "allow_action": {
                    "type": "choice",
                    "instructions": "Should the proposed side effect proceed?",
                    "criteria": {"allow": None, "ask": None, "deny": None},
                },
            },
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(transport=self._transport, timeout=30.0) as client:
            response = await client.post(
                self._api_url,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
        return self._parse(response.json())

    def _parse(self, payload: dict[str, Any]) -> JevDecision:
        answers = payload.get("answers")
        if not isinstance(answers, dict):
            raise ValueError("Jev response is missing an answers object")

        quality_answer = self._answer(answers, "quality")
        raw_quality = self._number(quality_answer, "score")
        return JevDecision(
            next_worker=Worker(self._text(self._answer(answers, "next_worker"), "choice")),
            needs_web_research=self._number(
                self._answer(answers, "needs_web_research"), "noul"
            ),
            needs_repository_files=self._number(
                self._answer(answers, "needs_repository_files"), "noul"
            ),
            brief_sufficient=self._number(self._answer(answers, "brief_sufficient"), "noul"),
            ready_to_ship=self._number(self._answer(answers, "ready_to_ship"), "noul"),
            quality_normalized=normalize_score(raw_quality, len(self.QUALITY_LEVELS)),
            allow_action=ActionDecision(
                self._text(self._answer(answers, "allow_action"), "choice")
            ),
        )

    @staticmethod
    def _answer(answers: dict[str, Any], name: str) -> dict[str, Any]:
        answer = answers.get(name)
        if not isinstance(answer, dict):
            raise ValueError(f"Jev answer {name!r} is missing or malformed")
        return answer

    @staticmethod
    def _number(answer: dict[str, Any], field: str) -> float:
        value = answer.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Jev field {field!r} must be numeric")
        return float(value)

    @staticmethod
    def _text(answer: dict[str, Any], field: str) -> str:
        value = answer.get(field)
        if not isinstance(value, str):
            raise ValueError(f"Jev field {field!r} must be text")
        return value
