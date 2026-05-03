"""Tests for GitHub URL extraction and confidence scoring."""
import pytest

from insecure_tree.metadata.github_urls import _parse_github, extract_github_candidates
from insecure_tree.models import ConfidenceLevel, PackageMetadata


# ---------------------------------------------------------------------------
# _parse_github
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url,expected", [
    ("https://github.com/psf/requests", ("psf", "requests")),
    ("https://github.com/psf/requests.git", ("psf", "requests")),
    ("https://github.com/psf/requests/", ("psf", "requests")),
    ("git+https://github.com/psf/requests.git", ("psf", "requests")),
    ("git@github.com:psf/requests.git", ("psf", "requests")),
    ("ssh://git@github.com/psf/requests.git", ("psf", "requests")),
    ("https://example.com/psf/requests", None),
    ("https://gist.github.com/abc/def", None),
])
def test_parse_github(url, expected):
    assert _parse_github(url) == expected


# ---------------------------------------------------------------------------
# extract_github_candidates
# ---------------------------------------------------------------------------

def _meta(**kwargs) -> PackageMetadata:
    defaults = dict(
        index_url="",
        metadata_source="test",
        summary="",
        home_page=None,
        project_urls={},
        requires_dist=[],
        download_url=None,
        docs_url=None,
        description="",
    )
    defaults.update(kwargs)
    return PackageMetadata(**defaults)


def test_high_confidence_from_source_label():
    meta = _meta(project_urls={"Source": "https://github.com/psf/requests"})
    candidates = extract_github_candidates(meta)
    assert candidates
    assert candidates[0].confidence == ConfidenceLevel.high
    assert candidates[0].owner == "psf"
    assert candidates[0].repo == "requests"


def test_medium_confidence_from_homepage():
    meta = _meta(home_page="https://github.com/psf/requests")
    candidates = extract_github_candidates(meta)
    assert candidates
    assert candidates[0].confidence == ConfidenceLevel.medium


def test_rejected_issues_url():
    meta = _meta(project_urls={"Bug Tracker": "https://github.com/psf/requests/issues"})
    candidates = extract_github_candidates(meta)
    assert not candidates


def test_rejected_subpath():
    # issues, pulls, actions sub-paths are rejected
    meta = _meta(project_urls={"Source": "https://github.com/psf/requests/issues"})
    candidates = extract_github_candidates(meta)
    assert not candidates


def test_deduplicate_same_repo():
    meta = _meta(
        project_urls={"Source": "https://github.com/psf/requests"},
        home_page="https://github.com/psf/requests",
    )
    candidates = extract_github_candidates(meta)
    assert len(candidates) == 1
    assert candidates[0].confidence == ConfidenceLevel.high


def test_normalized_clone_url():
    meta = _meta(project_urls={"Source": "https://github.com/psf/requests"})
    c = extract_github_candidates(meta)[0]
    assert c.normalized_clone_url == "https://github.com/psf/requests.git"


def test_no_github_url():
    meta = _meta(home_page="https://example.com/mypackage")
    assert extract_github_candidates(meta) == []


def test_github_url_in_description():
    meta = _meta(description="See https://github.com/psf/requests for docs.")
    candidates = extract_github_candidates(meta)
    assert candidates
    assert candidates[0].confidence == ConfidenceLevel.low


def test_repository_label_high_confidence():
    meta = _meta(project_urls={"Repository": "https://github.com/encode/httpx"})
    candidates = extract_github_candidates(meta)
    assert candidates[0].confidence == ConfidenceLevel.high


def test_profile_only_rejected():
    # github.com/psf with no repo is rejected
    meta = _meta(home_page="https://github.com/psf")
    assert extract_github_candidates(meta) == []
