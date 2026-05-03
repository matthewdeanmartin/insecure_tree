"""GitHub REST API client."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

log = logging.getLogger(__name__)

_API_BASE = "https://api.github.com"


class GitHubAPIError(Exception):
    def __init__(self, status: int, message: str) -> None:
        self.status = status
        super().__init__(f"GitHub API {status}: {message}")


class GitHubClient:
    def __init__(
        self,
        token: Optional[str],
        session: httpx.AsyncClient,
        concurrency: int = 8,
    ) -> None:
        self._token = token
        self._session = session
        self._sem = asyncio.Semaphore(concurrency)

    def _headers(self) -> Dict[str, str]:
        h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    async def _get(self, path: str) -> Any:
        async with self._sem:
            url = f"{_API_BASE}{path}"
            resp = await self._session.get(url, headers=self._headers())

            remaining = int(resp.headers.get("X-RateLimit-Remaining", "1"))
            if remaining == 0:
                reset_at = int(resp.headers.get("X-RateLimit-Reset", "0"))
                import time
                wait = max(0.0, reset_at - time.time()) + 1
                log.warning("GitHub rate limit hit; sleeping %.1fs", wait)
                await asyncio.sleep(wait)

            if resp.status_code == 404:
                raise GitHubAPIError(404, f"Not found: {path}")
            if resp.status_code == 403:
                raise GitHubAPIError(403, f"Forbidden (rate limit or auth): {path}")
            if resp.status_code >= 400:
                raise GitHubAPIError(resp.status_code, resp.text[:200])

            return resp.json()

    async def get_repo_info(self, owner: str, repo: str) -> Dict[str, Any]:
        """Return repository metadata dict from GitHub API."""
        return await self._get(f"/repos/{owner}/{repo}")  # type: ignore[return-value]

    async def get_default_branch_sha(self, owner: str, repo: str, branch: str) -> str:
        """Return the HEAD commit SHA for the default branch."""
        data = await self._get(f"/repos/{owner}/{repo}/git/refs/heads/{branch}")
        if isinstance(data, list):
            data = data[0]
        return str(data["object"]["sha"])

    async def list_workflow_files(self, owner: str, repo: str, ref: str) -> List[Dict[str, Any]]:
        """List .yml/.yaml files in .github/workflows at the given ref."""
        try:
            items = await self._get(f"/repos/{owner}/{repo}/contents/.github/workflows?ref={ref}")
        except GitHubAPIError as exc:
            if exc.status == 404:
                return []
            raise
        if not isinstance(items, list):
            return []
        return [i for i in items if isinstance(i, dict) and i.get("name", "").endswith((".yml", ".yaml"))]

    async def get_file_content(self, owner: str, repo: str, path: str, ref: str) -> bytes:
        """Return the raw file content at the given path and ref."""
        data = await self._get(f"/repos/{owner}/{repo}/contents/{path}?ref={ref}")
        if isinstance(data, dict) and data.get("encoding") == "base64":
            import base64
            content = data.get("content", "").replace("\n", "")
            return base64.b64decode(content)
        # Fallback: raw download_url
        download_url = data.get("download_url") if isinstance(data, dict) else None
        if download_url:
            resp = await self._session.get(download_url, headers=self._headers())
            return resp.content
        return b""
