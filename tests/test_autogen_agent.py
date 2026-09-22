from types import SimpleNamespace

import pytest

from agile_po_agent.autogen_agent import _extract_draft
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
