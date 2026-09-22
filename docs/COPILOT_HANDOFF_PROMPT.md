# Copilot Handoff Prompt

Copy everything below this line into GitHub Copilot when handing off the project.

---

You are continuing development of the public repository:

`https://github.com/kudretocom/agile-po-agent`

The product goal is to build an exceptional open-source Product Owner agent that turns rough product intent into clear, valuable, testable Agile Jira work items.

## Current baseline

- The repository is public and `main` contains the initial MVP scaffold.
- Python 3.12 is recommended; Python 3.10+ is supported.
- Microsoft AutoGen AgentChat and `autogen-ext[openai]` are pinned to stable version `0.7.5`.
- The AutoGen runtime lives in the repository's local `.venv`; secrets remain outside the repository and are injected at runtime.
- Jira issue `SCRUM-1` is the first MVP issue. Its local source-of-truth examples are:
  - `examples/first-issue-brief.json`
  - `examples/scrum-1-proposed-task.json`
  - `examples/scrum-1-proposed-task.md`
- The initial local validation passed Ruff, mypy, and seven pytest tests.
- Do not assume the first issue is complete merely because scaffold code exists. Verify every acceptance criterion with evidence.

## Read before editing

Read these files completely:

1. `.github/copilot-instructions.md`
2. `docs/COPILOT_BUILD_PROMPT.md`
3. `docs/architecture.md`
4. `README.md`
5. `examples/scrum-1-proposed-task.md`

Follow repository instructions when they are stricter than this handoff.

## Required architecture

Keep these responsibilities separate:

1. `AutoGenProductOwner` uses one fresh, bounded AutoGen `AssistantAgent` session per work item to draft or revise structured product prose.
2. `TypeSafeJevClient` asks atomic Choice, Score, and Noul questions. Jev never writes prose and never performs side effects.
3. Deterministic Python code owns validation, thresholds, score normalization, caching, retries, termination, test gates, and authorization checks.
4. `JiraClient` is the only Jira side-effect boundary. It remains dry-run by default and requires explicit human confirmation.

Do not add an unbounded `RoundRobinGroupChat`, Swarm, or self-directed multi-agent loop to the MVP.

## AutoGen rules

- Use the stable Microsoft AutoGen documentation, not unverified `dev/main` behavior.
- Use `AssistantAgent` with `OpenAIChatCompletionClient` and validated `JiraTaskDraft` structured output.
- Close the model client after every run.
- Prevent conversation state from leaking between Jira issues.
- Keep model calls bounded by `MAX_STEPS`.
- A model may propose content; it may not authorize or directly perform a Jira write.

## Jev rules

Keep web and repository requirements as separate atomic Noul questions:

- `needs_web_research`: probability from `0.0` to `1.0`;
- `needs_repository_files`: probability from `0.0` to `1.0`;
- `brief_sufficient`: probability from `0.0` to `1.0`;
- `ready_to_ship`: probability from `0.0` to `1.0`.

Use Choice for:

- `next_worker`: `research | write | revise | finish | escalate`;
- `allow_action`: `allow | ask | deny`.

Use Score for quality, retain the raw rubric/legend, and normalize it explicitly in application code. Validate the raw response envelope. Reject boolean Nouls, missing fields, unknown choices, and scores outside their declared rubric. Never clamp or silently coerce invalid values.

## Agile product-quality contract

Every generated Jira work item must include:

- an action-oriented summary;
- user/business context and a clear problem;
- a measurable desired outcome and business value;
- explicit scope and non-goals;
- independently testable Given/When/Then acceptance criteria;
- named evidence for every acceptance criterion;
- test plan, dependencies, risks, rollout, success metrics, and open questions.

Prefer a small vertical slice that delivers observable value. Never invent priority, story points, project keys, field IDs, technical facts, or dependencies. Leave uncertainty visible for refinement.

## Definition of Ready and Done

The deterministic Definition of Ready must explain every failed check.

The shipping gate must require all of the following:

```text
ready_to_ship >= READY_THRESHOLD
quality_normalized >= QUALITY_THRESHOLD
tests_passed is true
lint_passed is true
typecheck_passed is true
unresolved_blockers == 0
human authorization exists for any side effect
```

Jev confidence is advisory and cannot waive failed tests or human authorization.

## Your immediate task: finish and verify SCRUM-1

Audit the current implementation against every acceptance criterion in `examples/scrum-1-proposed-task.md`.

At minimum, verify or add automated coverage for:

1. Valid and invalid `ProductBrief` validation.
2. Valid and invalid `JiraTaskDraft` validation.
3. AutoGen structured-output extraction without making a live model call.
4. Named Definition of Ready failures and the CLI's non-zero exit code for a failed gate.
5. A dry-run Jira flow that performs zero HTTP requests.
6. A confirmed Jira flow that is exercised only through a mocked transport.
7. Separate `needs_web_research` and `needs_repository_files` Jev questions.
8. Fail-closed handling for malformed Jev responses and out-of-range Score values.

Do not make live OpenAI, Jev, or Jira calls as part of tests. Do not update Jira, push, open a pull request, publish a package, or deploy unless the user explicitly requests that side effect.

## Verification

Set up the environment using:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
```

Before reporting completion, run:

```sh
.venv/bin/ruff check .
.venv/bin/mypy
.venv/bin/pytest
.venv/bin/agile-po --help
```

Report:

- acceptance criteria and their evidence;
- changed files;
- exact verification results;
- AutoGen/Jev/Jira calls made, which should be zero for normal tests;
- unresolved risks and recommended next issue.

Do not claim completion if any acceptance criterion lacks evidence.
