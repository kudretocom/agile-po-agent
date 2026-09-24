# Wise Assess: read-only pilot slice (SCRUM-12)

`WiseAssessor` implements the four-state decision policy from [the product contract](wise-product-contract.md). It does not create, update, comment on, or assign Jira issues. `read_scoped_issue` makes one Jira GET and binds it to an explicitly authorized installation ID and site. The caller must supply that trusted identity; it must never come from a model answer.

The pipeline has three distinct layers:

1. A trusted collector loads a Jira issue and source contents. It records source ID, scope, immutable version, observation time, access, freshness, and a short finding. A link alone is not evidence. `current` is a collector assertion about the exact version, not a date heuristic; the collector must verify this before constructing a record. This slice validates the record but does not crawl Confluence or repositories.
2. Code maps explicit claim kinds to required source kinds: issue → Jira, existing behavior → repository, approved flow/policy → product document, external fact → external source. Missing/stale/unknown required evidence is named. Denied access, missing Jira snapshot, and step exhaustion block. A normalized `JiraTaskDraft` tied to the issue summary enables the existing nine deterministic Definition of Ready checks; without it, `Ready` is unavailable.
3. TypeSafe Jev receives independent claim-to-finding Choice questions and a support-quality Score in one request. It returns typed judgments, not sources or authorization. The client validates the answer envelope, option set, probabilities, confidence, score rubric, and usage. Uncertain or contradictory answers require a decision. A high score never waives a deterministic failure. A bad response or timeout blocks.

State precedence is `Blocked > Needs decision > Needs evidence > Ready`. Unresolved material contradictions retain both source IDs. Closing one requires a chosen rule, named decision maker, timestamp, rationale, and the exact two source versions. A changed source version invalidates the resolution. The [example report](../examples/wise-assessment-example.json) is `wise.assessment.v1`; its `run_id` joins a short summary to a sanitized trace. No credentials, raw source body, or model reasoning are serialized.

The installed project skill is `.agents/skills/typesafe-ai/SKILL.md`, pinned by `skills-lock.json`. Design follows the live [TypeSafe API](https://docs.typesafe.ai/api), [State](https://docs.typesafe.ai/concepts/state), [Choice](https://docs.typesafe.ai/primitives/choice), and [citation-checking recipe](https://docs.typesafe.ai/cookbooks/citation_check). Tests use deterministic HTTP fixtures; the repository does not contain a TypeSafe credential.

## Pilot boundary and follow-up

This is a callable Python core, not a deployed Rovo/A2A agent. Before a customer pilot, build authenticated source collectors for Confluence/repository/external data, a reliable issue-description-to-normalized-draft mapper, and an installation-scoped service boundary. The SCRUM-11 open product choices remain open, particularly the final required-source policy, undocumented claims, and freshness ownership. The pilot must not treat a fixture `Ready` as a claim of universal product readiness.

The SCRUM-11 example was originally a proposed Refine result; it now shows an Assess result to match the executable contract. Refine proposal, approval, and Apply fields move to their later operation-specific reports.
