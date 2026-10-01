# Pilot issue boundaries and session creation

Head 3ef4efa had site validation but no issue allowlist. Earlier approval text
describing a SCRUM-73 server filter was a proposal, not an enforced control.
No live deployment/provider execution occurred during that gap. The correction
requires explicit PILOT_ISSUES_JSON, for example
`{"operoner.atlassian.net":["SCRUM-73"]}`. Missing, malformed, wildcard or duplicate
policy fails closed. SendMessage denies other issues before Jira read, session
reservation or provider/tool execution. GetTask rechecks the current allowlist
after minimal routing metadata lookup, before any Jira/provider read. Lifecycle
cleanup remains installation-scoped even when issue policy is removed. This
does not narrow read:jira-work: the grant can read other issues visible to the
invoking user. Local smoke fixtures configure their own explicit fixture keys.

Previously new-session Assess made an additional paid “Initialize Wise” model
turn, committing its session identity only after initialization polling success.
Official create input is optional. We now create an empty session, then run the
first real assessment in the SAME saved agent/session. No initialization prompt
is sent. Function request and completion after function output still involve
model inference; HTTP request count is not a provider inference/cost bound.

A valid returned ID is durably stored under the original scoped reservation
before configuration/status validation. It is quarantined as creationPending
until completion. Unexpected/busy/failed responses retain the known ID and block
another create. An ambiguous create response without an ID retains the durable
reservation, also blocking duplicate dispatch. A crash between provider success
and durable ID write remains an uncertainty window; exact-once creation is not
promised. The reservation prevents automatic retry.

Explicit internal reconcileCreatedSession verifies the known SAME scoped
session and requires idle with zero turns before completing its reservation.
It creates/sends nothing and is not a new public operator endpoint. An ID
returned after uninstall is stored retired for separately authorized cleanup;
it cannot reactivate the installation.

The official `agent.session.input.cancel` event is implemented. Explicit loop
cancellation verifies session identity/configuration first. Poll/fetch timeout
does not automatically invoke it. Acknowledgement is not terminal cancellation,
a refund or budget proof; subsequent session/turn readback is required. Pending
claims are not released. No live cancellation/provider call occurred.

Validation: 98 Python tests, 37 Node tests, Ruff and mypy (17 source files).
Regressions cover missing/outside policies, GetTask policy tightening, known and
unknown creation failures/restart, early-ID quarantine and explicit read-only
reconciliation, real SQLite restart, late result after uninstall and cancel.

US$1 was our proposed limit, not a user-specified or approved budget. It is NOT
guaranteed: Hosted Agents create/session/events expose no verified total token/
generation cap, and provider spend enforcement can lag. The 4096-output envelope
was hypothetical, not implemented. Free plan/remaining allowance is unverified.
New grant/credential/install/deploy/network AI spend need separate authorization.
No SDK/Responses architecture substitution was made. Old setup discovery is
closed: the complete old thread had no actual installation.

Official contracts checked 2026-10-01:

- https://developers.openai.com/api/reference/resources/beta/subresources/agents/subresources/sessions/methods/create
- https://developers.openai.com/api/reference/resources/beta/subresources/agents/subresources/sessions/subresources/events/methods/create
- https://developers.openai.com/api/docs/guides/spend-limits
