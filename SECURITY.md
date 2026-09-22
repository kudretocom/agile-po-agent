# Security Policy

Do not report live API keys, Jira tokens, secret-manager references, or customer data in public issues.

The application must fail closed when:

- a Jev response is missing or malformed;
- a Jira target is ambiguous;
- a required human approval is absent;
- a path escapes the configured repository boundary;
- deterministic quality or test gates fail.

Jira writes are dry-run by default and require an explicit `--confirm` flag. AI-generated `allow` decisions never replace user authorization.

