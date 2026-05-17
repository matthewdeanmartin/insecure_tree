"""Detect dangerous workflow trigger+action patterns without running zizmor."""

from __future__ import annotations

import logging
import re
from typing import Any

log = logging.getLogger(__name__)

# Matches any variant of actions/checkout (pinned or unpinned)
_CHECKOUT_RE = re.compile(r"actions/checkout", re.IGNORECASE)


def _load_yaml(content: str) -> dict[str, Any] | None:
    try:
        import yaml  # type: ignore[import-untyped]

        return yaml.safe_load(content)  # type: ignore[no-any-return]
    except Exception:
        return None


def _has_pull_request_target(on_value: Any) -> bool:
    """Return True if the workflow triggers on pull_request_target."""
    if isinstance(on_value, str):
        return on_value == "pull_request_target"
    if isinstance(on_value, list):
        return "pull_request_target" in on_value
    if isinstance(on_value, dict):
        return "pull_request_target" in on_value
    return False


def _checkout_steps(jobs: dict[str, Any]) -> list[tuple[str, int, str]]:
    """
    Return (job_name, step_index, uses_value) for every actions/checkout step.
    """
    hits: list[tuple[str, int, str]] = []
    if not isinstance(jobs, dict):
        return hits
    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps") or []
        if not isinstance(steps, list):
            continue
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            uses = step.get("uses", "") or ""
            if _CHECKOUT_RE.search(uses):
                hits.append((str(job_name), i, str(uses)))
    return hits


class PatternMatch:
    """A detected dangerous pattern in a single workflow file."""

    RULE_ID = "pwn-request"

    def __init__(
        self,
        workflow_name: str,
        workflow_path: str,
        job_name: str,
        step_index: int,
        uses: str,
    ) -> None:
        self.workflow_name = workflow_name
        self.workflow_path = workflow_path
        self.job_name = job_name
        self.step_index = step_index
        self.uses = uses

    @property
    def message(self) -> str:
        return (
            f"Workflow '{self.workflow_name}' triggers on pull_request_target and calls "
            f"{self.uses!r} in job '{self.job_name}' (step {self.step_index + 1}). "
            "This combination lets untrusted PR code run with base-repo write permissions "
            "(pwn-request / GHSL-2021-041 class vulnerability)."
        )


def detect_pwn_request(
    workflows: list[dict[str, str]],
) -> list[PatternMatch]:
    """
    Scan a list of workflow dicts (each with 'path', 'name', 'content') for the
    pull_request_target + actions/checkout co-occurrence.

    Returns one PatternMatch per (workflow, checkout-step) that is affected.
    """
    matches: list[PatternMatch] = []

    for wf in workflows:
        path = wf.get("path", "")
        name = wf.get("name", path)
        content = wf.get("content", "")

        # Fast-path: skip files that don't mention pull_request_target at all
        if "pull_request_target" not in content:
            continue

        data = _load_yaml(content)
        if not data or not isinstance(data, dict):
            continue

        on_value = data.get("on") or data.get(True)  # YAML 'on' may parse as True
        if not _has_pull_request_target(on_value):
            continue

        jobs = data.get("jobs") or {}
        for job_name, step_idx, uses in _checkout_steps(jobs):
            matches.append(
                PatternMatch(
                    workflow_name=name,
                    workflow_path=path,
                    job_name=job_name,
                    step_index=step_idx,
                    uses=uses,
                )
            )

    return matches
