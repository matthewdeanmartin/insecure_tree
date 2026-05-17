"""Full scan pipeline: discovery → metadata → GitHub → zizmor → report."""

from __future__ import annotations

import asyncio
import datetime
import logging
import tempfile
from pathlib import Path

import httpx

from insecure_tree.__about__ import __version__
from insecure_tree.adapters.base import AdapterOptions, BaseAdapter
from insecure_tree.adapters.pip_inspect import PipInspectAdapter
from insecure_tree.adapters.pipdeptree import PipdeptreeAdapter
from insecure_tree.adapters.requirements import RequirementsAdapter
from insecure_tree.adapters.uv import UvAdapter
from insecure_tree.adapters.uv_pip import UvPipAdapter
from insecure_tree.cache import Cache
from insecure_tree.config import Config
from insecure_tree.github.client import GitHubClient
from insecure_tree.github.fetch import FetchResult, fetch_workflows
from insecure_tree.metadata.github_urls import extract_github_candidates, select_best_candidate
from insecure_tree.metadata.local import read_local_dist_metadata
from insecure_tree.metadata.pypi import fetch_pypi_metadata
from insecure_tree.models import (
    DependencyGraph,
    PackageNode,
    PatternFinding,
    Report,
    ReportSummary,
    ScanResult,
    ScanStatus,
    SourceAdapter,
)
from insecure_tree.scanners.workflow_patterns import PatternMatch, detect_pwn_request
from insecure_tree.scanners.zizmor import ScanInfraError, run_zizmor

log = logging.getLogger(__name__)


def _auto_detect_adapter(options: AdapterOptions, _config: Config) -> BaseAdapter:
    ordered: list[BaseAdapter] = [
        UvAdapter(),
        UvPipAdapter(),
        PipInspectAdapter(),
        PipdeptreeAdapter(),
        RequirementsAdapter(),
    ]
    for adapter in ordered:
        if adapter.detect(options):
            log.info("Auto-detected adapter: %s", type(adapter).__name__)
            return adapter
    raise RuntimeError("Could not detect a dependency source. Pass --source explicitly.")


def _choose_adapter(source: SourceAdapter, options: AdapterOptions, config: Config) -> BaseAdapter:
    mapping: dict[SourceAdapter, BaseAdapter] = {
        SourceAdapter.uv: UvAdapter(),
        SourceAdapter.uv_pip: UvPipAdapter(),
        SourceAdapter.pip_inspect: PipInspectAdapter(),
        SourceAdapter.pipdeptree: PipdeptreeAdapter(),
        SourceAdapter.requirements: RequirementsAdapter(),
    }
    if source == SourceAdapter.auto:
        return _auto_detect_adapter(options, config)
    adapter = mapping.get(source)
    if adapter is None:
        raise ValueError(f"Unsupported source: {source}")
    return adapter


async def _resolve_metadata(
    pkg: PackageNode,
    session: httpx.AsyncClient,
    cache: Cache,
    meta_ttl: int,
    sem: asyncio.Semaphore,
) -> PackageNode:
    async with sem:
        # Try local first
        local = read_local_dist_metadata(pkg.name)
        if local:
            pkg = pkg.model_copy(update={"metadata": local})
        else:
            pypi_meta = await fetch_pypi_metadata(
                pkg.name,
                pkg.version or None,
                session=session,
                cache=cache,
                ttl=meta_ttl,
            )
            if pypi_meta:
                pkg = pkg.model_copy(update={"metadata": pypi_meta})

        if pkg.metadata:
            candidates = extract_github_candidates(pkg.metadata)
            selected = select_best_candidate(candidates)
            pkg = pkg.model_copy(update={"repo_candidates": candidates, "selected_repo": selected})

    return pkg


