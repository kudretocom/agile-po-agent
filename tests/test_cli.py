from typer.testing import CliRunner

from agile_po_agent.cli import app
from tests.test_quality import ready_draft


def test_evaluate_failed_readiness_returns_nonzero_and_named_failures(tmp_path) -> None:
    draft = ready_draft().model_copy(update={"summary": "Too vague"})
    path = tmp_path / "draft.json"
    path.write_text(draft.model_dump_json())

    result = CliRunner().invoke(app, ["evaluate", str(path)])

    assert result.exit_code == 2
    assert "actionable_summary" in result.stdout
