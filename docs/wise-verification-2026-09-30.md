# Wise continuation verification — 2026-09-30

Baseline PR #5 remains open/draft at cd492d4e1a23ec041c092f5ff642846278b1e6e1;
Python 3.10–3.12 CI was verified green through GitHub. Original checkout preserved,
including untracked `examples/scrum-6-personelos-landing-v2-brief.json`.
Continuation uses an independent clone and branch.

Old Codex task was read through supported local `read_thread`; no database/session
access bypass. Latest decisions recovered: Wise name, Cloudflare replacing
Vercel, same OpenAI Wise session behind Jira/Rovo. Project function document read.
Repository `.agents/skills/typesafe-ai/SKILL.md` read; relevant local memory
summary/rollout-summary search found no Wise matches. No repo AGENTS.md was found.

| Verification | Result | Limit |
| --- | --- | --- |
| Python baseline | 75 tests passed | Existing offline tests |
| Python continuation | 76 tests passed; Ruff/mypy passed | Adds minimized real-source replay; no network/model execution |
| Node coordinator/storage | 12 tests passed | Injected provider fixtures and local storage contract |
| Multiworker | 8 independent Node processes → one dispatch reservation | Real temporary SQLite, not Cloudflare deployed DO |
| Restart/failure | Cached task survives restart; uncertain dispatch never reclaims automatically | Provider reconciliation/cleanup still required |
| Real Jira read | SCRUM-32 read via authorized connector; source updated 2026-09-29T21:10:28.434+0300 | Existing production work only read, not invoked or rewritten |
| Real-work-derived replay | Needs evidence, no normalized DoR, missing repository evidence, zero JEV calls, jira_changed=false | Minimized excerpt fixture, not full live pilot |
| Live Forge→Cloudflare→OpenAI A2A | Not run | Nonprod site and bounded provider/install/grant approval pending |
| Marketplace submission | Not performed | Runtime/real pilot/security/brand/privacy/support/legal package incomplete |

SCRUM-32 is Done in Jira but the minimized claim still requires repository/schema
evidence; Jira status or a prior JEV percentage cannot stand in for that evidence.
This result does not reevaluate or reopen SCRUM-32; it verifies Wise's safe behavior
with a representative brief. No fresh live JEV pass is claimed.

## Jira route

- Epic [SCRUM-59](https://operoner.atlassian.net/browse/SCRUM-59)
- [SCRUM-60](https://operoner.atlassian.net/browse/SCRUM-60): Cloudflare/OpenAI runtime
- [SCRUM-61](https://operoner.atlassian.net/browse/SCRUM-61): persistent replay/lifecycle
- [SCRUM-62](https://operoner.atlassian.net/browse/SCRUM-62): Turkish/versioned collectors
- [SCRUM-63](https://operoner.atlassian.net/browse/SCRUM-63): authorized actual A2A pilot
- [SCRUM-64](https://operoner.atlassian.net/browse/SCRUM-64): publication package
- [SCRUM-65](https://operoner.atlassian.net/browse/SCRUM-65): future Refine/Apply/Figma slices

All Task issues were confirmed assigned to existing SCRUM Sprint 0 (ID 2); epic
outside sprint. Blocks links: 28→60; 60→61/62; 61/62→63; 63→64. Existing issues
searched before creation. No issue was marked Done on this continuation.

GitHub rejected the initial push because the existing OAuth credential lacks
`workflow` scope for CI edits. The workflow change was preserved as
`cloudflare/ci-node24.patch` for an authorized maintainer; no broader grant was
requested. Until applied, Python CI runs normally and Node validation remains local.

Remaining implementation is explicit: real client adapters and deterministic core
tool binding; GetTask and install/uninstall flows; DO capacity/retention/cleanup;
collectors and free-form Turkish normalization; actual runtime/provider tests.
The local spike is reviewable implementation evidence, not release completion.

## Offline continuation, 2026-10-01

- Actual HTTP adapters added: WebCrypto RS256 FIT verification against the fixed
  Atlassian JWKS, approved app/module/environment/site binding, signed Jira API
  route and invoking-user GET; OpenAI Agents create/retrieve/same-session input
  events with the documented beta header. Provider execution defaults to disabled.
- 17 Node tests pass, including mocked official HTTP envelopes, JWT tampering,
  environment/site rejection, bounded request/response bodies and no automatic
  retry after provider uncertainty. These are contract tests, not live A2A.
- Python Assess ran inside local Pyodide 314.0.7 / Python 3.14.2 with actual
  pydantic/httpx/pydantic-settings packages and the minimized SCRUM-32 fixture:
  needs_evidence, jira_changed=false, zero JEV calls. Reproduce with
  `node cloudflare/python-wasm-smoke.mjs <installed-pyodide.mjs-path>`.
  Public dependency downloads occur during this optional smoke. This does not
  establish Cloudflare's selected Python ABI, workerd packaging or deployment.
- Turkish `## Wise iddiaları` is an explicit alias of `## Wise claims`; typed
  claim keys remain canonical. Multiple sections, >32 claims and >2000-character
  claims fail closed rather than inferring assertions from ordinary prose.
- Biggest implementation blocker: host the deterministic Assess tool in the
  actual Workers runtime and bind the OpenAI required-actions/turn-result loop.
  No nonprod site, install, grants or paid calls are needed to continue offline
  implementation. Live deployment/pilot still requires the concrete approval
  handoff; none has been performed. JS GetTask/lifecycle/physical-retention/caps
  remain open (Python GetTask tests are not JS runtime evidence).
