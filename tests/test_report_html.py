"""Tests for HTML report generation."""
from insecure_tree.models import PackageNode, Report, ReportSummary, ScanResult, ScanStatus
from insecure_tree.report.html import write_html


def _minimal_report() -> Report:
    return Report(
        project_path="/src/example",
        source_adapter="uv",
        scan_timestamp="2026-05-03T14:10:00Z",
        insecure_tree_version="0.1.0",
        summary=ReportSummary(total_packages=1),
        packages=[
            PackageNode(
                name="requests",
                normalized_name="requests",
                version="2.32.3",
                scan=ScanResult(status=ScanStatus.no_repo),
            ),
        ],
    )


def test_write_html_creates_file(tmp_path):
    report = _minimal_report()
    out = tmp_path / "report.html"
    write_html(report, out)
    assert out.exists()


def test_write_html_is_valid(tmp_path):
    report = _minimal_report()
    out = tmp_path / "report.html"
    write_html(report, out)
    content = out.read_text()
    assert "<!DOCTYPE html>" in content
    assert "<table" in content


def test_html_escapes_xss(tmp_path):
    report = Report(
        project_path="<script>alert(1)</script>",
        source_adapter="uv",
        scan_timestamp="2026-05-03T00:00:00Z",
        insecure_tree_version="0.1.0",
        summary=ReportSummary(),
        packages=[],
    )
    out = tmp_path / "report.html"
    write_html(report, out)
    content = out.read_text()
    assert "<script>alert(1)</script>" not in content
    assert "&lt;script&gt;" in content
