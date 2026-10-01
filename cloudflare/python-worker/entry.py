"""Internal Python Workers RPC entrypoint. No public HTTP route."""
import json

from workers import Response, WorkerEntrypoint

from agile_po_agent.config import Settings
from agile_po_agent.wise_assess import TypeSafeClaimJudge
from agile_po_agent.wise_tool import assess_verified_snapshot


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        return Response("Not found", status=404)

    async def assess(self, scope_json: str, snapshot_json: str) -> str:
        if len(scope_json.encode()) > 4096 or len(snapshot_json.encode()) > 256_000:
            raise ValueError("Tool input exceeds limit")
        result = await assess_verified_snapshot(json.loads(scope_json), json.loads(snapshot_json))
        return json.dumps(result)

    async def assessWithJev(self, scope_json: str, snapshot_json: str) -> str:
        if getattr(self.env, "WISE_JEV_EXECUTION_ENABLED", "false") != "true":
            raise PermissionError("Live JEV execution has not been authorized")
        if len(scope_json.encode()) > 4096 or len(snapshot_json.encode()) > 256_000:
            raise ValueError("Tool input exceeds limit")
        settings = Settings(typesafe_api_key=self.env.WISE_TYPESAFE_API_KEY,
                            typesafe_environment=self.env.WISE_TYPESAFE_ENVIRONMENT)
        judge = TypeSafeClaimJudge(settings)
        result = await assess_verified_snapshot(
            json.loads(scope_json), json.loads(snapshot_json), judge,
        )
        return json.dumps(result)
