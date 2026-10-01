# User-selected AE assessment — 2026-10-01

Authorized read-only Jira discovery found SCRUM-72 epic and SCRUM-73 task on
operoner.atlassian.net, project SCRUM. Snapshot versions were respectively
2026-10-01T09:41:43.212+0300 and 2026-10-01T09:44:24.505+0300.
The same actual descriptions were assessed before and after the Wise fix.
No AE repository or Jira issue was changed, and no AI/JEV call was made.

Initial Wise output missed declared acceptance criteria because the strict
JiraTaskDraft schema does not normalize Turkish free text. The correction
extracts explicitly headed “Kabul”, “Kabul kriterleri/ölçütleri/şartları” and
“Acceptance criteria” into bounded candidates, including inline paragraphs,
multiline bullets, bold/Markdown headings and numbered items. It stops at the
next named section. Every candidate is unverified and requires human review;
no typed claim, source citation or normalized JiraTaskDraft is invented.

After the correction SCRUM-73 has six criteria candidates (transaction order,
VAT, post roles, DB regressions, review/CI, no production write), and SCRUM-72
has four. Both explicitly report declared criteria present while remaining
needs_evidence; jira_changed=false and jev_required=false. This is not a
criteria-absence finding or an assessment of implementation completion.
SCRUM-73 regression fixture is the actual source description, without people,
customer or ledger records. Eleven new cases test extraction, section bounds,
input limits, absence of invented criteria and preservation of evidence gates.

Owner supplied AE source base 3bb83366cb5390c67367977668d01e2ba969f81c and noted
development is ongoing with no PR yet. That is provenance, not code/test proof.
Missing future PR/test evidence is expected at this stage, not a task defect.
When available, the resulting commit/schema and terminal DB/role/tenant tests
can be assessed separately using authorized versioned source evidence.

Local verification: 98 Python tests, 28 Node tests, Ruff and mypy (17 source
files) pass. Exact-head CI is tracked on PR6. This is real-input offline
assessment, not installed Forge FIT, live OpenAI/Rovo A2A or Marketplace release
acceptance. The AE-specific live proposal and explicit authorization gaps are
in wise-nonprod-approval-handoff.md.
