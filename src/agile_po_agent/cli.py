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
from agile_po_agent.jev import TypeSafeJevClient
from agile_po_agent.jira import JiraClient
from agile_po_agent.models import JiraTaskDraft, ProductBrief
from agile_po_agent.orchestrator import OrchestrationContext, ProductOwnerOrchestrator
from agile_po_agent.quality import DefinitionOfReadyEvaluator

app = typer.Typer(no_args_is_help=True, help="Draft excellent, evidence-gated Jira work items.")
console = Console()


@app.command("jev-smoke")
def jev_smoke(
    confirm_non_production: Annotated[
        bool,
        typer.Option(
            help="Confirm the injected credential is approved for non-production use."
        ),
    ] = False,
) -> None:
    """Run one synthetic, secrets-free Jev decision smoke test."""

    settings = Settings()
    if settings.typesafe_environment != "non-production":
        raise typer.BadParameter(
            "TYPESAFE_ENVIRONMENT must be exactly 'non-production'"
        )
    if not confirm_non_production:
        raise typer.BadParameter("--confirm-non-production is required")
    evaluation = asyncio.run(
        TypeSafeJevClient(settings).evaluate(
            {
                "smoke_test": True,
                "task": "Draft a bounded product work item from supplied evidence.",
                "contains_customer_data": False,
                "proposed_side_effect": "none",
            }
        )
    )
    console.print_json(
        json.dumps(
            {
                "model": evaluation.model,
                "input_tokens": evaluation.usage.input_tokens,
                "output_tokens": evaluation.usage.output_tokens,
                "latency_ms": round(evaluation.latency_ms, 1),
                "next_worker": evaluation.decision.next_worker.value,
                "needs_web_research": evaluation.decision.needs_web_research,
                "needs_repository_files": evaluation.decision.needs_repository_files,
            }
        )
    )


@app.command()
def draft(
    brief_path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path, typer.Option("--output", "-o")],
    web_research_complete: Annotated[
        bool, typer.Option(help="Confirm required web evidence was collected outside Jev.")
    ] = False,
    repository_files_loaded: Annotated[
        bool, typer.Option(help="Confirm required repository evidence was loaded.")
    ] = False,
) -> None:
    """Generate and evaluate a Jira task draft using AutoGen."""

    brief = ProductBrief.model_validate_json(brief_path.read_text())
    settings = Settings()
    owner = AutoGenProductOwner(settings)
    jev = TypeSafeJevClient(settings)
    orchestrator = ProductOwnerOrchestrator(settings, owner, jev)
    outcome = asyncio.run(
        orchestrator.create_draft(
            brief,
            context=OrchestrationContext(
                web_research_complete=web_research_complete,
                repository_files_loaded=repository_files_loaded,
            ),
        )
    )
    for trace in outcome.decision_trace:
        console.print(
            "Jev decision "
            f"{trace.step}: model={trace.evaluation.model}, "
            f"input_tokens={trace.evaluation.usage.input_tokens}, "
            f"output_tokens={trace.evaluation.usage.output_tokens}, "
            f"latency_ms={trace.evaluation.latency_ms:.1f}"
        )
    if outcome.draft is None or outcome.readiness is None:
        console.print(f"No draft produced; terminal reason: {outcome.terminal_reason}")
        raise typer.Exit(code=2)
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