async def _fetch_and_scan(
    owner: str,
    repo: str,
    gh_client: GitHubClient,
    cache: Cache,
    repo_ttl: int,
    tmp_dir: Path,
    config: Config,
) -> tuple[str, ScanResult]:
    repo_key = f"{owner}/{repo}"

    if config.no_clone:
        return repo_key, ScanResult(status=ScanStatus.skipped, error_message="--no-clone set")

    fetch_result: FetchResult = await fetch_workflows(
        owner,
        repo,
        client=gh_client,
        cache=cache,
        ttl=repo_ttl,
        tmp_base=tmp_dir,
    )

    if fetch_result.status == "no_workflows":
        return repo_key, ScanResult(
            status=ScanStatus.no_workflows,
            repo_ref=f"{owner}/{repo}@{fetch_result.commit_sha}",
        )
    if fetch_result.status != "ok" or fetch_result.workflow_dir is None:
        return repo_key, ScanResult(
            status=ScanStatus.github_api_failed,
            error_message=fetch_result.error_message,
        )

    # Pattern detection on raw workflow content (no zizmor needed)
    wf_cache_key = f"{owner}/{repo}@{fetch_result.commit_sha}"
    raw_workflows: list[dict[str, str]] = cache.get_json("github_workflows", wf_cache_key) or []
    pattern_matches: list[PatternMatch] = detect_pwn_request(raw_workflows)
    pattern_findings: list[PatternFinding] = [
        PatternFinding(
            rule_id=m.RULE_ID,
            workflow_name=m.workflow_name,
            workflow_path=m.workflow_path,
            job_name=m.job_name,
            step_index=m.step_index,
            uses=m.uses,
            message=m.message,
        )
        for m in pattern_matches
    ]

    try:
        scan_result = await run_zizmor(
            fetch_result.workflow_dir,
            owner=owner,
            repo=repo,
            commit_sha=fetch_result.commit_sha,
            zizmor_bin=config.zizmor.bin,
            extra_args=config.zizmor.args,
            cache=cache,
            timeout=120.0,
        )
    except ScanInfraError:
        raise  # Propagate missing zizmor as infrastructure error
    except Exception as exc:
        scan_result = ScanResult(status=ScanStatus.zizmor_failed, error_message=str(exc))

    if pattern_findings:
        scan_result = scan_result.model_copy(update={"pattern_findings": pattern_findings})

    return repo_key, scan_result


async def run_scan(config: Config) -> Report:
    """Execute the full pipeline and return a Report."""
    project_path = Path(config.project).resolve()
    options = AdapterOptions(
        project_path=project_path,
        python=config.python,
        depth=config.depth,
        include_dev=config.include_dev,
        requirements_files=config.requirements,
        timeout=config.timeout,
    )

    # Step 1: Build dependency graph
    adapter = _choose_adapter(config.source, options, config)
    graph: DependencyGraph = adapter.fetch(options)
    log.info("Graph: %d nodes, %d edges", len(graph.nodes), len(graph.edges))

    # Apply repo overrides and ignore packages
    nodes = graph.nodes

    cache = Cache() if not config.no_cache else _NullCache()
    token = config.github.token or _read_token(config.github.token_env)

    async with httpx.AsyncClient(timeout=config.timeout) as session:
        gh_client = GitHubClient(token, session, config.github_concurrency)

        # Step 2: Resolve package metadata + GitHub candidates
        meta_sem = asyncio.Semaphore(config.concurrency)
        resolved_nodes: list[PackageNode] = await asyncio.gather(
            *[_resolve_metadata(pkg, session, cache, config.metadata_ttl, meta_sem) for pkg in nodes]
        )

        # Apply config repo overrides
        overridden: list[PackageNode] = []
        for pkg in resolved_nodes:
            norm = pkg.normalized_name
            if norm in config.repo_overrides or pkg.name in config.repo_overrides:
                override_url = config.repo_overrides.get(norm) or config.repo_overrides.get(pkg.name, "")
                from insecure_tree.metadata.github_urls import _normalize_clone_url, _parse_github

                parsed = _parse_github(override_url)
                if parsed:
                    from insecure_tree.models import ConfidenceLevel, RepoCandidate

                    o, r = parsed
                    cand = RepoCandidate(
                        url=f"https://github.com/{o}/{r}",
                        owner=o,
                        repo=r,
                        source_field="config_override",
                        confidence=ConfidenceLevel.high,
                        reason="User-configured repo override",
                        normalized_clone_url=_normalize_clone_url(o, r),
                    )
                    pkg = pkg.model_copy(update={"selected_repo": cand, "repo_candidates": [cand]})
            overridden.append(pkg)
        resolved_nodes = overridden

        # Step 3: Deduplicate repos
        repo_to_packages: dict[str, list[int]] = {}
        for i, pkg in enumerate(resolved_nodes):
            if pkg.selected_repo:
                key = f"{pkg.selected_repo.owner}/{pkg.selected_repo.repo}"
                repo_to_packages.setdefault(key, []).append(i)

        # Step 4 & 5: Fetch workflows and run zizmor (once per unique repo)
        if not config.offline:
            with tempfile.TemporaryDirectory(prefix="insecure-tree-") as tmp:
                tmp_path = Path(tmp)
                gh_sem = asyncio.Semaphore(config.github_concurrency)

                async def fetch_one(owner: str, repo: str) -> tuple[str, ScanResult]:
                    async with gh_sem:
                        return await _fetch_and_scan(owner, repo, gh_client, cache, config.repo_ttl, tmp_path, config)

                unique_repos = list(repo_to_packages.keys())
                results = await asyncio.gather(
                    *[fetch_one(rk.split("/")[0], rk.split("/")[1]) for rk in unique_repos],
                    return_exceptions=True,
                )

                repo_results: dict[str, ScanResult] = {}
                for rk, result in zip(unique_repos, results, strict=False):
                    if isinstance(result, ScanInfraError):
                        raise result
                    if isinstance(result, Exception):
                        repo_results[rk] = ScanResult(status=ScanStatus.zizmor_failed, error_message=str(result))
                    elif isinstance(result, tuple):
                        _, scan = result
                        repo_results[rk] = scan
                    else:
                        repo_results[rk] = ScanResult(status=ScanStatus.zizmor_failed, error_message=str(result))
        else:
            repo_results = {}

        # Step 6: Fan results back to packages
        final_nodes: list[PackageNode] = []
        for pkg in resolved_nodes:
            if pkg.selected_repo:
                rk = f"{pkg.selected_repo.owner}/{pkg.selected_repo.repo}"
                repo_scan = repo_results.get(rk)
                if repo_scan:
                    pkg = pkg.model_copy(update={"scan": repo_scan})
                else:
                    pkg = pkg.model_copy(update={"scan": ScanResult(status=ScanStatus.no_repo)})
            elif not config.offline:
                pkg = pkg.model_copy(update={"scan": ScanResult(status=ScanStatus.no_repo)})
            final_nodes.append(pkg)

    # Build summary
    summary = _build_summary(final_nodes)
    zizmor_ver = _first_zizmor_version(final_nodes)

    return Report(
        project_path=str(project_path),
        source_adapter=graph.source.value,
        scan_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        insecure_tree_version=__version__,
        zizmor_version=zizmor_ver,
        summary=summary,
        packages=final_nodes,
        graph=graph,
        has_findings_above_threshold=_check_threshold(summary, config.fail_on),
        has_partial_failures=any(
            p.scan and p.scan.status in (ScanStatus.github_api_failed, ScanStatus.zizmor_failed) for p in final_nodes
        ),
    )


