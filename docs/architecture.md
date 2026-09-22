# Architecture

## Boundaries

The system has four deliberately separate responsibilities:

1. `AutoGenProductOwner` converts an incomplete brief into a validated `JiraTaskDraft` and revises that draft from explicit feedback.
2. `DefinitionOfReadyEvaluator` and `ShippingGate` apply deterministic product and delivery rules.
3. `TypeSafeJevClient` asks atomic Choice, Score, and Noul questions. It never produces prose and never owns side effects.
4. `JiraClient` renders and publishes a validated draft. It is dry-run unless the caller explicitly confirms the write.

The `ProductOwnerOrchestrator` owns the bounded loop and composes these parts.

## Jev decisions

The MVP uses separate questions for web and repository context:

- `needs_web_research`: Noul probability;
- `needs_repository_files`: Noul probability;
- `brief_sufficient`: Noul probability;
- `ready_to_ship`: Noul probability;
- `next_worker`: Choice;
- `allow_action`: Choice;
- `quality`: Score normalized by application code.

A value near `0.5` is uncertainty. The application never silently casts a Noul to a boolean.

## Test-based shipping gate

Shipping requires all of the following:

```text
ready_to_ship >= READY_THRESHOLD
quality_normalized >= QUALITY_THRESHOLD
tests_passed
lint_passed
typecheck_passed
unresolved_blockers == 0
human authorization when a side effect is requested
```

Jev may recommend readiness; it cannot waive failed tests or authorize a Jira write.

## AutoGen lifecycle

AutoGen runs from the repository's `.venv`. Each issue receives a fresh `AssistantAgent` session so that context does not leak across customers or Jira issues. The orchestrator closes the model client after each run.

The first release uses one PO agent rather than a group chat. Future agents must be narrow, tool-limited, and selected by the orchestrator rather than by an unbounded conversation.

