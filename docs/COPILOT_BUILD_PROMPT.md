# GitHub Copilot Build Prompt

You are implementing `agile-po-agent`, a public-ready Python project that produces exceptional Agile Jira work items.

## Technical baseline

- Use Python 3.12 locally and support Python 3.10+.
- Use the stable Microsoft AutoGen AgentChat packages pinned in `pyproject.toml`.
- Follow the stable AutoGen quickstart, not the unstable `dev/main` documentation.
- Instantiate `autogen_agentchat.agents.AssistantAgent` with `autogen_ext.models.openai.OpenAIChatCompletionClient`.
- Return validated `JiraTaskDraft` structured output.
- Create a fresh agent context for each Jira issue and close the model client after the run.
- Do not introduce `RoundRobinGroupChat`, Swarm, or another unbounded agent loop in the MVP.

## Responsibility split

- AutoGen writes or revises product-task prose and structured drafts.
- Jev evaluates atomic decisions only; it never writes prose.
- Python application code owns loops, thresholds, normalization, caching, retries, termination, test gates, logging, and side effects.
- Jira writes are performed only by the Jira adapter, are dry-run by default, and require explicit confirmation.
- An AI `allow_action=allow` result never replaces human authorization.

## Jev contract

Keep these questions atomic:

- `needs_web_research`: Noul probability from `0.0` to `1.0`;
- `needs_repository_files`: Noul probability from `0.0` to `1.0`;
- `brief_sufficient`: Noul probability from `0.0` to `1.0`;
- `ready_to_ship`: Noul probability from `0.0` to `1.0`;
- `next_worker`: Choice from `research | write | revise | finish | escalate`;
- `allow_action`: Choice from `allow | ask | deny`;
- `quality`: Score whose raw rubric/legend is retained and whose value is normalized by application code.

Validate the raw response envelope and fail closed. Never clamp an out-of-range score or silently coerce a malformed answer.

## Agile task quality

Every generated work item must contain:

- a concise action-oriented summary;
- user/business context and the problem being solved;
- a measurable desired outcome;
- explicit scope and non-goals;
- Given/When/Then acceptance criteria with observable evidence;
- a test plan;
- dependencies, risks, rollout notes, success metrics, and open questions;
- no invented technical facts, project keys, field IDs, or estimates.

Prefer a small vertical slice over a horizontal technical layer. Story points and priority require team or user input.

## Definition of Done

Do not mark a task ready to ship unless all gates pass:

```text
ready_to_ship >= READY_THRESHOLD
quality_normalized >= QUALITY_THRESHOLD
tests_passed is true
lint_passed is true
typecheck_passed is true
unresolved_blockers == 0
```

## Security and public-repository rules

- Never add real secrets, secret-manager references, Jira metadata, customer data, or sensitive local paths.
- Keep `.env.example` inert.
- Do not resolve or print credentials.
- Do not publish to Jira, GitHub, or a package registry unless explicitly requested.
- Preserve dry-run behavior and approval gates.

## First issue

Implement the smallest vertical slice: load a local `ProductBrief`, use the AutoGen PO agent to produce a schema-valid `JiraTaskDraft`, evaluate its deterministic Definition of Ready, and render Jira-ready Markdown/JSON without writing to Jira.

Before finishing, run:

```sh
.venv/bin/ruff check .
.venv/bin/mypy
.venv/bin/pytest
```

Report changed files, verification results, and unresolved risks.

