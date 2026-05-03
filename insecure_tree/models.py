"""Domain models for insecure-tree."""

from __future__ import annotations

import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ConfidenceLevel(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"
    rejected = "rejected"


class ScanStatus(str, Enum):
    scanned = "scanned"
    no_repo = "no_repo"
    no_workflows = "no_workflows"
    clone_failed = "clone_failed"
    zizmor_failed = "zizmor_failed"
    metadata_failed = "metadata_failed"
    github_api_failed = "github_api_failed"
    skipped_cached = "skipped_cached"
    skipped = "skipped"
    non_github_repo = "non_github_repo"


class SourceAdapter(str, Enum):
    uv = "uv"
    uv_pip = "uv-pip"
    pip_inspect = "pip-inspect"
    pipdeptree = "pipdeptree"
    requirements = "requirements"
    json = "json"
    auto = "auto"


class ReportFormat(str, Enum):
    text = "text"
    html = "html"
    json = "json"


class FetchMode(str, Enum):
    auto = "auto"
    api = "api"
    git = "git"
    archive = "archive"


class PackageMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    index_url: str = ""
    metadata_source: str = ""
    summary: str = ""
    home_page: Optional[str] = None
    project_urls: Dict[str, str] = Field(default_factory=dict)
    requires_dist: List[str] = Field(default_factory=list)
    download_url: Optional[str] = None
    docs_url: Optional[str] = None
    description: str = ""


class RepoCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str
    owner: str
    repo: str
    source_field: str
    confidence: ConfidenceLevel
    reason: str
    normalized_clone_url: str
    default_branch: Optional[str] = None
    archived: Optional[bool] = None


class ScanFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str
    severity: str
    title: str
    path: str
    line: int
    column: int
    message: str
    url: str = ""


class ScanResult(BaseModel):
    status: ScanStatus
    zizmor_version: Optional[str] = None
    repo_ref: Optional[str] = None
    workflow_count: int = 0
    finding_count: int = 0
    findings_by_severity: Dict[str, int] = Field(default_factory=dict)
    findings: List[ScanFinding] = Field(default_factory=list)
    raw_output_path: Optional[str] = None
    error_message: Optional[str] = None


class PackageNode(BaseModel):
    name: str
    normalized_name: str
    version: str
    source: str = ""
    requested: bool = False
    depth: int = 0
    dependency_groups: List[str] = Field(default_factory=list)
    extras: List[str] = Field(default_factory=list)
    markers_applied: bool = False
    metadata: Optional[PackageMetadata] = None
    repo_candidates: List[RepoCandidate] = Field(default_factory=list)
    selected_repo: Optional[RepoCandidate] = None
    scan: Optional[ScanResult] = None


class GraphEdge(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    from_pkg: str = Field(alias="from", serialization_alias="from")
    to: str
    requirement: str = ""
    extra: Optional[str] = None
    marker: Optional[str] = None
    source: str = ""


class DependencyGraph(BaseModel):
    nodes: List[PackageNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)
    source: SourceAdapter = SourceAdapter.auto
    complete: bool = True
    root_packages: List[str] = Field(default_factory=list)


class ReportSummary(BaseModel):
    total_packages: int = 0
    packages_with_github: int = 0
    repos_scanned: int = 0
    repos_no_workflows: int = 0
    repos_with_findings: int = 0
    findings_by_severity: Dict[str, int] = Field(default_factory=dict)
    skipped: int = 0
    failed: int = 0


class Report(BaseModel):
    project_path: str = ""
    source_adapter: str = ""
    scan_timestamp: str = ""
    insecure_tree_version: str = ""
    zizmor_version: Optional[str] = None
    summary: ReportSummary = Field(default_factory=ReportSummary)
    packages: List[PackageNode] = Field(default_factory=list)
    graph: Optional[DependencyGraph] = None
    has_findings_above_threshold: bool = False
    has_partial_failures: bool = False


class GitHubConfig(BaseModel):
    token_env: str = "GITHUB_TOKEN"
    token: Optional[str] = None


class ZizmorphConfig(BaseModel):
    bin: str = "zizmor"
    args: List[str] = Field(default_factory=list)


class IgnoreRule(BaseModel):
    package: Optional[str] = None
    repo: Optional[str] = None
    rule: Optional[str] = None
    reason: str = ""
    expires: Optional[datetime.date] = None


class RepoOverride(BaseModel):
    package: str
    url: str
