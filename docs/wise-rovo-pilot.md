# Wise Rovo read-only pilot (SCRUM-28)

This is a non-production A2A 1.0 adapter for the existing Wise Assess core, not a deployed Forge app or Marketplace listing. The [manifest template](../forge/manifest.example.yml) deliberately has no app ID or remote URL. The pilot accepts both issue assignment and comment @mention messages so the product owner can choose a first entry surface without changing the security boundary. It does not handle free-form Rovo Chat, streaming, Apply, Jira comments, or issue updates.

## Trusted path

1. Forge sends `SendMessage` to `/a2a/json-rpc`. The remote verifies its FIT with Atlassian's JWKS, the expected app audience, issuer, endpoint module key, timestamps, installation ID, site, and principal. Message text and the issue summary embedded in the event are not trusted as source data.
2. The adapter takes the issue key only from the structured issue part and requires the event's user account ID to match the verified principal. It requires `x-forge-oauth-user`; a missing user token rejects the task. It never falls back to `x-forge-oauth-system` or the repository's Basic-auth Jira adapter.
3. It fetches exactly one issue with GET through the verified cloud ID's Atlassian API gateway. The issue response must match the requested key. The current Jira snapshot becomes a versioned Jira evidence record. Unsupported or inaccessible sources remain missing; a link alone is not promoted to evidence.
4. A strict parser recognizes the existing `JiraTaskDraft` section template and optional `## Wise claims` lines in the form `- issue: ...`, `- code_behavior: ...`, `- product_policy: ...`, or `- external_fact: ...`. It does not infer claims from free-form prose. Only an explicit `issue` claim cites the Jira snapshot. Other kinds require their own future collectors, so they cannot become Ready in this pilot. A draft that does not match the template remains unnormalized; Wise reports the missing Definition of Ready gate rather than inventing fields.
5. The response is a terminal A2A task with a short message and a `wise.assessment.v1` data artifact. `GetTask` and repeat `messageId` requests re-read Jira with the current invoking-user token and return a cached result only while that user still has access and the issue version is unchanged. Repeats do not call JEV again for the same version. Task data is held only in bounded process memory; this is **not** a distributed or durable task store and must be replaced before a multi-worker/customer pilot.

The installed TypeSafe skill guided this design: code verifies source identity, claim kind, and deterministic gates before sending any semantic support question to JEV. No JEV call is made for missing claims, absent/failed Definition of Ready, or unavailable required sources. The [TypeSafe State guidance](https://docs.typesafe.ai/concepts/state) and [citation-checking recipe](https://docs.typesafe.ai/cookbooks/citation_check) describe the narrow claim-to-finding judgment used by the core.

## Local setup

Install with `pip install -e '.[dev,rovo]'`. Set `FORGE_APP_ID` to the exact app ARI in the manifest and inject `TYPESAFE_API_KEY` through the approved secret mechanism. Start `uvicorn agile_po_agent.wise_rovo_server:app --host 127.0.0.1 --port 8000` for local fixture testing. The remote must use HTTPS when connected to Forge. Never copy a production FIT or OAuth token into a fixture or terminal command.

Before Forge deployment, replace the manifest placeholders, select and approve the initial invocation surface, configure the remote HTTPS endpoint, verify the app-user token is issued, and run a non-production end-to-end test. This connector is based on Atlassian's current [Rovo Agent Connector](https://developer.atlassian.com/platform/forge/manifest-reference/modules/rovo-agent-connector/), [Jira remote-agent guide](https://developer.atlassian.com/platform/forge/remote-agents-in-jira/), and [Forge Remote FIT verification](https://developer.atlassian.com/platform/forge/remote/essentials/). A connector changes which app user is mentionable; deploy a dedicated pilot app, not an existing shared Forge app.

## Known limits before a customer pilot

- No authenticated repository, Confluence, or external content collectors. Do not treat links or the event's text as source content.
- No durable task/nonce store or cross-process replay protection. The in-memory store is bounded but intentionally ephemeral.
- No deployment or real Atlassian installation has been performed; only offline FIT/Jira/A2A fixtures are verified.
- Source-policy acceptance, freshness ownership, and the @mention-versus-assignment choice are open product decisions from SCRUM-11.
