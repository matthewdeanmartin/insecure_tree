"""Tests for the pipdeptree adapter."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from insecure_tree.adapters.base import AdapterOptions
from insecure_tree.adapters.pipdeptree import PipdeptreeAdapter


def test_fetch_uses_current_python_module(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The adapter should invoke pipdeptree with the active interpreter by default."""
    captured: dict[str, object] = {}

    def fake_run_subprocess(cmd: list[str], cwd: Path, timeout: float) -> tuple[int, str, str]:
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["timeout"] = timeout
        payload = [
            {
                "package_name": "requests",
                "installed_version": "2.32.0",
                "dependencies": [],
            }
        ]
        return 0, json.dumps(payload), ""

    monkeypatch.setattr("insecure_tree.adapters.pipdeptree.run_subprocess", fake_run_subprocess)

    graph = PipdeptreeAdapter().fetch(AdapterOptions(project_path=tmp_path, timeout=12.5))

    assert captured["cmd"] == [sys.executable, "-m", "pipdeptree", "--json-tree"]
    assert captured["cwd"] == tmp_path
    assert captured["timeout"] == 12.5
    assert graph.root_packages == ["requests==2.32.0"]


def test_fetch_uses_explicit_python_when_provided(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
