"""Tests for text report generation."""

from insecure_tree.models import PackageNode, Report, ReportSummary, ScanResult, ScanStatus
from insecure_tree.report.text import write_text


def _minimal_report() -> Report:
    return Report(
        project_path="/src/example",
        source_adapter="uv",
        scan_timestamp="2026-05-03T14:10:00Z",
        insecure_tree_version="0.1.0",
        summary=ReportSummary(
            total_packages=2,
            packages_with_github=1,
            repos_scanned=1,
            findings_by_severity={"error": 0, "warning": 0},
        ),
        packages=[
            PackageNode(
                name="requests",
                normalized_name="requests",
                version="2.32.3",
                scan=ScanResult(status=ScanStatus.no_workflows),
            ),
            PackageNode(
                name="charset-normalizer",
                normalized_name="charset-normalizer",
                version="3.3.2",
                scan=ScanResult(status=ScanStatus.no_repo),
            ),
        ],
    )


def test_write_text_creates_file(tmp_path):
    report = _minimal_report()
    out = tmp_path / "report.txt"
    write_text(report, out)
    assert out.exists()


def test_write_text_contains_header(tmp_path):
    report = _minimal_report()
    out = tmp_path / "report.txt"
    write_text(report, out)
    text = out.read_text()
    assert "insecure-tree report" in text
    assert "/src/example" in text


def test_write_text_contains_packages(tmp_path):
    report = _minimal_report()
    out = tmp_path / "report.txt"
    write_text(report, out)
    text = out.read_text()
    assert "requests==2.32.3" in text
    assert "charset-normalizer==3.3.2" in text
