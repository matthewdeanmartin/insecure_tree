"""Tests for JSON report generation."""

import json
from pathlib import Path

from insecure_tree.models import PackageNode, Report, ReportSummary, ScanResult, ScanStatus
from insecure_tree.report.json import write_json


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


def test_write_json_creates_parent_directories(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "reports" / "report.json"

    write_json(_minimal_report(), out)

    assert out.exists()


def test_write_json_serializes_report_content(tmp_path: Path) -> None:
    out = tmp_path / "report.json"

    write_json(_minimal_report(), out)

    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["project_path"] == "/src/example"
    assert data["packages"][0]["name"] == "requests"
    assert '"project_path": "/src/example"' in out.read_text(encoding="utf-8")
