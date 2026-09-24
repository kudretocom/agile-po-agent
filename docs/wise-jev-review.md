# Wise product contract: live Jev review

Date: 24 September 2026. Source: authenticated TypeSafe Playground, `jev-latest` resolved to `jev-1.13.0`. These requests used a summary of the public Wise product draft and no customer issue content or credentials. Jev gave typed, atomic answers; the interpretations and product changes below are made by the application team.

## First request: release direction

State summarized the Assess/Refine scope, current bounded JEV/AutoGen and deterministic readiness implementation, four proposed states, and three open decisions. Questions asked which Jira entry point to pilot, whether the contract is sufficient for a pilot, and which open decision to resolve first.

Request ID: `playground_1f15a91414e743746a7850a8854eb6a10d3`.

| Question | Typed result | Interpretation |
| --- | --- | --- |
| Pilot entry | `assignment` 0.49, `chat` 0.28, `mention` 0.23; Choice confidence 0.23 | Below configured 0.70 confidence; no entry point selected by Jev |
| Contract sufficient | Noul 0.61 | Between configured 0.30/no and 0.70/yes thresholds; uncertain |
| Most urgent gap | `source_policy` 0.58, `pilot_surface` 0.29, `trace_retention` 0.13; Choice confidence 0.38 | Source policy is a useful review focus, but confidence is below 0.70 |

Usage: 661 input and 100 output tokens; reported evaluation time 96.5 ms. The response did not authorize Jira writes or a Ready state.

## Second request: source policy

State supplied the claim-specific source proposal: versioned Jira snapshot, repository SHA for claims about code behavior, versioned product documents for policy/user-flow claims, external research only for external facts, and distinct missing/denied/stale/conflicting states. Questions asked whether that policy is sufficient and which one rule matters most before a pilot.

Request ID: `playground_1f1e8703244e7c843f99ec213012f806a3f`.

| Question | Typed result | Interpretation |
| --- | --- | --- |
| Source policy sufficient | Noul 0.61 | Still uncertain under configured thresholds |
| Most important missing rule | `conflict_resolution` 0.76, `source_freshness` 0.20, `none` 0.04; Choice confidence 0.63 | Focus on explicit conflict ownership and recording. Below 0.70, so not an autonomous policy decision |

Usage: 641 input and 71 output tokens; reported evaluation time 53.3 ms. The product contract now proposes a conflict-resolution rule and retains PO review as pending.

## Resulting product changes

- Added a proposed owner and decision record for contradictory code/product sources. An unresolved material conflict remains `Needs decision`.
- Left the pilot entry point open. A 0.49 leading probability with 0.23 Choice confidence cannot settle it.
- Kept source policy and contract sufficiency pending human review because Noul 0.61 is uncertain under the repository's current 0.30/0.70 interpretation.
- Kept Apply outside the initial pilot and preserved the existing authorization boundary.

The playground response has an extra `request_id` and `evaluation_time_ms` compared with the strict envelope parsed by the current Python client. These UI results are review evidence, not a fixture claiming that the direct API returned the same envelope. The API contract and smoke test remain documented in [jev-contract.md](jev-contract.md).
