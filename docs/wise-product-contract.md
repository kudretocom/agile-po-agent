# Wise: first-release product contract

Status: proposed for Product Owner review (SCRUM-11, 24 September 2026). Reviewed with two live TypeSafe Jev playground requests, recorded in [wise-jev-review.md](wise-jev-review.md). This document specifies intended behavior; it does not claim the Jira agent is deployed.

## Purpose and first-release boundary

Wise helps a Product Owner or team lead decide whether one existing Jira work item is ready for development. It can assess the item, prepare an evidence-linked refinement, and later apply a reviewed refinement. `Ready` means ready to start development, not done, safe to release, or authorized to publish. The first pilot exposes Assess and Refine; Apply is a separate implementation and authorization milestone. No automatic issue creation, estimation, sprint planning, or broad autonomous research is in scope.

## Operation contract

| Operation | Required input | Output | Allowed side effect | Failure behavior |
| --- | --- | --- | --- | --- |
| Assess | Site/install identity, issue key, issue snapshot/version, requesting principal, accessible source references | Readiness state, checks, findings, missing evidence/decisions, source list, trace | None; optionally post a report only on explicit request | Return `Blocked` for unavailable essential input/service; never report `Ready` from partial execution |
| Refine | Assess result tied to the current issue snapshot, applicable evidence, requested scope | Structured draft, field-level diff, source-linked rationale, draft hash/version, readiness after proposed changes | Save a private draft; no Jira field edit | Return findings and unresolved questions; no fabricated source or silent fallback to guessed facts |
| Apply | Exact draft hash, issue version, current authorized principal, explicit approval bound to that hash and issue, diff | Jira update result with changed fields, actor, time, and resulting issue version | Update only approved fields on that issue | Reject missing/stale approval, changed issue, changed draft, denied permission, or failed gate. Return no success until Jira confirms the write |

For a user-facing Rovo invocation, the principal and site come from verified Atlassian context, not model-generated text. The service must scope every request and stored draft to installation, site, and issue. A repeated Apply request uses the same idempotency key and must not duplicate the update. An approval is single use and expires; exact lifetime is an open product decision. If an update times out after submission, query Jira before reporting whether it applied.

## Input and evidence

Minimum input is the Jira issue key, summary, description, type, status, version/updated timestamp, relevant links, and the requesting principal. The issue snapshot is always captured before assessment. Linked Confluence pages and repository files are optional by default; the decision policy can declare a particular source mandatory for a particular claim. A link alone is not evidence: the source content and stable reference (page version, commit SHA, or issue version) must be loaded and accessible.

Each evidence item has `source_id`, `kind`, `uri`, `version`, `observed_at`, `access`, `freshness`, and a concise `finding`. `access` is `available`, `missing`, or `denied`; `freshness` is `current`, `stale`, or `unknown`. These states remain distinct. The user can see which findings support each proposed change. A repository reference without a commit SHA, or a Confluence page without a version, has unknown freshness until resolved. A source is never marked current merely because it was read today.

The first pilot requires the Jira snapshot. Repository evidence becomes mandatory when a proposed criterion claims existing behavior or a code-level constraint. Confluence or other product evidence becomes mandatory when a proposed criterion asserts a product policy or approved user flow. External web research is requested only when the question depends on an external fact. The source owner or policy may later refine these defaults. Denied access does not authorize Wise to seek alternate credentials.

For a material contradiction, Wise records both sources and stops at `Needs decision`. The Product Owner decides the intended product behavior; an engineering owner confirms the implementation gap when code differs from that decision. The resolution record names the decision maker, chosen rule, rationale, source versions, and any follow-up issue. Neither the newest source nor the repository automatically wins. Wise reassesses from a fresh issue snapshot after the resolution; an unresolved contradiction cannot become `Ready`.

## Decision rules

Process in this order; the first applicable state wins.

1. `Blocked`: the Jira snapshot or required service cannot be read, a source is denied, the run times out or reaches its step cap before a stable result, the decision response is malformed, or a mandatory control cannot be evaluated. Explain the operational blocker and safe retry/owner.
2. `Needs decision`: available sources contradict each other on a material claim, a policy/owner decision is open, or JEV's Noul/Choice confidence is in its configured uncertainty band. Name the deciding person or role where known.
3. `Needs evidence`: a required source is missing, stale, or of unknown freshness; or required acceptance/test evidence is absent. List exactly what to collect.
4. `Ready`: all required sources are available and current, no material conflict or open decision remains, every deterministic Definition of Ready check passes, and JEV's relevant sufficiency/quality advice passes configured thresholds.

JEV outputs are advice to code-owned gates. A high score cannot waive a failed check. `allow_action` cannot grant Jira write authority. The service uses the repository's configured Noul thresholds and bounded `MAX_STEPS`; uncertainty is a recorded result, never silently coerced to yes or no. `Ready` remains unavailable if evaluation is partial. Shipping checks (tests/lint/typecheck/human approval) are separate from this readiness decision.

## Output contract

