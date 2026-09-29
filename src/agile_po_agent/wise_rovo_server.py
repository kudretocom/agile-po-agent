"""ASGI entrypoint for an explicitly configured, non-production Wise Rovo pilot."""

import os

from agile_po_agent.config import Settings
from agile_po_agent.wise_assess import TypeSafeClaimJudge
from agile_po_agent.wise_rovo import FitVerifier, RovoPilot


def build_app() -> RovoPilot:
    app_id = os.environ.get("FORGE_APP_ID", "")
    if not app_id:
        raise RuntimeError("FORGE_APP_ID must be set for the Rovo pilot")
    settings = Settings()
    return RovoPilot(
        FitVerifier(app_id, "wise-a2a-endpoint"),
        settings,
        TypeSafeClaimJudge(settings),
    )


app = build_app()
