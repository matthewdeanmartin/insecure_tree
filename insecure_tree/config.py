"""Configuration loading and merging for insecure-tree."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from insecure_tree.models import (
    FetchMode,
    GitHubConfig,
    IgnoreRule,
    ReportFormat,
    SourceAdapter,
    ZizmorphConfig,
)

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]


class Config(BaseModel):
    source: SourceAdapter = SourceAdapter.auto
    project: str = "."
    output_dir: str = "insecure-tree-report"
    formats: List[ReportFormat] = Field(default_factory=lambda: [ReportFormat.text, ReportFormat.html, ReportFormat.json])
    fail_on: str = "never"
    report_min_severity: str = "note"
    repo_fetch: FetchMode = FetchMode.api
    concurrency: int = 16
    github_concurrency: int = 8
    zizmor_concurrency: int = 8
    metadata_ttl: int = 7 * 24 * 3600
    repo_ttl: int = 1 * 24 * 3600
    no_cache: bool = False
    refresh: bool = False
    offline: bool = False
    no_clone: bool = False
    strict: bool = False
    fail_on_partial: bool = False
    depth: Optional[int] = None
    include_dev: bool = True
    timeout: float = 30.0
    python: Optional[str] = None
    requirements: List[str] = Field(default_factory=list)
    github: GitHubConfig = Field(default_factory=GitHubConfig)
    zizmor: ZizmorphConfig = Field(default_factory=ZizmorphConfig)
    ignore: List[IgnoreRule] = Field(default_factory=list)
    repo_overrides: Dict[str, str] = Field(default_factory=dict)


def _parse_ttl(value: object) -> int:
    """Convert a TTL string like '7d', '2h', '30m' to seconds, or pass int through."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        units = {"d": 86400, "h": 3600, "m": 60, "s": 1}
        for suffix, mult in units.items():
            if value.endswith(suffix):
                return int(value[:-1]) * mult
        return int(value)
    return int(value)  # type: ignore[arg-type]


def load_config(project_path: Path) -> Config:
    """Load config from pyproject.toml or insecure-tree.toml."""
    data: dict = {}

    pyproject = project_path / "pyproject.toml"
    if pyproject.exists():
        with open(pyproject, "rb") as f:
            raw = tomllib.load(f)
        data = raw.get("tool", {}).get("insecure-tree", {})

    toml_file = project_path / "insecure-tree.toml"
    if toml_file.exists():
        with open(toml_file, "rb") as f:
            raw2 = tomllib.load(f)
        data.update(raw2.get("tool", {}).get("insecure-tree", raw2))

    for ttl_field in ("metadata_ttl", "repo_ttl"):
        if ttl_field in data:
            data[ttl_field] = _parse_ttl(data[ttl_field])

    github_data = data.pop("github", {})
    zizmor_data = data.pop("zizmor", {})
    ignore_data = data.pop("ignore", [])
    repo_overrides = data.pop("repo_overrides", {})

    config = Config(**data)
    if github_data:
        config = config.model_copy(update={"github": GitHubConfig(**github_data)})
    if zizmor_data:
        config = config.model_copy(update={"zizmor": ZizmorphConfig(**zizmor_data)})
    if ignore_data:
        config = config.model_copy(update={"ignore": [IgnoreRule(**r) for r in ignore_data]})
    if repo_overrides:
        config = config.model_copy(update={"repo_overrides": repo_overrides})

    return config