The default response has a short title, one of the four states, a plain-language reason, up to three next actions, and whether Jira was changed. Expandable details contain source references, findings, checks, a field-level diff, approval, and action history. The machine form is `wise.assessment.v1`, illustrated in [wise-assessment-example.json](../examples/wise-assessment-example.json). `run_id` links the visible result to the trace. The trace records model identifier, typed JEV decision, usage and latency where available, source versions, check results, proposed change, approval, attempted operation, and confirmed outcome. It excludes chain-of-thought, credentials, raw tokens, and unnecessary personal data.

User-facing example, matching the JSON fixture:

> **SCRUM-42 · Needs decision**
>
> The proposed payroll criterion says an employee sees every payroll document; the repository rule limits access to the selected employer. Confirm whether former employees retain access to historical documents.
>
> **Next:** Product Owner resolves the access rule; then review the narrower criterion.
>
> **Jira changed:** No. A refinement is proposed only.

## Scenario review

| Scenario | Evidence/control result | State | Next action | Jira field write |
| --- | --- | --- | --- | --- |
| Complete | Jira and required policy/code sources versioned and current; all deterministic checks pass; no open decision | Ready | Offer reviewed refinement or development handoff | No |
| Missing repository evidence | Criterion claims current access behavior but repository content is not loaded | Needs evidence | Load the relevant files at a commit SHA | No |
| Conflicting evidence | Product document allows historical access while code restricts it | Needs decision | Product owner resolves intended behavior; engineering records implementation gap | No |
| Uncertain JEV answer | Noul probability lies between configured no/yes thresholds | Needs decision | Human reviews the specific question and evidence | No |
| High JEV score, failed check | Quality 0.95 but acceptance criterion has no observable evidence | Needs evidence | Add a testable criterion and evidence method | No |
| Service unavailable or step cap | Required evaluation cannot complete | Blocked | Retry safely or contact service owner | No |
| Apply without approval | Draft hash has no matching approval | Blocked for Apply; assessment state stays unchanged | Review and approve exact diff | No |
| Apply after issue/draft change | Approved hash or issue version no longer matches | Blocked for Apply; assessment state stays unchanged | Reassess and seek new approval | No |

The `Blocked for Apply` rows are operation results rather than a rewrite of the earlier readiness assessment. This prevents an authorization problem from being misreported as a product-quality finding.

## Existing code and required work

| Capability | Current repository | Required for Wise |
| --- | --- | --- |
| Structured brief and Jira draft | `ProductBrief`, `JiraTaskDraft` in `models.py` | Map a live issue snapshot into the brief without losing issue version and references |
| Bounded JEV/AutoGen flow | `ProductOwnerOrchestrator` records decision trace and stops on uncertainty/missing context | Add source-linked findings and distinguish product decisions from operational blockers |
| Deterministic readiness | `DefinitionOfReadyEvaluator` checks nine draft properties and requires no failed check | Add evidence currency/conflict gates and the four-state decision policy |
| Jira preview/write | `JiraClient.preview`; `update` needs a `confirm` boolean | Add installation-scoped auth, exact draft/version approval, permission check, idempotency, and confirmed write trace |
| Output | CLI JSON draft/evaluation | Add Rovo/A2A response, short summary, expandable trace, and versioned JSON |

The existing Jira adapter's `confirm` flag is suitable for a local CLI guard, but does not by itself prove who approved a particular Wise draft. Existing JEV traces do not yet link source evidence to an individual proposed change.

## Atlassian delivery constraint

Atlassian's [Rovo Agent Connector reference](https://developer.atlassian.com/platform/forge/manifest-reference/modules/rovo-agent-connector/) describes a Forge Preview module for a remote agent that can be assigned a Jira item, mentioned, or used in Rovo Chat. New connectors target A2A 1.0 over JSON-RPC; only Jira is supported during Preview. The module requires `read:jira-work`; additional scopes follow the actual actions used. Sync transport times out at 55 seconds and streaming at 900 seconds, so any longer refinement needs a durable task and safe reconnect behavior. Forge Remote calls must verify their invocation token and isolate tenant data, per [Forge Remote guidance](https://developer.atlassian.com/platform/forge/remote/essentials/). The connector can change which app user is mentionable, so deployment must be checked on a dedicated pilot app. These are integration requirements, not a claim that Wise is installed.

## Proposed product decisions for review

1. Pilot surface: test a user-triggered `@mention` first as a proposed default, with assignment and Rovo Chat as alternatives. The initial Jev choice favored assignment but had only 0.23 confidence, below the repository's 0.70 Choice threshold. Therefore the surface is not settled by Jev; PO review and a small usability pilot determine it. Apply arrives only after approval controls are built.
2. Evidence freshness: use immutable commit/page/issue versions; treat unversioned evidence as unknown. Do not impose a universal number of days on product policy, since age alone does not establish validity.
3. Trace retention: keep only minimal references and decisions; set the actual retention period after privacy and customer-administration review.
4. Required-source policy: use the claim-specific defaults above and the explicit conflict-resolution rule, then validate them with pilot issues before claiming full coverage. Jev returned 0.61 on sufficiency in both reviews, inside the configured Noul uncertainty band; the policy needs human acceptance and scenario validation.

PO review: pending. No product owner has yet accepted these four choices or the proposed output schema. Acceptance of this document should record the reviewer, date, and any changes here or on SCRUM-11.
