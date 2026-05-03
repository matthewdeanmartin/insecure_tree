"""JSON report writer."""

from __future__ import annotations

from pathlib import Path

from insecure_tree.models import Report


def write_json(report: Report, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
