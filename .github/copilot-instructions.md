# Copilot instructions

Build a public-quality Agile product-owner agent with Python and Microsoft AutoGen AgentChat.

- Read `docs/COPILOT_BUILD_PROMPT.md` and `docs/architecture.md` before changing code.
- Use stable AutoGen `0.7.5`; do not follow `dev/main` examples without verifying them against stable docs.
- Keep AutoGen generation, Jev decisions, deterministic gates, and Jira side effects in separate modules.
- Use one bounded `AssistantAgent` session per issue; do not add unbounded group chats.
- Split web and repository context into separate Noul questions.
- Combine Jev readiness with deterministic test, lint, typecheck, blocker, and approval gates.
- Keep Jira writes dry-run by default.
- Never commit secrets, secret-manager paths, private Jira metadata, or customer data.
- Add tests for every behavior change and run Ruff, mypy, and pytest.

