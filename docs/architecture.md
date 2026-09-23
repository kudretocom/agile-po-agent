# Architecture

## Boundaries

The system has four deliberately separate responsibilities:

1. `AutoGenProductOwner` converts an incomplete brief into a validated `JiraTaskDraft` and revises that draft from explicit feedback.
2. `DefinitionOfReadyEvaluator` and `ShippingGate` apply deterministic product and delivery rules.
3. `TypeSafeJevClient` asks atomic Choice, Score, and Noul questions. It never produces prose and never owns side effects.
4. `JiraClient` renders and publishes a validated draft. It is dry-run unless the caller explicitly confirms the write.

The `ProductOwnerOrchestrator` composes Jev routing, AutoGen drafting, and the Definition of Ready evaluator. Jira remains a separate guarded adapter and is never reachable from a Jev decision.

## Jev decisions

The mock-tested Jev client defines separate questions for web and repository context:

- `needs_web_research`: Noul probability;
- `needs_repository_files`: Noul probability;
- `brief_sufficient`: Noul probability;
- `ready_to_ship`: Noul probability;
- `next_worker`: Choice;
- `allow_action`: Choice;
- `quality`: Score normalized by application code.

A value near `0.5` is uncertainty. The application never silently casts a Noul to a boolean.

The orchestrator records a secrets-free trace with the resolved model, token usage, latency, typed decision, and code-owned Noul interpretations. Required evidence must be confirmed by the caller; Jev cannot claim that web or repository evidence was actually collected.

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

Jev may recommend readiness; it cannot waive failed tests or authorize a Jira write. An `allow` answer is necessary but never sufficient for a side effect, and low-confidence permission fails closed.

## Bounded routing

Each decision step asks Jev for one `next_worker` Choice and the independent Noul/Score questions. Application code validates the full official response contract before using any answer. `write` and `revise` call the narrow AutoGen service, `finish` must pass deterministic readiness and quality checks, and `research` / `escalate` stop for an external bounded worker or human. `MAX_STEPS` caps both decision and generation progress.

See [jev-contract.md](jev-contract.md) for the verified wire contract and non-production smoke procedure.

## AutoGen lifecycle

AutoGen runs from the repository's `.venv`. Each issue receives a fresh `AssistantAgent` session so that context does not leak across customers or Jira issues. The orchestrator closes the model client after each run.

The first release uses one PO agent rather than a group chat. Future agents must be narrow, tool-limited, and selected by the orchestrator rather than by an unbounded conversation.
