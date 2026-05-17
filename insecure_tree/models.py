"""Domain models for insecure-tree."""

from __future__ import annotations

import datetime
from enum import Enum

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
    home_page: str | None = None
    project_urls: dict[str, str] = Field(default_factory=dict)
    requires_dist: list[str] = Field(default_factory=list)
    download_url: str | None = None
    docs_url: str | None = None
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
    default_branch: str | None = None
    archived: bool | None = None


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


class PatternFinding(BaseModel):
    """A dangerous trigger+action co-occurrence detected by insecure-tree itself."""

    model_config = ConfigDict(frozen=True)

    rule_id: str
    workflow_name: str
    workflow_path: str
    job_name: str
    step_index: int
    uses: str
    message: str


class ScanResult(BaseModel):
    status: ScanStatus
    zizmor_version: str | None = None
    repo_ref: str | None = None
    workflow_count: int = 0
    finding_count: int = 0
    findings_by_severity: dict[str, int] = Field(default_factory=dict)
    findings: list[ScanFinding] = Field(default_factory=list)
    pattern_findings: list[PatternFinding] = Field(default_factory=list)
    raw_output_path: str | None = None
    error_message: str | None = None


class PackageNode(BaseModel):
    name: str
    normalized_name: str
    version: str
    source: str = ""
    requested: bool = False
    depth: int = 0
    dependency_groups: list[str] = Field(default_factory=list)
    extras: list[str] = Field(default_factory=list)
    markers_applied: bool = False
    metadata: PackageMetadata | None = None
    repo_candidates: list[RepoCandidate] = Field(default_factory=list)
    selected_repo: RepoCandidate | None = None
    scan: ScanResult | None = None


class GraphEdge(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    from_pkg: str = Field(alias="from", serialization_alias="from")
    to: str
    requirement: str = ""
    extra: str | None = None
    marker: str | None = None
    source: str = ""


class DependencyGraph(BaseModel):
    nodes: list[PackageNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    source: SourceAdapter = SourceAdapter.auto
    complete: bool = True
    root_packages: list[str] = Field(default_factory=list)


class ReportSummary(BaseModel):
    total_packages: int = 0
    packages_with_github: int = 0
    repos_scanned: int = 0
    repos_no_workflows: int = 0
    repos_with_findings: int = 0
    findings_by_severity: dict[str, int] = Field(default_factory=dict)
    pwn_request_count: int = 0
    skipped: int = 0
    failed: int = 0


class Report(BaseModel):
    project_path: str = ""
    source_adapter: str = ""
    scan_timestamp: str = ""
    insecure_tree_version: str = ""
    zizmor_version: str | None = None
    summary: ReportSummary = Field(default_factory=ReportSummary)
    packages: list[PackageNode] = Field(default_factory=list)
    graph: DependencyGraph | None = None
    has_findings_above_threshold: bool = False
    has_partial_failures: bool = False


class GitHubConfig(BaseModel):
    token_env: str = "GITHUB_TOKEN"
    token: str | None = None


class ZizmorphConfig(BaseModel):
    bin: str = "zizmor"
    args: list[str] = Field(default_factory=list)


class IgnoreRule(BaseModel):
    package: str | None = None
    repo: str | None = None
    rule: str | None = None
    reason: str = ""
    expires: datetime.date | None = None


class RepoOverride(BaseModel):
    package: str
    url: str
