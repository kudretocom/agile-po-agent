"""Product-owner prompts kept short, explicit, and reusable."""

PO_SYSTEM_PROMPT = """
You are an expert Agile Product Owner. Convert an incomplete product brief into one small,
valuable, independently reviewable Jira work item.

Start from the user problem and desired outcome. Do not invent technical facts, project keys,
estimates, priorities, dependencies, or implementation details. Prefer a thin vertical slice.
Write observable Given/When/Then acceptance criteria and name the evidence that proves each one.
Separate scope from non-goals. Include a concrete test plan, risks, rollout, success metrics, and
open questions. Mark uncertainty explicitly. Return only the requested structured output.
""".strip()


def draft_task_prompt(brief_json: str) -> str:
    return f"Create one Definition-of-Ready Jira work item from this brief:\n\n{brief_json}"


def revise_task_prompt(draft_json: str, failures: list[str]) -> str:
    feedback = "\n".join(f"- {failure}" for failure in failures)
    return (
        "Revise the Jira work item to resolve only the listed quality failures. "
        "Preserve valid information and do not invent facts.\n\n"
        f"Current draft:\n{draft_json}\n\nQuality failures:\n{feedback}"
    )

