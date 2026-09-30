# Bounded nonprod pilot handoff — proposed, not authorized

Target Jira nonprod **site URL is pending user response**. The only connected site
observed is operoner.atlassian.net; it is not assumed to be a test site. Existing
SCRUM-32 was read through the authorized connector and minimized for offline
testing. No installation, OAuth grant or spend has occurred.

| Provider/action | Exact proposed scope | Persistence/cost/reuse |
| --- | --- | --- |
| Atlassian Forge | Register dedicated `wise-read-only-pilot`; deploy development environment; contributor-only Jira installation on the user-confirmed nonprod site; `read:app-user-token` + `read:jira-work`; HTTPS compute remote only | App identity/install persists until removed. Reuse existing developer login if authorized; no Basic API token reuse, system-user fallback, public sharing or write scope. Actual consent screen is reviewed before acceptance. |
| Cloudflare | Dedicated nonprod Worker + SQLite Durable Object namespace; route `/a2a/json-rpc`; metadata store only; secret binding for Wise-specific provider keys | Persistent Worker/DO configuration; proposed 24h data retention and verified deletion after pilot. Existing Cloudflare login may be reused through official handoff. Start with available Free tier, no paid plan purchase. SQLite DO is available on Free; usage limits/errors apply. |
| OpenAI | One Wise nonprod agent definition; session scoped to installation/site/principal/issue; `environment.type:none`; read-only evidence tools, no executor, MCP grant, code editing or hosted sandbox | Agent/session retained under provider policy. Reuse only a confirmed Wise nonprod project-scoped key that already has necessary access. Firmam production key/project not silently reused. Otherwise owner creates narrow credential in official console and stores through approved secret path. |
| TypeSafe JEV | At most one bounded claim-to-source judgment after deterministic evidence/DoR gates pass | Existing confirmed nonprod key may be reused. No production credential or automatic quota expansion; server-side secret injection only. |
| 1Password | Confirm existing Wise nonprod item metadata or create owner-approved dedicated item; transfer directly to scoped Cloudflare secret binding | No value in conversation, Jira, fixture or logs. Firmam/GCP/Vercel production synchronization is outside scope. |

Cost proposal awaiting explicit approval: **maximum 3 Assess executions, maximum
1 JEV call, aggregate provider spend below US$1**, stop at limits. These are not
currently enforced production budget controls or user-approved spend. No call
will be made until runtime caps and selected model pricing are verified. Existing
subscriptions do not imply authorization to add paid resources.

External participants: Atlassian Jira/Rovo's installed **dedicated Wise connector**
(app ARI and agent account ID available only after authorized registration), and
the **same OpenAI Wise agent/session** (agent ID pending authorized creation).
No other Rovo/Jira agent, human recipient, Slack/Teams channel or third-party
autonomous agent is part of this proposal. If a different agent is desired,
obtain its exact ID and bounded communication authorization first.

Minimal test brief: “Assess whether the connected-grant and external-client
relationship model requires separate data/authorization evidence. Report missing
commit/schema evidence and up to three next steps. Do not edit Jira or post a
comment.” This derives from SCRUM-32, excludes people, customer records,
documents, prices and secrets. On the approved nonprod site the user chooses an
existing suitable issue or authorizes a dedicated fixture issue separately.
No noise issue is created on operoner.

Test sequence: authorized invocation; duplicate request; revoked/read-denied
fixture or bounded access-denied case. Capture source version, state, latency,
actual usage/cost and `jira_changed=false`. Compare issue fields before/after.
No production field/status/comment write, code push by the agent, external
communication beyond the named participants, public deployment or publication.

Owner uses the official Forge install consent and provider console/1Password
handoffs. A general “allow” response is insufficient to select an unknown site,
accept agreement, upgrade billing or grant broader access.

Official references checked 2026-09-30:

- https://developer.atlassian.com/platform/forge/remote-agents-in-jira/
- https://developer.atlassian.com/platform/forge/distribute-your-apps/
- https://developers.cloudflare.com/durable-objects/platform/pricing/
- https://developers.openai.com/api/docs/guides/agents-api/architecture

