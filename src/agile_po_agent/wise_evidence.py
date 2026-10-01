"""Read-only, allowlisted versioned source contracts. Live execution defaults off."""
from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from agile_po_agent.wise_assess import Evidence, EvidenceKind, Scope


def turkish_candidates(description: str) -> list[dict[str, Any]]:
    """Candidate text is untrusted, untyped and never authorizes Ready or tools."""
    if len(description.encode()) > 64_000:
        return []
    lines = description.splitlines()
    return [{"line": index + 1, "text": line.strip()[:2000], "kind": None,
             "human_review_required": True}
            for index, line in enumerate(lines)
            if line.strip() and not line.startswith("#")][:32]


class _PlainText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


class VersionedCollectors:
    """Operator-selected refs only; no link crawling, redirects, writes or retries.

    Explicit enablement and source allowlists are independent of a Jira token.
    Mock transports test the actual HTTP contract without provider authorization.
    """
    def __init__(self, scope: Scope, cloud_id: str, *, repos: set[str], pages: set[str],
                 enabled: bool = False, transport: httpx.AsyncBaseTransport | None = None):
        UUID(cloud_id)
        self.scope, self.cloud_id = scope, cloud_id
        self.repos = {repo.lower() for repo in repos}
        self.pages, self.enabled, self.transport = pages, enabled, transport

    async def _get(self, url: str, token: str, github: bool = False) -> tuple[str, Any]:
        if not self.enabled or not token:
            raise PermissionError("Explicit source access authorization required")
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        if github:
            headers.update({"Accept": "application/vnd.github+json",
                            "X-GitHub-Api-Version": "2026-03-10"})
        async with (
            httpx.AsyncClient(transport=self.transport, follow_redirects=False,
                             timeout=10.0) as client,
            client.stream("GET", url, headers=headers) as response,
        ):
            if response.status_code in {401, 403}:
                return "denied", None
            if response.status_code != 200:
                return "missing", None
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > 256_000:
                    raise ValueError("Source response exceeds limit")
            return "available", json.loads(body)

    def _evidence(self, source: str, kind: EvidenceKind, uri: str, access: str,
                  version: str | None = None, finding: str = "", stale: bool = False) -> Evidence:
        return Evidence(scope=self.scope, source_id=source, kind=kind, uri=uri,
                        access=access, version=version, finding=finding[:2000],
                        observed_at=datetime.now(timezone.utc),
                        freshness="stale" if stale else "current" if version else "unknown")

    async def github_file(self, repo: str, commit: str, path: str, token: str) -> Evidence:
        if (not re.fullmatch(r"[\w.-]+/[\w.-]+", repo) or repo.lower() not in self.repos
                or not re.fullmatch(r"[a-fA-F0-9]{40}", commit)
                or not path or len(path) > 512 or not re.fullmatch(r"[\w./-]+", path)
                or any(part in {"", ".", ".."} for part in path.split("/"))):
            raise ValueError("Unapproved repository/immutable file reference")
        uri = f"https://github.com/{repo}/blob/{commit}/{quote(path, safe='/')}"
        access, raw = await self._get(
            f"https://api.github.com/repos/{repo}/contents/{quote(path, safe='/')}?ref={commit}",
            token, github=True,
        )
        if access != "available":
            return self._evidence("repository-file", EvidenceKind.REPOSITORY, uri, access)
        if (not isinstance(raw, dict) or raw.get("type") != "file" or raw.get("path") != path
                or raw.get("encoding") != "base64" or not isinstance(raw.get("content"), str)):
            raise ValueError("Repository file contract mismatch")
        text = base64.b64decode(raw["content"].replace("\n", ""), validate=True).decode("utf-8")
        if not text.strip():
            return self._evidence("repository-file", EvidenceKind.REPOSITORY, uri, "missing")
        return self._evidence("repository-file", EvidenceKind.REPOSITORY, uri,
                              "available", commit, text)

    async def github_checks(self, repo: str, commit: str, token: str) -> Evidence:
        if (not re.fullmatch(r"[\w.-]+/[\w.-]+", repo) or repo.lower() not in self.repos
                or not re.fullmatch(r"[a-fA-F0-9]{40}", commit)):
            raise ValueError("Unapproved repository/commit")
        uri = f"https://github.com/{repo}/commit/{commit}"
        access, raw = await self._get(
            f"https://api.github.com/repos/{repo}/commits/{commit}/check-runs?per_page=30",
            token, github=True,
        )
        if access != "available":
            return self._evidence("repository-ci", EvidenceKind.REPOSITORY, uri, access)
        runs = raw.get("check_runs") if isinstance(raw, dict) else None
        if (not isinstance(runs, list) or not runs or len(runs) > 30
                or raw.get("total_count") != len(runs)):
            return self._evidence("repository-ci", EvidenceKind.REPOSITORY, uri, "missing")
        if any(not isinstance(run, dict) for run in runs):
            raise ValueError("Invalid CI contract")
        complete = sum(run.get("status") == "completed" for run in runs)
        failed = sum(run.get("conclusion") in {"failure", "cancelled", "timed_out"}
                     for run in runs)
        stale = any(run.get("head_sha") != commit for run in runs)
        return self._evidence("repository-ci", EvidenceKind.REPOSITORY, uri, "available",
                              commit, f"CI: {complete}/{len(runs)} completed; {failed} failed. "
                              "Test coverage and code correctness are not implied.", stale=stale)

    async def confluence_page(self, page: str, version: int, user_token: str) -> Evidence:
        if (page not in self.pages or not re.fullmatch(r"[1-9][0-9]{0,19}", page)
                or type(version) is not int or version < 1):
            raise ValueError("Unapproved page/version")
        uri = f"https://{self.scope.site}/wiki/pages/{page}"
        access, raw = await self._get(
            f"https://api.atlassian.com/ex/confluence/{self.cloud_id}/wiki/api/v2/pages/{page}"
            "?body-format=storage&status=current", user_token,
        )
        if access != "available":
            return self._evidence("product-page", EvidenceKind.PRODUCT_DOCUMENT, uri, access)
        if not isinstance(raw, dict) or str(raw.get("id")) != page:
            raise ValueError("Confluence page identity mismatch")
        actual = raw.get("version", {}).get("number")
        body = raw.get("body", {}).get("storage", {}).get("value")
        if type(actual) is not int or not isinstance(body, str):
            raise ValueError("Confluence version/body missing")
        plain = _PlainText()
        plain.feed(body)
        finding = " ".join(plain.parts).strip()
        if not finding:
            return self._evidence("product-page", EvidenceKind.PRODUCT_DOCUMENT, uri, "missing")
        return self._evidence("product-page", EvidenceKind.PRODUCT_DOCUMENT, uri,
                              "available", str(actual), finding,
                              stale=actual != version or raw.get("status") != "current")
