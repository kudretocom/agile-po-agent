# Wise Cloudflare runtime (SCRUM-60/61)

Approved route: Jira/Rovo → Cloudflare → the same user/issue-specific OpenAI Wise
session. The Python Assess core owns deterministic evidence/Definition of Ready
checks. Assistant prose never becomes a Ready decision.

Implemented locally:

- `runtime.mjs` composes actual FIT/Jira/OpenAI HTTP clients and the Python private
  service binding. `/a2a/json-rpc` matches the existing Forge template. Execution
  defaults to disabled; configure no credentials or allowances without the
  concrete approved nonprod handoff.
- `agent-loop.mjs` checks the saved/session agent (one `wise_assess` function,
  no subagents, environment none), follows bounded session/turn state, executes
  only server-collected input and submits the official tool_result envelope.
  Result retrieval reads the matching function-call output, never model prose.
  Timeouts, ambiguous turns and uncertain submissions require reconciliation.
- `durable-ledger.mjs` uses real SQLite DO transactions and alarms. Scope keys
  hash installation/cloud/site/principal/issue. Same-installation DO routing keeps
  user memory keys isolated and serializes session invocations. The task index
  includes an issue key for a fresh invoking-user permission/version GET; it
  contains no Jira description, model output or credentials.
- `GetTask` requires the same verified user, current Jira access/version and a
  completed root-agent turn. Cached requests also recheck user access.
- Default capacity is 1000 records. Session/Assess/JEV allowances are explicit,
  never refunded after uncertainty and never automatically reset. They bound
  invocation counts, not dollar cost; approval must also constrain the provider
  agent/model/project budget.
- Completed metadata is physically removed at TTL (default 24h, a proposed pilot
  policy). Session memory retires at expiry; new turns stop until reconciliation.
  Authorized remote session deletion is separately gated, with at most three
  deletions per alarm. OpenAI deletion cleanup can itself be asynchronous.
  Unknown charged attempts retain bounded tombstones for manual reconciliation.
- The dedicated principal-free Forge `preUninstall` FIT endpoint disables only
  its verified installation. It clears message/task metadata transactionally,
  retaining session IDs/pending creation metadata only for cleanup/reconciliation.
  Assessment FITs cannot invoke this endpoint. No Jira system token is used.
- `python-worker/entry.py` exposes Assess over private RPC; its HTTP handler is
  404. The existing TypeSafe client is bound behind explicit JEV enablement and
  a DO JEV allowance. All live provider execution remains disabled.

## Reproduction without deployment

Use Node 24: `node --test cloudflare/*.test.mjs` (28 tests).
Install Miniflare 4 in an isolated local tools directory, then:

```
node cloudflare/workerd-smoke.mjs /absolute/path/to/miniflare/dist/src/index.js
node cloudflare/python-worker/prepare-local.mjs
```

In `cloudflare/python-worker`, with uv installed and its binary in PATH:

```
WRANGLER_SEND_METRICS=false uv run pywrangler dev --local --config wrangler.smoke.jsonc --port 8799
```

In `cloudflare`, start the **local-only** RPC harness:

```
WRANGLER_SEND_METRICS=false npx wrangler dev --local --config wrangler.rpc-smoke.jsonc --port 8798
```

Then from the repository root:

```
node cloudflare/python-workerd-smoke.mjs http://127.0.0.1:8798
node cloudflare/runtime-composition-smoke.mjs http://127.0.0.1:8798
```

The latter uses actual JS coordinator/HTTP-client/loop code and real JS→Python
Workers RPC; Jira/OpenAI transports are mocked. No Forge installation, live A2A,
provider grant, model spend or deployment is represented by these results.
Never deploy the smoke entry/config files. Keep emulator logs outside the watched
Python project to prevent log writes from triggering reloads.

Python packaging must use official pywrangler (lock files included); the old
Miniflare PythonRequirement format is removed in current workerd. Tested local
Python runtime: 3.13.2, pydantic 2.10.6, httpx 0.28.1. The prior standalone Pyodide
3.14.2 smoke is separate evidence. Cloud resource CPU/startup limits, actual
provider latency/usage, authentic installed FITs, uninstall delivery and remote
physical cleanup still require a bounded authorized nonprod pilot. Node CI job
remains a maintainer handoff in `ci-node24.patch`; no OAuth workflow expansion.

Official references checked 2026-10-01:

- https://developers.cloudflare.com/workers/languages/python/packages/
- https://developers.cloudflare.com/workers/wrangler/configuration/
- https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/
- https://developers.openai.com/api/docs/guides/agents-api/tools/functions
- https://developers.openai.com/api/docs/guides/agents-api/sessions/manage
- https://developer.atlassian.com/platform/forge/manifest-reference/modules/pre-uninstall-trigger/
