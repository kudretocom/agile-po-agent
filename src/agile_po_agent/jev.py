"""TypeSafe Jev decision gateway with strict response validation."""

import math
from time import perf_counter
from typing import Any, TypeVar
from urllib.parse import urlsplit

import httpx

from agile_po_agent.config import Settings
from agile_po_agent.models import (
    ActionDecision,
    JevDecision,
    JevEvaluation,
    JevUsage,
    Worker,
)
from agile_po_agent.quality import normalize_score

EnumValue = TypeVar("EnumValue", Worker, ActionDecision)


class JevEvaluationError(RuntimeError):
    """A sanitized, fail-closed Jev failure safe to show to operators."""


class TypeSafeJevClient:
    """Ask atomic questions; application code interprets and thresholds answers."""

    QUALITY_LEVELS = [
        "not actionable",
        "major refinement required",
        "minor refinement required",
        "ready for implementation",
    ]
    QUESTION_NAMES = {
        "next_worker",
        "needs_web_research",
        "needs_repository_files",
        "brief_sufficient",
        "ready_to_ship",
        "quality",
        "allow_action",
    }
    PROBABILITY_SUM_TOLERANCE = 0.001

    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        api_key = settings.typesafe_api_key
        if not api_key:
            raise ValueError("TYPESAFE_API_KEY is required")
        self._validate_url(settings.typesafe_api_url)
        self.settings = settings
        self._api_key = api_key
        self._api_url = settings.typesafe_api_url
        self._transport = transport

    async def evaluate(self, state: dict[str, Any]) -> JevEvaluation:
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
                    "criteria": {
                        "true": "Current external sources are required.",
                        "false": "The supplied evidence is sufficient without current web sources.",
                    },
                },
                "needs_repository_files": {
                    "type": "noul",
                    "instructions": "Does this task require repository-file evidence?",
                    "criteria": {
                        "true": "Repository files must be inspected.",
                        "false": "Repository-file evidence is not required.",
                    },
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
        started = perf_counter()
        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                timeout=self.settings.typesafe_timeout_seconds,
            ) as client:
                response = await client.post(self._api_url, json=payload, headers=headers)
            if response.status_code < 200 or response.status_code >= 300:
                raise JevEvaluationError(f"Jev request failed with HTTP {response.status_code}")
            if len(response.content) > self.settings.typesafe_max_response_bytes:
                raise JevEvaluationError("Jev response exceeded the configured size limit")
            try:
                response_payload = response.json()
            except ValueError as error:
                raise JevEvaluationError("Jev response was not valid JSON") from error
            if not isinstance(response_payload, dict):
                raise JevEvaluationError("Jev response envelope must be an object")
            return self._parse(response_payload, (perf_counter() - started) * 1000)
        except JevEvaluationError:
            raise
        except httpx.TimeoutException as error:
            raise JevEvaluationError("Jev request timed out") from error
        except httpx.HTTPError as error:
            raise JevEvaluationError("Jev request failed") from error

    def _parse(self, payload: dict[str, Any], latency_ms: float = 0.0) -> JevEvaluation:
        if set(payload) != {"model", "answers", "usage"}:
            raise JevEvaluationError("Jev response envelope has unexpected fields")
        model = self._text(payload, "model")
        answers = payload.get("answers")
        if not isinstance(answers, dict):
            raise JevEvaluationError("Jev response is missing an answers object")
        answer_names = set(answers)
        if answer_names != self.QUESTION_NAMES:
            raise JevEvaluationError("Jev response answer set does not match the request")

        next_worker_answer = self._typed_answer(answers, "next_worker", "choice")
        next_worker, next_worker_probabilities, next_worker_confidence = self._choice(
            next_worker_answer, Worker
        )
        action_answer = self._typed_answer(answers, "allow_action", "choice")
        allow_action, allow_action_probabilities, allow_action_confidence = self._choice(
            action_answer, ActionDecision
        )

        quality_answer = self._typed_answer(answers, "quality", "score")
        raw_quality = self._number(
            quality_answer,
            "score",
            minimum=0.0,
            maximum=float(len(self.QUALITY_LEVELS) - 1),
        )
        quality_legend = self._quality_legend(quality_answer)
        quality_probabilities = self._probabilities(
            quality_answer,
            "probabilities",
            expected_keys=set(quality_legend),
        )
        expected_quality = sum(
            int(level) * probability
            for level, probability in quality_probabilities.items()
        )
        if not math.isclose(
            raw_quality,
            expected_quality,
            rel_tol=0.0,
            abs_tol=self.PROBABILITY_SUM_TOLERANCE,
        ):
            raise JevEvaluationError(
                "Jev score does not match its probability-weighted rubric"
            )
        quality_confidence = self._number(
            quality_answer, "confidence", minimum=0.0, maximum=1.0
        )

        usage_value = payload.get("usage")
        if not isinstance(usage_value, dict):
            raise JevEvaluationError("Jev response is missing usage")
        usage = JevUsage(
            input_tokens=self._integer(usage_value, "input_tokens"),
            output_tokens=self._integer(usage_value, "output_tokens"),
        )
        return JevEvaluation(
            model=model,
            usage=usage,
            latency_ms=latency_ms,
            decision=JevDecision(
                next_worker=next_worker,
                next_worker_probabilities=next_worker_probabilities,
                next_worker_confidence=next_worker_confidence,
                needs_web_research=self._noul(answers, "needs_web_research"),
                needs_repository_files=self._noul(answers, "needs_repository_files"),
                brief_sufficient=self._noul(answers, "brief_sufficient"),
                ready_to_ship=self._noul(answers, "ready_to_ship"),
                quality_score=raw_quality,
                quality_normalized=normalize_score(raw_quality, len(self.QUALITY_LEVELS)),
                quality_legend=quality_legend,
                quality_probabilities=quality_probabilities,
                quality_confidence=quality_confidence,
                allow_action=allow_action,
                allow_action_probabilities=allow_action_probabilities,
                allow_action_confidence=allow_action_confidence,
            ),
        )

    def _noul(self, answers: dict[str, Any], name: str) -> float:
        answer = self._typed_answer(answers, name, "noul")
        return self._number(answer, "noul", minimum=0.0, maximum=1.0)

    def _choice(
        self,
        answer: dict[str, Any],
        enum_type: type[EnumValue],
    ) -> tuple[EnumValue, dict[EnumValue, float], float]:
        raw_choice = self._text(answer, "choice")
        try:
            choice = enum_type(raw_choice)
        except ValueError as error:
            raise JevEvaluationError("Jev choice is outside the requested criteria") from error
        raw_probabilities = self._probabilities(
            answer,
            "probabilities",
            expected_keys={item.value for item in enum_type},
        )
        probabilities = {enum_type(key): value for key, value in raw_probabilities.items()}
        if probabilities[choice] < max(probabilities.values()):
            raise JevEvaluationError("Jev choice is not a highest-probability option")
        confidence = self._number(answer, "confidence", minimum=0.0, maximum=1.0)
        return choice, probabilities, confidence

    def _quality_legend(self, answer: dict[str, Any]) -> dict[str, str]:
        legend = answer.get("legend")
        if not isinstance(legend, dict):
            raise JevEvaluationError("Jev score legend must be an object")
        expected = {str(index): value for index, value in enumerate(self.QUALITY_LEVELS)}
        if legend != expected:
            raise JevEvaluationError("Jev score legend does not match the requested rubric")
        return expected

    def _probabilities(
        self,
        answer: dict[str, Any],
        field: str,
        *,
        expected_keys: set[str],
    ) -> dict[str, float]:
        value = answer.get(field)
        if not isinstance(value, dict) or set(value) != expected_keys:
            raise JevEvaluationError(f"Jev field {field!r} has unexpected keys")
        result = {key: self._probability_value(item, field) for key, item in value.items()}
        if not math.isclose(
            sum(result.values()),
            1.0,
            rel_tol=0.0,
            abs_tol=self.PROBABILITY_SUM_TOLERANCE,
        ):
            raise JevEvaluationError(f"Jev field {field!r} must sum to 1")
        return result

    @staticmethod
    def _typed_answer(
        answers: dict[str, Any], name: str, expected_type: str
    ) -> dict[str, Any]:
        answer = answers.get(name)
        if not isinstance(answer, dict):
            raise JevEvaluationError(f"Jev answer {name!r} is missing or malformed")
        if answer.get("type") != expected_type:
            raise JevEvaluationError(f"Jev answer {name!r} has the wrong type")
        return answer

    @staticmethod
    def _number(
        answer: dict[str, Any],
        field: str,
        *,
        minimum: float | None = None,
        maximum: float | None = None,
    ) -> float:
        value = answer.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise JevEvaluationError(f"Jev field {field!r} must be numeric")
        result = float(value)
        if not math.isfinite(result):
            raise JevEvaluationError(f"Jev field {field!r} must be finite")
        if minimum is not None and result < minimum:
            raise JevEvaluationError(f"Jev field {field!r} is below its allowed range")
        if maximum is not None and result > maximum:
            raise JevEvaluationError(f"Jev field {field!r} is above its allowed range")
        return result

    @classmethod
    def _probability_value(cls, value: Any, field: str) -> float:
        return cls._number({field: value}, field, minimum=0.0, maximum=1.0)

    @staticmethod
    def _integer(value: dict[str, Any], field: str) -> int:
        item = value.get(field)
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            raise JevEvaluationError(f"Jev usage field {field!r} must be a non-negative integer")
        return item

    @staticmethod
    def _text(value: dict[str, Any], field: str) -> str:
        item = value.get(field)
        if not isinstance(item, str) or not item:
            raise JevEvaluationError(f"Jev field {field!r} must be non-empty text")
        return item

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("TYPESAFE_API_URL must be an absolute HTTPS URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("TYPESAFE_API_URL must not contain credentials, query, or fragment")
