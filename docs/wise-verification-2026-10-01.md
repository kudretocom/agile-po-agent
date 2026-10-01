# Wise local runtime continuation — 2026-10-01

PR: https://github.com/kudretocom/agile-po-agent/pull/6
Route remains Cloudflare + the same OpenAI Wise user/issue session.

## Evidence

- 78 Python tests; Ruff across the repository and mypy (15 source files) pass.
- 28 Node tests: actual WebCrypto FIT verification, user-token Jira HTTP,
  same-session OpenAI tool-result contract, GetTask, revoked access/current
  versions, replay/multiworker uncertainty, storage capacity, cleanup race,
  session retirement/deletion, explicit allowances and isolated lifecycle FITs.
- Actual local Miniflare/workerd + SQLite DO: 8 concurrent claims, 1 dispatch;
  completed replay, task lookup and uninstall rejection pass. No provider calls.
- Actual Python Workers through official pywrangler: Python 3.13.2,
  pydantic 2.10.6/httpx 0.28.1. The canonical Turkish claim fixture produces
  needs_evidence with jira_changed=false and zero provider calls.
- Actual JS Worker→Python Worker private RPC passes. Runtime composition with
  real coordinator/client/loop code plus mocked Jira/OpenAI transports proves
  same-session continuation, completed replay and GetTask; one deterministic
  tool execution, zero real provider calls.
- Local transport disconnection recovered. Old Miniflare PythonRequirement
  packaging is unsupported; recovered with the official uv/pywrangler path.
- The Forge example and JS entry both use /a2a/json-rpc. Pre-uninstall uses its
  own endpoint/FIT; no principal or Jira user/system token is used for cleanup.

## What this does not prove

No actual Forge app was created/installed, no Cloudflare deployment occurred,
no OpenAI/TypeSafe call was made, and no external agent was contacted. The live
JEV guard/client binding is implemented but its Workers network path has not been
executed. Actual cloud CPU/startup/latency, installed A2A schema and provider
lifecycle/usage need the approved bounded nonprod pilot.

The initial official Python bundle included development environment modules.
Isolating the prepared bundle reduced the local dry-run to 283 modules,
7277.06 KiB upload / 1986.89 KiB gzip; dry-run exited without upload/deployment.
Actual cloud CPU/startup verification is still pending. Current Cloudflare
limits are checked from the official page, not remembered historical limits.

The 24h TTL remains a proposed pilot policy. Completed metadata is physically
removed. Retired sessions await explicitly enabled provider deletion; uncertain
charged attempts and unknown session creations retain bounded reconciliation
metadata. Full deletion cannot be promised before that process is demonstrated.

## Jira acceptance remains open

- SCRUM-59 epic: progress/evidence, not Done.
- SCRUM-60: real transports + Workers tool host/composition now evidenced locally;
  genuine installed FIT/Jira/Rovo/OpenAI A2A and cloud metrics pending.
- SCRUM-61: GetTask/lifecycle/caps/alarms/race-safe deletion implemented and tested;
  real uninstall/provider deletion/uncertain-provider reconciliation pending.
- SCRUM-62: canonical Turkish claim collector and strict deterministic host tested;
  wider authorized versioned evidence collectors not claimed complete.
- SCRUM-63: target nonprod site/install/grants/bounded spend/live participant
  identity still need the concrete approval handoff.
- SCRUM-64: listing/privacy/support/assets/partner verification/legal submission
  remain draft; no Marketplace publication or provider acceptance is claimed.
- SCRUM-65: future Refine/Apply/Figma scope unchanged and not implemented here.

## Approval dependencies

Nonprod Jira URL is unresolved; operoner is only used for the authorized backlog.
Dedicated Forge registration/install, CF deployment/bindings/secret attachment,
OpenAI reusable Wise agent/project credential and TypeSafe nonprod secret reuse,
live agent communication, session data processing/retention and actual spend
must follow the concrete provider/action/scope form. General “continue” does not
activate these flags or authorize legal terms/payments. See
[nonprod approval handoff](wise-nonprod-approval-handoff.md).
