"""Extract and score GitHub repository candidates from package metadata."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from insecure_tree.models import ConfidenceLevel, PackageMetadata, RepoCandidate

_GITHUB_RE = re.compile(
    r"https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?(?:[/#?].*)?$",
    re.IGNORECASE,
)
# For scanning free-text; no end anchor
_GITHUB_SCAN_RE = re.compile(
    r"https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?(?=[/#?\s>)\]\"']|$)",
    re.IGNORECASE,
)
_GIT_SSH_RE = re.compile(
    r"git@github\.com:([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?$",
    re.IGNORECASE,
)
_GIT_SSH_URL_RE = re.compile(
    r"ssh://git@github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?$",
    re.IGNORECASE,
)
_GIT_PLUS_RE = re.compile(
    r"git\+https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?(?:[/#?].*)?$",
    re.IGNORECASE,
)

_SOURCE_LABELS = frozenset(["source", "source code", "repository", "code", "github", "homepage", "home"])
_REJECT_LABELS = frozenset(["bug tracker", "issues", "issue tracker", "ci", "funding"])
_DOC_LABELS = frozenset(["documentation", "docs"])
_CHANGELOG_LABELS = frozenset(["changelog", "changes", "history", "release notes"])

_REJECT_PATH_PARTS = frozenset([
    "issues", "pulls", "pull", "actions", "releases", "wiki",
    "gist.github.com", "topics", "search",
])


def _parse_github(raw: str) -> Optional[Tuple[str, str]]:
    """Return (owner, repo) from a raw GitHub URL/string, or None."""
    raw = raw.strip()
    for pattern in (_GIT_PLUS_RE, _GIT_SSH_URL_RE, _GIT_SSH_RE, _GITHUB_RE):
        m = pattern.match(raw)
        if m:
            owner, repo = m.group(1), m.group(2)
            repo = repo.removesuffix(".git")
            return owner, repo
    return None


def _is_rejected_path(url: str, owner: str, repo: str) -> bool:
    """Return True if the URL points to a sub-page rather than a repo root."""
    try:
        parsed = urlparse(url)
    except Exception:
        return True

    parts = [p for p in parsed.path.strip("/").split("/") if p]
    # owner/repo is fine; owner/repo/<anything> may indicate a sub-path
    if len(parts) > 2:
        third = parts[2].lower()
        if third in _REJECT_PATH_PARTS:
            return True
        # blob/tree paths that don't end at repo root
        if third in ("blob", "tree"):
            return True

    # Gist, org-level, or user-level only
    if len(parts) < 2:
        return True

    # Profile page: github.com/owner with no repo
    if len(parts) == 1:
        return True

    return False


def _normalize_clone_url(owner: str, repo: str) -> str:
    return f"https://github.com/{owner}/{repo}.git"


def _score_label(label: str) -> Tuple[ConfidenceLevel, str]:
    """Map a project_urls label to a confidence level."""
    low = label.lower().strip()
    if low in _SOURCE_LABELS:
        return ConfidenceLevel.high, f"Project-URL label '{label}' matched source/repository pattern"
    if low in _REJECT_LABELS:
        return ConfidenceLevel.rejected, f"Project-URL label '{label}' is a non-source label"
    if low in _DOC_LABELS:
        return ConfidenceLevel.low, f"Project-URL label '{label}' is documentation (low confidence)"
    if low in _CHANGELOG_LABELS:
        return ConfidenceLevel.medium, f"Project-URL label '{label}' is changelog/history"
    return ConfidenceLevel.medium, f"Project-URL label '{label}' (unrecognized; medium confidence)"


def _candidate_from_url(
    raw: str,
    source_field: str,
    confidence: ConfidenceLevel,
    reason: str,
) -> Optional[RepoCandidate]:
    parsed = _parse_github(raw)
    if parsed is None:
        return None
    owner, repo = parsed
    if _is_rejected_path(raw, owner, repo):
        return None
    return RepoCandidate(
        url=f"https://github.com/{owner}/{repo}",
        owner=owner,
        repo=repo,
        source_field=source_field,
        confidence=confidence,
        reason=reason,
        normalized_clone_url=_normalize_clone_url(owner, repo),
    )


def extract_github_candidates(metadata: PackageMetadata) -> List[RepoCandidate]:
    """Extract and rank GitHub repo candidates from package metadata."""
    seen: Dict[str, RepoCandidate] = {}

    def add(candidate: Optional[RepoCandidate]) -> None:
        if candidate is None or candidate.confidence == ConfidenceLevel.rejected:
            return
        key = f"{candidate.owner}/{candidate.repo}".lower()
        existing = seen.get(key)
        if existing is None or _confidence_rank(candidate.confidence) > _confidence_rank(existing.confidence):
            seen[key] = candidate

    # project_urls — highest signal
    for label, url in metadata.project_urls.items():
        if not url:
            continue
        conf, reason = _score_label(label)
        if conf == ConfidenceLevel.rejected:
            continue
        add(_candidate_from_url(url, f"project_urls.{label}", conf, reason))

    # home_page
    if metadata.home_page:
        parsed = _parse_github(metadata.home_page)
        if parsed and not _is_rejected_path(metadata.home_page, *parsed):
            owner, repo = parsed
            add(RepoCandidate(
                url=f"https://github.com/{owner}/{repo}",
                owner=owner,
                repo=repo,
                source_field="home_page",
                confidence=ConfidenceLevel.medium,
                reason="home_page field points to GitHub project root",
                normalized_clone_url=_normalize_clone_url(owner, repo),
            ))

    # download_url
    if metadata.download_url:
        add(_candidate_from_url(
            metadata.download_url,
            "download_url",
            ConfidenceLevel.low,
            "download_url field contains GitHub URL",
        ))

    # docs_url — very low confidence
    if metadata.docs_url:
        add(_candidate_from_url(
            metadata.docs_url,
            "docs_url",
            ConfidenceLevel.low,
            "docs_url field contains GitHub URL (low confidence)",
        ))

    # description — scan for GitHub URLs
    if metadata.description:
        for m in _GITHUB_SCAN_RE.finditer(metadata.description):
            raw = m.group(0)
            owner, repo_name = m.group(1), m.group(2).removesuffix(".git")
            if not _is_rejected_path(raw, owner, repo_name):
                add(RepoCandidate(
                    url=f"https://github.com/{owner}/{repo_name}",
                    owner=owner,
                    repo=repo_name,
                    source_field="description",
                    confidence=ConfidenceLevel.low,
                    reason="GitHub URL found in package description",
                    normalized_clone_url=_normalize_clone_url(owner, repo_name),
                ))

    _rank = [ConfidenceLevel.high, ConfidenceLevel.medium, ConfidenceLevel.low]
    return sorted(seen.values(), key=lambda c: _rank.index(c.confidence))


def _confidence_rank(c: ConfidenceLevel) -> int:
    return {ConfidenceLevel.high: 3, ConfidenceLevel.medium: 2, ConfidenceLevel.low: 1, ConfidenceLevel.rejected: 0}[c]


def select_best_candidate(candidates: List[RepoCandidate]) -> Optional[RepoCandidate]:
    """Return the highest-confidence candidate."""
    return candidates[0] if candidates else None
