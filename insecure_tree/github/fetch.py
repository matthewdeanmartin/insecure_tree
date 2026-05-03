"""Fetch GitHub Actions workflow files for a repository."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from insecure_tree.cache import Cache
from insecure_tree.github.client import GitHubAPIError, GitHubClient

log = logging.getLogger(__name__)


@dataclass
class FetchResult:
    owner: str
    repo: str
    status: str
    workflow_dir: Path | None = None
    commit_sha: str = ""
    default_branch: str = ""
    workflow_paths: list[str] = field(default_factory=list)
    error_message: str = ""


async def fetch_workflows(  # pylint: disable=too-many-return-statements
    owner: str,
    repo: str,
    *,
    client: GitHubClient,
    cache: Cache,
    ttl: int,
    tmp_base: Path,
) -> FetchResult:
    """Fetch workflow YAML files via GitHub API into a temp-like directory."""
    cache_key = f"{owner}/{repo}"

    # Check cache for repo metadata (branch + sha)
    cached_meta_raw = cache.get("github_repo", cache_key)
    cached_meta = json.loads(cached_meta_raw) if cached_meta_raw else None

    try:
        if cached_meta:
            default_branch = cached_meta["default_branch"]
            archived = cached_meta.get("archived", False)
        else:
            repo_info = await client.get_repo_info(owner, repo)
            default_branch = repo_info.get("default_branch", "main")
            archived = repo_info.get("archived", False)
            cache.put(
                "github_repo",
                cache_key,
                json.dumps(
                    {
                        "default_branch": default_branch,
                        "archived": archived,
                    }
                ),
                ttl,
            )
    except GitHubAPIError as exc:
        return FetchResult(
            owner=owner,
            repo=repo,
            status="github_api_failed",
            error_message=str(exc),
        )

    if archived:
        log.info("%s/%s is archived", owner, repo)

    # Get HEAD SHA
    sha_cache_key = f"{owner}/{repo}@{default_branch}"
    cached_sha = cache.get("github_sha", sha_cache_key)

    try:
        if cached_sha:
            commit_sha = cached_sha
        else:
            commit_sha = await client.get_default_branch_sha(owner, repo, default_branch)
            cache.put("github_sha", sha_cache_key, commit_sha, min(ttl, 3600))
    except GitHubAPIError as exc:
        return FetchResult(
            owner=owner,
            repo=repo,
            status="github_api_failed",
            error_message=str(exc),
            default_branch=default_branch,
        )

    # Check workflow content cache
    workflow_cache_key = f"{owner}/{repo}@{commit_sha}"
    cached_workflows = cache.get_json("github_workflows", workflow_cache_key)
    if cached_workflows and isinstance(cached_workflows, list) and cached_workflows:
        workflow_dir = _write_workflows(owner, repo, cached_workflows, tmp_base)
        return FetchResult(
            owner=owner,
            repo=repo,
            status="ok",
            workflow_dir=workflow_dir,
            commit_sha=commit_sha,
            default_branch=default_branch,
            workflow_paths=[w["path"] for w in cached_workflows],
        )

    # Fetch workflow list
    try:
        workflow_files = await client.list_workflow_files(owner, repo, commit_sha)
    except GitHubAPIError as exc:
        return FetchResult(
            owner=owner,
            repo=repo,
            status="github_api_failed",
            error_message=str(exc),
            default_branch=default_branch,
            commit_sha=commit_sha,
        )

    if not workflow_files:
        return FetchResult(
            owner=owner,
            repo=repo,
            status="no_workflows",
            default_branch=default_branch,
            commit_sha=commit_sha,
        )

    # Download each workflow file
    fetched: list[dict[str, str]] = []
    for wf in workflow_files:
        wf_path = wf.get("path", "")
        try:
            content = await client.get_file_content(owner, repo, wf_path, commit_sha)
            fetched.append(
                {
                    "path": wf_path,
                    "name": wf.get("name", ""),
                    "content": content.decode("utf-8", errors="replace"),
                }
            )
        except Exception as exc:
            log.warning("Failed to fetch %s/%s %s: %s", owner, repo, wf_path, exc)

    if not fetched:
        return FetchResult(
            owner=owner,
            repo=repo,
            status="no_workflows",
            default_branch=default_branch,
            commit_sha=commit_sha,
        )

    cache.put_json("github_workflows", workflow_cache_key, fetched, ttl)
    workflow_dir = _write_workflows(owner, repo, fetched, tmp_base)

    return FetchResult(
        owner=owner,
        repo=repo,
        status="ok",
        workflow_dir=workflow_dir,
        commit_sha=commit_sha,
        default_branch=default_branch,
        workflow_paths=[w["path"] for w in fetched],
    )


def _write_workflows(owner: str, repo: str, workflows: list[dict[str, str]], tmp_base: Path) -> Path:
    safe_name = f"{owner}__{repo}"
    dest = tmp_base / safe_name / ".github" / "workflows"
    dest.mkdir(parents=True, exist_ok=True)
    for wf in workflows:
        (dest / wf["name"]).write_text(wf["content"], encoding="utf-8")
    return dest.parent.parent  # Return repo root (tmp_base/owner__repo)
