"""Run zizmor against workflow directories and parse results."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from pathlib import Path
from typing import Any

from insecure_tree.cache import Cache
from insecure_tree.models import ScanFinding, ScanResult, ScanStatus
from insecure_tree.subprocess import SubprocessError, run_subprocess

log = logging.getLogger(__name__)


class ScanInfraError(Exception):
    pass


def _get_zizmor_version(zizmor_bin: str) -> str | None:
    try:
        _, stdout, stderr = run_subprocess([zizmor_bin, "--version"], timeout=10)
        line = (stdout or stderr).strip()
        # "zizmor 1.24.1" or just the version.
        parts = line.split()
        return parts[-1] if parts else None
    except (SubprocessError, OSError):
        return None


def _parse_zizmor_json(raw: dict[str, Any], owner: str, repo: str, commit_sha: str) -> list[ScanFinding]:
    findings: list[ScanFinding] = []
    # zizmor SARIF-like JSON: {"runs": [{"results": [...]}]}
    runs = raw.get("runs", [])
    for run in runs:
        for result in run.get("results", []):
            rule_id = result.get("ruleId", "")
            level = result.get("level", "note")
            message = result.get("message", {})
            msg_text = message.get("text", "") if isinstance(message, dict) else str(message)

            locations = result.get("locations", [])
            path = ""
            line = 0
            col = 0
            if locations:
                loc = locations[0]
                pl = loc.get("physicalLocation", {})
                af = pl.get("artifactLocation", {})
                path = af.get("uri", "")
                region = pl.get("region", {})
                line = region.get("startLine", 0)
                col = region.get("startColumn", 0)

            url = ""
            if commit_sha and path and line:
                url = f"https://github.com/{owner}/{repo}/blob/{commit_sha}/{path}#L{line}"

            # Map SARIF level to severity label
            severity_map = {"error": "error", "warning": "warning", "note": "note", "none": "note"}
            severity = severity_map.get(level, level)

            # Try to get a better title from rule metadata
            rule_index = result.get("rule", {}).get("index")
            title = rule_id
            if rule_index is not None:
                try:
                    rule_meta = run.get("tool", {}).get("driver", {}).get("rules", [])[rule_index]
                    title = rule_meta.get("shortDescription", {}).get("text", rule_id)
                except (IndexError, TypeError, KeyError):
                    pass

            findings.append(ScanFinding(
                rule_id=rule_id,
                severity=severity,
                title=title,
                path=path,
                line=line,
                column=col,
                message=msg_text,
                url=url,
            ))
    return findings


async def run_zizmor(  # pylint: disable=too-many-return-statements
    workflow_dir: Path,
    *,
    owner: str,
    repo: str,
    commit_sha: str,
    zizmor_bin: str = "zizmor",
    extra_args: list[str] | None = None,
    cache: Cache,
    timeout: float = 120.0,
) -> ScanResult:
    """Run zizmor against workflow_dir and return a ScanResult."""
    resolved = shutil.which(zizmor_bin)
    if not resolved:
        raise ScanInfraError(f"zizmor binary not found: {zizmor_bin!r}")

    zizmor_version = _get_zizmor_version(resolved) or "unknown"
    repo_ref = f"{owner}/{repo}@{commit_sha}"

    # Check cache
    config_hash = "default"
    cache_key = f"{zizmor_version}:{repo_ref}:{config_hash}"
    cached = cache.get_json("zizmor", cache_key)
    if cached and isinstance(cached, dict):
        findings = [ScanFinding(**f) for f in cached.get("findings", [])]
        return _build_result(ScanStatus.scanned, zizmor_version, repo_ref, findings, cached.get("workflow_count", 0))

    # Count workflow files
    wf_dir = workflow_dir / ".github" / "workflows"
    workflow_count = len(list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml"))) if wf_dir.exists() else 0

    cmd = [resolved, "--format", "sarif"] + (extra_args or []) + [str(workflow_dir)]

    try:
        proc = await asyncio.to_thread(
            run_subprocess,
            cmd,
            timeout=timeout,
            check=False,
        )
    except TimeoutError:
        return ScanResult(status=ScanStatus.zizmor_failed, error_message="zizmor timed out")
    except Exception as exc:
        return ScanResult(status=ScanStatus.zizmor_failed, error_message=str(exc))

    # zizmor exits non-zero when findings exist; that's expected
    returncode, stdout, stderr = proc
    raw_output = stdout or stderr or ""
    if not raw_output.strip():
        return ScanResult(
            status=ScanStatus.zizmor_failed,
            zizmor_version=zizmor_version,
            error_message=f"zizmor produced no output (exit {returncode})",
        )

    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        return ScanResult(
            status=ScanStatus.zizmor_failed,
            zizmor_version=zizmor_version,
            error_message=f"zizmor JSON parse error: {exc}",
        )
    if not isinstance(data, dict):
        return ScanResult(
            status=ScanStatus.zizmor_failed,
            zizmor_version=zizmor_version,
            error_message="zizmor returned an unexpected JSON payload",
        )

    findings = _parse_zizmor_json(data, owner, repo, commit_sha)

    cache.put_json("zizmor", cache_key, {
        "findings": [f.model_dump() for f in findings],
        "workflow_count": workflow_count,
    }, 7 * 24 * 3600)

    return _build_result(ScanStatus.scanned, zizmor_version, repo_ref, findings, workflow_count)


def _build_result(
    status: ScanStatus,
    version: str,
    repo_ref: str,
    findings: list[ScanFinding],
    workflow_count: int,
) -> ScanResult:
    by_sev: dict[str, int] = {}
    for f in findings:
        by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
    return ScanResult(
        status=status,
        zizmor_version=version,
        repo_ref=repo_ref,
        workflow_count=workflow_count,
        finding_count=len(findings),
        findings_by_severity=by_sev,
        findings=findings,
    )
