# Bounded nonprod pilot handoff — proposed, not authorized

User selected AE development in **operoner.atlassian.net / SCRUM / SCRUM-73**.
The site URL is known; permission for a development Forge install on this site
remains unconfirmed, and it is not assumed to be a test site. Existing
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


## Runtime implementation update (2026-10-01)

Local Workers/RPC/DO evidence now exists; it does not grant deployment access.
The proposed install includes the same read-only scopes plus a dedicated
preUninstall remote endpoint. Local metadata includes task issue keys for fresh
permission checks, hashed scope/message/version, claim/task/session IDs and
allowance counters. OpenAI session memory is retired at the proposed TTL; remote
physical deletion and uncertain attempts require the demonstrated reconciliation
process. Confirm this retention/data-processing scope in the concrete handoff.
Runtime enablement, Assess/session/JEV allowances, JEV execution and retention
provider deletion each default to disabled/unconfigured. Call counts are not a
USD ceiling; constrain the approved provider agent/model/project budget too.

## User-selected AE scenario (2026-10-01)

This scenario supersedes the SCRUM-32 brief above. Use existing SCRUM-73 only,
with SCRUM-72 epic as optional context. Brief: “Assess daily accounting
transaction order, VAT expected 40 and post-role boundaries against supplied
versioned development evidence. Report missing evidence and up to three next
steps. Do not edit Jira or post comments.” No accounting records, customer data,
employee data or credentials are shared. AE code and Jira remain unchanged.

Data recipients are: Atlassian (issue and invoking-user context); the dedicated
Cloudflare remote/Python tool (minimal issue snapshot and transient user token
for authorized Jira read); the same OpenAI Wise agent/session (minimal brief
and deterministic function result, never OAuth tokens); TypeSafe only if a
separate explicit JEV authorization is granted. First AE live-test proposal
keeps JEV and optional GitHub/Confluence source access OFF.

Smallest proposal is one Assess plus one identical replay; aggregate AI spend
at most US$1, **not approved**. A selected model, token bounds and enforceable
provider/project budget must be confirmed before enabling network execution;
call caps alone cannot guarantee the dollar limit. No paid plan upgrade.

Existing Jira connector read access already supports the executed local test.
It does not expose Forge install inventory or prove an installed Wise connector.
For credential reuse discovery, owner supplies metadata only: existing Wise
Forge app ARI, development environment/installation and remote endpoint;
Cloudflare account/project; existing Wise OpenAI agent ID/project; confirmation
that existing scoped credentials can be reused. Values are never requested in
chat. Manifest still contains placeholder app/remote identity, so actual
participant IDs cannot currently be named. Do not fabricate them or contact
another Rovo agent. If reuse is unavailable, the registration/install, exact
read-only consent and official secret binding actions in the table above
require scoped approval. AE test selection grants none of those actions.
