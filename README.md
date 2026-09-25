# Agile PO Agent

Agile PO Agent turns a rough product brief into a clear, testable Jira work item. It combines:

- **Microsoft AutoGen AgentChat** for product reasoning and structured drafting;
- a **TypeSafe Jev client** for small, auditable routing and readiness decisions;
- **deterministic quality gates** for Definition of Ready and test-based shipping decisions;
- **a guarded Jira adapter** that is dry-run by default.

The project is intentionally opinionated: a language model may propose work, but application code owns thresholds, validation, side effects, retries, and termination.

## Status

The bounded PO flow now validates and uses Jev decisions before AutoGen drafting or revision. Installation and automated tests remain fully offline through deterministic HTTP fixtures. Jira writes still require explicit publish confirmation or a separate, authorized connector workflow.

Wise's read-only four-state Assess core is implemented separately from the drafting CLI. It binds Jira reads to site/install context, checks versioned claim evidence, uses narrow TypeSafe Jev judgments, and emits `wise.assessment.v1` without Jira writes. See [the Assess contract](docs/wise-assess.md). Rovo deployment and source collectors are not yet included.

## Architecture

```text
Product brief
    ↓
Jev atomic decision gate → explicit web/repository evidence requirements
    ↓
AutoGen ProductOwnerAgent → structured JiraTaskDraft
    ↓
Jev-guided revision loop + deterministic readiness (bounded by MAX_STEPS)
    ↓
Human review / guarded Jira publish
```

AutoGen is installed inside this repository's virtual environment. Shared credentials remain outside the repository and are injected at runtime. Jev is not an AutoGen agent and never owns control flow or side effects. The direct wire contract is documented in [docs/jev-contract.md](docs/jev-contract.md).

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

If Jev reports that external or repository evidence is required, collect it through an approved bounded process and explicitly pass `--web-research-complete` and/or `--repository-files-loaded`. Uncertain Noul values stop the run for review.

An approved non-production Jev credential can be checked with one synthetic request:

```sh
TYPESAFE_ENVIRONMENT=non-production \
  .venv/bin/agile-po jev-smoke --confirm-non-production
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
- Model responses are schema-validated; Jev's official Choice, Score, Noul, usage, and envelope shapes are covered by deterministic fixtures.
- Malformed decision responses fail closed.

See [docs/architecture.md](docs/architecture.md) and [SECURITY.md](SECURITY.md).

## Wise product direction

The proposed Jira agent first-release contract, decision rules, and example assessment output are in [docs/wise-product-contract.md](docs/wise-product-contract.md). This is a product specification under review, not a deployed integration.

## License

MIT
