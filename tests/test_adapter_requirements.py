"""Tests for the requirements.txt adapter."""

import pytest

from insecure_tree.adapters.base import AdapterOptions
from insecure_tree.adapters.requirements import RequirementsAdapter


@pytest.fixture
def req_project(tmp_path):
    (tmp_path / "requirements.txt").write_text(
        "requests==2.32.3\nurllib3>=1.21,<3\n# comment\nchardet\n",
        encoding="utf-8",
    )
    return tmp_path


def test_detect_when_requirements_present(req_project):
    adapter = RequirementsAdapter()
    options = AdapterOptions(project_path=req_project)
    assert adapter.detect(options) is True


def test_detect_when_no_requirements(tmp_path):
    adapter = RequirementsAdapter()
    options = AdapterOptions(project_path=tmp_path)
    assert adapter.detect(options) is False


def test_fetch_parses_packages(req_project):
    adapter = RequirementsAdapter()
    options = AdapterOptions(project_path=req_project)
    graph = adapter.fetch(options)
    names = {n.name for n in graph.nodes}
    assert "requests" in names
    assert "urllib3" in names
    assert "chardet" in names


def test_fetch_pinned_version(req_project):
    adapter = RequirementsAdapter()
    options = AdapterOptions(project_path=req_project)
    graph = adapter.fetch(options)
    requests_node = next(n for n in graph.nodes if n.name == "requests")
    assert requests_node.version == "2.32.3"


def test_fetch_graph_incomplete(req_project):
    adapter = RequirementsAdapter()
    options = AdapterOptions(project_path=req_project)
    graph = adapter.fetch(options)
    assert graph.complete is False


def test_fetch_deduplicates(tmp_path):
    (tmp_path / "requirements.txt").write_text("requests==2.0\nRequests==2.0\n")
    adapter = RequirementsAdapter()
    graph = adapter.fetch(AdapterOptions(project_path=tmp_path))
    assert sum(1 for n in graph.nodes if n.normalized_name == "requests") == 1