def _build_summary(nodes: list[PackageNode]) -> ReportSummary:
    with_github = sum(1 for n in nodes if n.selected_repo)
    scanned = sum(1 for n in nodes if n.scan and n.scan.status == ScanStatus.scanned)
    no_wf = sum(1 for n in nodes if n.scan and n.scan.status == ScanStatus.no_workflows)
    with_findings = sum(1 for n in nodes if n.scan and n.scan.finding_count > 0)
    skipped = sum(1 for n in nodes if n.scan and n.scan.status in (ScanStatus.skipped, ScanStatus.skipped_cached))
    failed = sum(
        1 for n in nodes if n.scan and n.scan.status in (ScanStatus.github_api_failed, ScanStatus.zizmor_failed)
    )
    by_sev: dict[str, int] = {}
    pwn_count = 0
    for n in nodes:
        if n.scan:
            for sev, cnt in n.scan.findings_by_severity.items():
                by_sev[sev] = by_sev.get(sev, 0) + cnt
            pwn_count += len(n.scan.pattern_findings)
    return ReportSummary(
        total_packages=len(nodes),
        packages_with_github=with_github,
        repos_scanned=scanned,
        repos_no_workflows=no_wf,
        repos_with_findings=with_findings,
        findings_by_severity=by_sev,
        pwn_request_count=pwn_count,
        skipped=skipped,
        failed=failed,
    )


def _first_zizmor_version(nodes: list[PackageNode]) -> str | None:
    for n in nodes:
        if n.scan and n.scan.zizmor_version:
            return n.scan.zizmor_version
    return None


def _check_threshold(summary: ReportSummary, fail_on: str) -> bool:
    if fail_on == "never":
        return False
    sev_order = ["note", "warning", "error"]
    if fail_on not in sev_order:
        return False
    threshold_idx = sev_order.index(fail_on)
    return any(summary.findings_by_severity.get(sev, 0) > 0 for sev in sev_order[threshold_idx:])


def _read_token(env_var: str) -> str | None:
    import os

    return os.environ.get(env_var) or None


class _NullCache(Cache):  # pylint: disable=super-init-not-called
    """Cache that never stores anything."""

    def __init__(self) -> None:  # pylint: disable=super-init-not-called
        pass

    def get(self, domain: str, key: str) -> str | None:
        return None

    def put(self, domain: str, key: str, value: str, ttl_seconds: int) -> None:
        pass

    def get_json(self, domain: str, key: str) -> object | None:
        return None

    def put_json(self, domain: str, key: str, value: object, ttl_seconds: int) -> None:
        pass

    def close(self) -> None:
        pass
