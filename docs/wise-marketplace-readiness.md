# Wise Jira remote-agent publication package — draft

Reviewed 2026-09-30. Not an application submission or provider approval.

## Destination and eligibility

The existing product contract points to the [Jira agents collection](https://marketplace.atlassian.com/collections/jira-agents).
It currently presents AGENT-tagged Jira remote-agent apps. The selected technical
route is a dedicated Forge `rovo:agentConnector` registering externally hosted
Wise, with A2A 1.0. [Connector reference](https://developer.atlassian.com/platform/forge/manifest-reference/modules/rovo-agent-connector/).
Native Forge Rovo agents/actions and custom Studio agents with MCP are different
options; they do not replace the agreed remote Wise/OpenAI session architecture.
Collection inclusion is not guaranteed by an ordinary Marketplace app submission.
Confirm the applicable agent category/collection placement during provider review.

A remote-agent Forge app may be installed directly on the developer's own site
or distributed through Marketplace. [Remote-agent guide](https://developer.atlassian.com/platform/forge/remote-agents-in-jira/).
For a contributor-only nonprod pilot use direct installation, without public
sharing. Sharing links involve Forge production deployment and distribution
settings; this must not be silently used for the nonprod test.
[Distribution guide](https://developer.atlassian.com/platform/forge/distribute-your-apps/).

Public listings require approval, partner verification, privacy/security review
and applicable security tickets. Authentication for public apps cannot rely on
Basic auth. Partner Agreement acceptance is a separate owner action.
[Approval guidelines](https://developer.atlassian.com/platform/marketplace/app-approval-guidelines/).

## Proposed listing copy (publish only after installed behavior is verified)

**Working name:** Wise — Evidence-based readiness for Jira

**Tagline:** Assess Jira work items with clear evidence gaps and next steps.

**Description:** Wise helps Product Owners and team leads review whether a Jira
work item is ready for development. It presents Ready, Needs evidence, Needs
decision or Blocked, with source references and up to three next steps. The first
release performs read-only assessment. Ready means ready for development review,
not completed work or release approval. Wise does not edit Jira fields, statuses
or comments in this release.

**External service disclosure draft:** Wise uses an externally hosted Cloudflare
service and an OpenAI agent session. Narrow semantic evidence checks may use
TypeSafe JEV. Actual account requirements, pricing, data locations and retention
must be confirmed before publication. No claim of free operation, Runs on
Atlassian certification, universal data residency or zero data retention is made.

**Not advertised as available:** Refine/Apply, automatic issue creation, Figma
editing, Slack/Teams bots, autonomous delivery, durable multi-tenant production
hosting. The current code is an offline-tested pilot and local runtime spike.

## Submission manifest

| Item | Available evidence | Remaining owner/provider action |
| --- | --- | --- |
| Code/license | Public repository, MIT license, PR #5 and local continuation | Review and merge tested code |
| Forge app/connector | Manifest template, no app ID or HTTPS remote | Dedicated app identity, approved nonprod install, actual deployment |
| Tenant/user authorization | Offline FIT/Jira boundaries, local session/replay tests | Real installed verification, configuration and lifecycle cleanup |
| Real product screenshots | None | Capture installed Wise success and missing-evidence states; do not label Figma concept as screenshot |
| Brand/logo/banner | Wise working name only | Name/trademark review and owner-approved brand assets |
| User documentation | Product contract, pilot docs, runtime README | Final installed setup/configuration/use/uninstall guide and public URL |
| Privacy/security | Data flow and scoped proposal below | Approved public policy URL, Privacy & Security tab, partner security tickets |
| Support | Repository issue tracker exists | Confirm business support URL/email, incident owner and response commitments |
| Pricing/licensing | No approved Wise pricing | Owner decision; separate external costs must be clear |
| Legal/partner identity | Not inspected/accepted | Authorized partner verification and agreement acceptance |
| Integration reviewer access | Not issued | Owner-approved temporary nonprod access through secure provider channel |

## Privacy and support policy drafting inputs

Inventory only the required issue key/summary, minimized description/claims,
issue version, source identifiers/versions, verified installation/site/user
context, assessment trace and usage metrics. Incoming FIT/user OAuth tokens are
transient credentials; do not persist or log them. Session/replay metadata is
user/issue scoped. A site-wide shared memory is prohibited. No employee/customer
records or special-category documents are needed for this pilot.

Cloudflare, OpenAI and TypeSafe are proposed processing services, not a finalized
subprocessor disclosure. Owner must approve actual hosting geography, provider
retention, lawful processing/transfer terms, deletion and incident contacts.
Suggested pilot retention is 24 hours followed by verified cleanup, but current
code does not implement a complete deletion lifecycle. Marketing policy text
must describe deployed behavior. Support guide must explain source missing vs
denied vs stale, safe retries, account revocation, uninstall cleanup and how to
report an incorrect assessment without submitting sensitive payloads.

No production publication, payment, partner agreement, OAuth grant, credential
creation or permission expansion has been performed.

