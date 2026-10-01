"""Local-only test entry. Never select this file for a deployed service."""
import json

from entry import Default as InternalTool
from workers import Response


class Default(InternalTool):
    async def fetch(self, request):
        data = await request.json()
        result = await self.assess(
            json.dumps(data["scope"]), json.dumps(data["snapshot"]),
        )
        return Response(result, headers={"Content-Type": "application/json"})
