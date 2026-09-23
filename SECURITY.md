# Security Policy

Do not report live API keys, Jira tokens, secret-manager references, or customer data in public issues.

Never use a production TypeSafe credential for a non-production Jev smoke test. Inject approved credentials at runtime; do not store them in files, logs, Jira, or test fixtures.

The application must fail closed when:

- a Jev response is missing or malformed;
- a Jira target is ambiguous;
- a required human approval is absent;
- a path escapes the configured repository boundary;
- deterministic quality or test gates fail.

Jira writes are dry-run by default and require an explicit `--confirm` flag. AI-generated `allow` decisions never replace user authorization.

Jev errors are sanitized. Do not add upstream bodies, request headers, credentials, or state payloads to logs. `ready_to_ship` remains advisory and cannot replace tests, lint, typecheck, zero blockers, or human approval.
