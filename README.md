# Agile PO Agent

Agile PO Agent turns a rough product brief into a clear, testable Jira work item. It combines:

- **Microsoft AutoGen AgentChat** for product reasoning and structured drafting;
- **TypeSafe Jev** for small, auditable routing and readiness decisions;
- **deterministic quality gates** for Definition of Ready and test-based shipping decisions;
- **a guarded Jira adapter** that is dry-run by default.

The project is intentionally opinionated: a language model may propose work, but application code owns thresholds, validation, side effects, retries, and termination.

## Status

This repository contains the first public-ready MVP scaffold. It does not publish to Jira or call a model during installation or tests. Live OpenAI, Jev, and Jira operations require explicit configuration and an explicit publish confirmation.

## Architecture

```text
Product brief
    ↓
AutoGen ProductOwnerAgent → structured JiraTaskDraft
    ↓
Deterministic Definition of Ready evaluation
    ↓
Jev atomic decisions (route, research needs, readiness, action permission)
    ↓
Revision loop (bounded by MAX_STEPS)
    ↓
Human review / guarded Jira publish
```

AutoGen is installed inside this repository's virtual environment. Shared credentials remain outside the repository and are injected at runtime. Jev is not an AutoGen agent; it is a separate decision gateway called by the Python orchestrator.

## Quickstart

Python 3.10 or later is required. Python 3.12 is recommended.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/agile-po --help
.venv/bin/pytest
```

Generate a draft after providing credentials through your approved secret-injection mechanism:

```sh
.venv/bin/agile-po draft examples/first-issue-brief.json --output drafts/scrum-1.json
```

Evaluate a previously generated draft without calling a model:

```sh
.venv/bin/agile-po evaluate drafts/scrum-1.json
```

Preview a Jira update without sending it:

```sh
.venv/bin/agile-po publish drafts/scrum-1.json --issue-key SCRUM-1
```

Publishing requires both `--confirm` and valid Jira credentials. The command refuses ambiguous create/update requests.

## Product principles

- Start with the user problem and desired outcome, not a predetermined solution.
- Prefer thin vertical slices that produce measurable value.
- Make acceptance criteria observable and testable.
- State scope, non-goals, dependencies, risks, and open questions explicitly.
- Separate Definition of Ready from Definition of Done.
- Never treat AI confidence as authorization.
- Keep uncertain work in human review.
- Optimize for inspectability over autonomous complexity.

## Why AutoGen without group chat?

The MVP calls one `AssistantAgent` directly and uses bounded revision turns. It does not use an open-ended round-robin team. This makes token use, termination, and ownership predictable. Specialized research and engineering agents can be added later behind the same orchestrator contract.

## Security

- No real credential belongs in this repository.
- `.env.example` contains names and inert values only.
- Jira publication is dry-run unless explicitly confirmed.
- Model and Jev responses are schema-validated.
- Malformed decision responses fail closed.

See [docs/architecture.md](docs/architecture.md) and [SECURITY.md](SECURITY.md).

## License

MIT

