"""Tests for domain models."""

from insecure_tree.models import (
    GraphEdge,
    PackageNode,
    Report,
    ReportSummary,
    ScanResult,
    ScanStatus,
    SourceAdapter,
)


def test_graph_edge_alias():
    edge = GraphEdge(**{"from": "a==1.0", "to": "b==2.0"})
    assert edge.from_pkg == "a==1.0"
    # Serialization uses "from"
    d = edge.model_dump(by_alias=True)
    assert "from" in d
    assert d["from"] == "a==1.0"


def test_scan_result_defaults():
    r = ScanResult(status=ScanStatus.no_repo)
    assert r.finding_count == 0
    assert r.findings == []


def test_package_node_defaults():
    n = PackageNode(name="requests", normalized_name="requests", version="2.32.3")
    assert n.requested is False
    assert n.scan is None


def test_report_roundtrip():
    report = Report(
        project_path="/tmp/test",
        source_adapter=SourceAdapter.uv.value,
        scan_timestamp="2026-05-03T00:00:00Z",
        insecure_tree_version="0.1.0",
        summary=ReportSummary(total_packages=5),
        packages=[PackageNode(name="requests", normalized_name="requests", version="2.32.3")],
    )
    json_str = report.model_dump_json()
    restored = Report.model_validate_json(json_str)
    assert restored.project_path == report.project_path
    assert len(restored.packages) == 1
    assert restored.packages[0].name == "requests"
