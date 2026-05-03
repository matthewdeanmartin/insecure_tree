"""Adapter for `python -m pipdeptree --json-tree`."""

from __future__ import annotations

from importlib.util import find_spec
import json
import logging
import sys
from typing import Any

from insecure_tree.adapters.base import AdapterOptions, BaseAdapter
from insecure_tree.models import DependencyGraph, GraphEdge, PackageNode, SourceAdapter
from insecure_tree.normalize import canonicalize
from insecure_tree.subprocess import SubprocessError, run_subprocess

log = logging.getLogger(__name__)


def _walk(
    node: dict[str, Any],
    nodes: list[PackageNode],
    edges: list[GraphEdge],
    depth: int,
    parent_key: str | None,
) -> None:
    name = node.get("package_name") or node.get("name") or ""
    version = node.get("installed_version") or node.get("version") or ""
    norm = canonicalize(name)
    pkg_key = f"{norm}=={version}"

    if not any(n.normalized_name == norm and n.version == version for n in nodes):
        nodes.append(
            PackageNode(
                name=name,
                normalized_name=norm,
                version=version,
                source=SourceAdapter.pipdeptree.value,
                requested=(depth == 0),
                depth=depth,
            )
        )

    if parent_key:
        edge = GraphEdge(**{"from": parent_key, "to": pkg_key, "source": SourceAdapter.pipdeptree.value})
        edges.append(edge)

    for dep in node.get("dependencies", []):
        _walk(dep, nodes, edges, depth + 1, pkg_key)


class PipdeptreeAdapter(BaseAdapter):
    def detect(self, options: AdapterOptions) -> bool:
        return find_spec("pipdeptree") is not None

    def fetch(self, options: AdapterOptions) -> DependencyGraph:
        python = options.python or sys.executable
        cmd = [python, "-m", "pipdeptree", "--json-tree"]

        try:
            _, stdout, _ = run_subprocess(cmd, cwd=options.project_path, timeout=options.timeout)
        except SubprocessError as exc:
            log.error("pipdeptree failed: %s", exc)
            raise

        try:
            raw = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise ValueError(f"pipdeptree produced invalid JSON: {exc}") from exc

        nodes: list[PackageNode] = []
        edges: list[GraphEdge] = []
        roots: list[str] = []

        for item in raw if isinstance(raw, list) else [raw]:
            name = item.get("package_name") or item.get("name") or ""
            version = item.get("installed_version") or item.get("version") or ""
            roots.append(f"{canonicalize(name)}=={version}")
            _walk(item, nodes, edges, 0, None)

        return DependencyGraph(
            nodes=nodes,
            edges=edges,
            source=SourceAdapter.pipdeptree,
            complete=True,
            root_packages=roots,
        )
