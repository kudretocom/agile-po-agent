"""Internal Python Workers RPC entrypoint. No public HTTP route."""
import json

from workers import Response, WorkerEntrypoint

from agile_po_agent.config import Settings
from agile_po_agent.wise_assess import TypeSafeClaimJudge
from agile_po_agent.wise_source_plan import collect_source_plan
from agile_po_agent.wise_tool import assess_verified_snapshot


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        return Response("Not found", status=404)

    async def assess(self, scope_json: str, snapshot_json: str, user_token: str = "") -> str:
        if len(scope_json.encode()) > 4096 or len(snapshot_json.encode()) > 256_000:
            raise ValueError("Tool input exceeds limit")
        scope = json.loads(scope_json)
        evidence = await self.source_evidence(scope, user_token)
        result = await assess_verified_snapshot(scope, json.loads(snapshot_json),
                                                additional_evidence=evidence)
        return json.dumps(result)

    async def assessWithJev(self, scope_json: str, snapshot_json: str,
                            user_token: str = "") -> str:
        if getattr(self.env, "WISE_JEV_EXECUTION_ENABLED", "false") != "true":
            raise PermissionError("Live JEV execution has not been authorized")
        if len(scope_json.encode()) > 4096 or len(snapshot_json.encode()) > 256_000:
            raise ValueError("Tool input exceeds limit")
        settings = Settings(typesafe_api_key=self.env.WISE_TYPESAFE_API_KEY,
                            typesafe_environment=self.env.WISE_TYPESAFE_ENVIRONMENT)
        judge = TypeSafeClaimJudge(settings)
        scope = json.loads(scope_json)
        evidence = await self.source_evidence(scope, user_token)
        result = await assess_verified_snapshot(
            scope, json.loads(snapshot_json), judge, additional_evidence=evidence,
        )
        return json.dumps(result)

    async def source_evidence(self, scope, user_token):
        if getattr(self.env, "WISE_SOURCES_ENABLED", "false") != "true":
            return []
        if len(user_token) > 16_000:
            raise ValueError("User token exceeds limit")
        return await collect_source_plan(
            scope, self.env.WISE_SOURCE_PLAN_JSON,
            github_token=getattr(self.env, "WISE_GITHUB_READ_TOKEN", ""),
            user_token=user_token, enabled=True,
        )
