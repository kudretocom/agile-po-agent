# Wise Cloudflare runtime spike (SCRUM-60/61)

This is local, dependency-free JavaScript, not a deployed Worker. It preserves the
approved direction: Jira/Rovo → Cloudflare A2A entry → the same user/issue-specific
OpenAI Wise session. Python Assess remains the authoritative deterministic core.
The Python AutoGen/PyJWT/cryptography environment has **not** been demonstrated to
run in Python Workers; this spike does not claim a direct Python deployment.

`a2a-coordinator.mjs` binds a verified invocation, invoking-user Jira read, current
issue version, replay ledger, and an injected agent client. FIT verification,
real Jira/OpenAI transports, GetTask, lifecycle endpoints and the deterministic
Assess tool binding still need implementation before installation. The agent
client in tests is a fixture; checking the result envelope is not sufficient to
prove a model-generated Ready decision. Real results must come from the Wise
deterministic evidence and Definition of Ready gates.

`replay-ledger.mjs` uses the documented Durable Object storage
`transaction/get/put` interface. Records contain hashed context/message/version,
claim IDs, task IDs and session IDs. No credential, Jira description or model
output is stored. Pending external calls remain pending after crashes or expiry;
an operator must reconcile them before another paid attempt. This prevents a
blind retry from causing another charge but does not promise exactly-once effects
at an external provider. Session creation has its own reservation.

Every cached result retrieval requires a fresh invoking-user Jira access/version
check. Memory is scoped to installation, cloud, site, principal and issue. Use
the same immutable scope to route to a Durable Object. Never route by unverified
payload identifiers. Never expose ledger operations through a public unauthenticated
endpoint. No Worker entrypoint or deploy config is included yet.

Run `node --test cloudflare/*.test.mjs` with Node 24. Tests include eight independent
processes contending against a real temporary SQLite database, process restart,
uncertain dispatch, metadata minimization, user access revocation, session reuse,
scope boundaries, malformed A2A input and safe result rejection. SQLite storage
fixtures exercise the storage contract; they do not emulate Cloudflare/workerd
isolation or constitute a provider deployment test.

Before a customer pilot: actual DO/workerd integration tests; bounded storage
capacity; retention alarms and uninstall deletion; task retrieval with permission
checks; install configuration; real FIT/Jira/OpenAI clients; reliable provider
reconciliation; counters/budget limits; deterministic Python tool hosting decision.
Completed-result TTL does not implement physical deletion or a full retention
policy. Those remain SCRUM-61 acceptance criteria.

References checked 2026-09-30:

- https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/
- https://developers.cloudflare.com/durable-objects/platform/pricing/
- https://developers.openai.com/api/docs/guides/agents-api/architecture

