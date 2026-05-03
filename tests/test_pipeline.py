"""Tests for pure pipeline helpers."""

from pytest import MonkeyPatch

from insecure_tree.models import (
    ConfidenceLevel,
    PackageNode,
    RepoCandidate,
    ReportSummary,
    ScanResult,
    ScanStatus,
)
from insecure_tree.pipeline import _build_summary, _check_threshold, _first_zizmor_version, _NullCache, _read_token


def _repo_candidate(name: str) -> RepoCandidate:
    return RepoCandidate(
        url=f"https://github.com/example/{name}",
        owner="example",
        repo=name,
        source_field="test",
        confidence=ConfidenceLevel.high,
        reason="test fixture",
        normalized_clone_url=f"https://github.com/example/{name}.git",
    )


def _package(name: str, *, with_repo: bool = False, scan: ScanResult | None = None) -> PackageNode:
    return PackageNode(
        name=name,
        normalized_name=name,
        version="1.0.0",
        selected_repo=_repo_candidate(name) if with_repo else None,
        scan=scan,
    )


def test_build_summary_counts_scans_statuses_and_severity_totals() -> None:
    nodes = [
        _package(
            "alpha",
            with_repo=True,
            scan=ScanResult(
                status=ScanStatus.scanned,
                finding_count=2,
                findings_by_severity={"warning": 1, "error": 1},
            ),
        ),
        _package("beta", with_repo=True, scan=ScanResult(status=ScanStatus.no_workflows)),
        _package("gamma", scan=ScanResult(status=ScanStatus.skipped)),
        _package("delta", scan=ScanResult(status=ScanStatus.github_api_failed)),
    ]

    summary = _build_summary(nodes)

    assert summary.total_packages == 4
    assert summary.packages_with_github == 2
    assert summary.repos_scanned == 1
    assert summary.repos_no_workflows == 1
    assert summary.repos_with_findings == 1
    assert summary.findings_by_severity == {"warning": 1, "error": 1}
    assert summary.skipped == 1
    assert summary.failed == 1


def test_first_zizmor_version_returns_first_available_value() -> None:
    nodes = [
        _package("alpha", scan=ScanResult(status=ScanStatus.no_repo)),
        _package("beta", scan=ScanResult(status=ScanStatus.scanned, zizmor_version="1.8.0")),
        _package("gamma", scan=ScanResult(status=ScanStatus.scanned, zizmor_version="2.0.0")),
    ]

    assert _first_zizmor_version(nodes) == "1.8.0"


def test_check_threshold_respects_requested_minimum() -> None:
    summary = ReportSummary(findings_by_severity={"note": 2, "warning": 1})

    assert _check_threshold(summary, "never") is False
    assert _check_threshold(summary, "error") is False
    assert _check_threshold(summary, "warning") is True
    assert _check_threshold(summary, "note") is True
    assert _check_threshold(summary, "unknown") is False


def test_read_token_uses_environment_variable(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("ALT_GITHUB_TOKEN", "token-value")
    assert _read_token("ALT_GITHUB_TOKEN") == "token-value"

    monkeypatch.delenv("ALT_GITHUB_TOKEN")
    assert _read_token("ALT_GITHUB_TOKEN") is None


def test_null_cache_discards_values() -> None:
    cache = _NullCache()

    cache.put("meta", "requests", "value", ttl_seconds=60)
    cache.put_json("meta", "requests", {"name": "requests"}, ttl_seconds=60)

    assert cache.get("meta", "requests") is None
    assert cache.get_json("meta", "requests") is None
    cache.close()
