# Proposed update for SCRUM-1

## Summary

Generate a Jira-ready task from a local product brief

## Context

Product ideas currently become vague Jira tasks that require repeated clarification before engineering can begin. The first vertical slice should prove that a bounded AutoGen Product Owner can turn a local brief into one reviewable, schema-valid task without changing Jira.

## Desired outcome

A developer can run one local command and receive a structured Jira task in JSON and readable Markdown, together with a deterministic Definition of Ready result.

## Scope

- Load and validate a local `ProductBrief` JSON file.
- Use one bounded AutoGen `AssistantAgent` session to create a `JiraTaskDraft`.
- Validate the structured output with Pydantic.
- Evaluate the draft with deterministic Definition of Ready checks.
- Render the draft locally without writing to Jira.

## Non-goals

- Creating or updating Jira issues.
- Running an autonomous group chat.
- Calling Jev in this first vertical slice.
- Estimating priority or story points.

## Acceptance criteria

- [ ] **Given** a valid local product brief, **when** the draft command runs with valid model configuration, **then** it produces a schema-valid `JiraTaskDraft`. Evidence: automated schema-validation test and a saved JSON artifact.
- [ ] **Given** the generated draft, **when** Definition of Ready evaluation runs, **then** every failed check is returned by name and the command uses a non-zero exit code when the gate fails. Evidence: unit tests for passing and failing drafts.
- [ ] **Given** the default first-issue workflow, **when** generation completes, **then** no Jira create or update request is sent. Evidence: integration test with a mocked Jira transport.
- [ ] **Given** the repository test suite, **when** CI runs, **then** Ruff, mypy, and pytest pass on supported Python versions. Evidence: green CI checks.

## Test plan

- Unit-test `ProductBrief` and `JiraTaskDraft` validation.
- Unit-test passing and failing Definition of Ready evaluations.
- Mock the Jira transport and prove that dry-run performs no request.
- Run Ruff, mypy, and pytest locally and in CI.

## Success metrics

- The example brief produces one valid task draft in a bounded run.
- All deterministic quality checks and repository tests pass.
- Zero Jira writes occur in the first vertical slice.

## Risks

- Model output may fail schema validation; the command must fail clearly without partial output.
- Prompt quality may vary across models; fixtures and evaluation cases will be expanded before public promotion.

## Open questions

- Which evaluation dataset should become the public benchmark for task quality?
- Which Jira fields beyond summary and description should be supported after the dry-run milestone?

