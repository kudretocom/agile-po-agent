"""Command-line interface with safe defaults."""

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

from agile_po_agent.autogen_agent import AutoGenProductOwner
from agile_po_agent.config import Settings
from agile_po_agent.jira import JiraClient
from agile_po_agent.models import JiraTaskDraft, ProductBrief
from agile_po_agent.orchestrator import ProductOwnerOrchestrator
from agile_po_agent.quality import DefinitionOfReadyEvaluator

app = typer.Typer(no_args_is_help=True, help="Draft excellent, evidence-gated Jira work items.")
console = Console()


@app.command()
def draft(
    brief_path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path, typer.Option("--output", "-o")],
) -> None:
    """Generate and evaluate a Jira task draft using AutoGen."""

    brief = ProductBrief.model_validate_json(brief_path.read_text())
    settings = Settings()
    owner = AutoGenProductOwner(settings)
    orchestrator = ProductOwnerOrchestrator(settings, owner)
    outcome = asyncio.run(orchestrator.create_draft(brief))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(outcome.draft.model_dump_json(indent=2) + "\n")
    console.print(
        Panel(
            outcome.draft.to_markdown(),
            title=f"{outcome.draft.summary} — readiness {outcome.readiness.score:.0%}",
        )
    )
    console.print(f"Saved {output}; terminal reason: {outcome.terminal_reason}")


@app.command()
def evaluate(draft_path: Annotated[Path, typer.Argument(exists=True, readable=True)]) -> None:
    """Run the deterministic Definition of Ready evaluation."""

    draft_value = JiraTaskDraft.model_validate_json(draft_path.read_text())
    result = DefinitionOfReadyEvaluator(Settings().ready_threshold).evaluate(draft_value)
    console.print_json(result.model_dump_json())
    if not result.passed:
        raise typer.Exit(code=2)


@app.command()
def publish(
    draft_path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    issue_key: Annotated[str | None, typer.Option()] = None,
    project_key: Annotated[str | None, typer.Option()] = None,
    confirm: Annotated[bool, typer.Option(help="Perform the Jira write.")] = False,
) -> None:
    """Preview or explicitly publish a validated draft to Jira."""

    if bool(issue_key) == bool(project_key):
        raise typer.BadParameter("provide exactly one of --issue-key or --project-key")
    draft_value = JiraTaskDraft.model_validate_json(draft_path.read_text())
    readiness = DefinitionOfReadyEvaluator(Settings().ready_threshold).evaluate(draft_value)
    if not readiness.passed:
        raise typer.BadParameter("draft does not pass Definition of Ready")
    client = JiraClient(Settings())
    if not confirm:
        console.print_json(json.dumps(client.preview(draft_value, issue_key=issue_key)))
        console.print("Dry-run only. Re-run with --confirm after human review.")
        return
    if issue_key:
        client.update(issue_key, draft_value, confirm=True)
        console.print(f"Updated {issue_key}")
    else:
        assert project_key
        created_key = client.create(project_key, draft_value, confirm=True)
        console.print(f"Created {created_key}")


if __name__ == "__main__":
    app()

