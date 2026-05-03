"""Tests for the pipdeptree adapter."""

from __future__ import annotations

import json
from pathlib import Path

from insecure_tree.adapters.base import AdapterOptions
from insecure_tree.adapters.pipdeptree import PipdeptreeAdapter


def test_fetch_prefers_uv_run_for_uv_projects(monkeypatch, tmp_path: Path) -> None:
    """The adapter should prefer `uv run pipdeptree` inside uv-managed projects."""
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")
    captured: list[list[str]] = []

    def fake_which(name: str) -> str | None:
        if name == "uv":
            return "C:\\tools\\uv.exe"
        if name == "pipdeptree":
            return "C:\\tools\\pipdeptree.exe"
        return None

    def fake_run_subprocess(cmd: list[str], cwd: Path, timeout: float) -> tuple[int, str, str]:
        captured.append(cmd)
        assert cwd == tmp_path
        assert timeout == 9.5
        payload = [{"package_name": "requests", "installed_version": "2.32.0", "dependencies": []}]
        return 0, json.dumps(payload), ""

    monkeypatch.setattr("insecure_tree.adapters.pipdeptree.shutil.which", fake_which)
    monkeypatch.setattr("insecure_tree.adapters.pipdeptree.run_subprocess", fake_run_subprocess)

    graph = PipdeptreeAdapter().fetch(AdapterOptions(project_path=tmp_path, timeout=9.5))

    assert captured == [["uv", "run", "pipdeptree", "--json-tree"]]
    assert graph.root_packages == ["requests==2.32.0"]


def test_fetch_uses_explicit_python_when_provided(monkeypatch, tmp_path: Path) -> None:
    """The adapter should honor an explicit interpreter override."""

    def fake_run_subprocess(cmd: list[str], cwd: Path, timeout: float) -> tuple[int, str, str]:
        assert cmd == ["C:\\Python313\\python.exe", "-m", "pipdeptree", "--json-tree"]
        assert cwd == tmp_path
        assert timeout == 7.0
        return 0, "[]", ""

    monkeypatch.setattr("insecure_tree.adapters.pipdeptree.run_subprocess", fake_run_subprocess)

    graph = PipdeptreeAdapter().fetch(
        AdapterOptions(project_path=tmp_path, python="C:\\Python313\\python.exe", timeout=7.0)
    )

    assert graph.nodes == []
    assert graph.root_packages == []
