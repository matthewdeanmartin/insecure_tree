"""Adapter for `uv pip tree --output-format json`."""

from __future__ import annotations

import json
import logging
import shutil
from typing import List, Optional

from insecure_tree.adapters.base import AdapterOptions, BaseAdapter
from insecure_tree.models import DependencyGraph, GraphEdge, PackageNode, SourceAdapter
from insecure_tree.normalize import canonicalize
from insecure_tree.subprocess import SubprocessError, run_subprocess

log = logging.getLogger(__name__)


def _walk(
    node: dict,
    nodes: List[PackageNode],
    edges: List[GraphEdge],
    depth: int,
    parent_key: Optional[str],
) -> None:
    name = node.get("name", "")
    version = node.get("version", "")
    norm = canonicalize(name)
    pkg_key = f"{norm}=={version}"

    if not any(n.normalized_name == norm and n.version == version for n in nodes):
        nodes.append(PackageNode(
            name=name,
            normalized_name=norm,
            version=version,
            source=SourceAdapter.uv_pip.value,
            requested=(depth == 0),
            depth=depth,
        ))

    if parent_key:
        edge = GraphEdge(
            **{"from": parent_key, "to": pkg_key, "source": SourceAdapter.uv_pip.value}
        )
        edges.append(edge)

    for dep in node.get("dependencies", []):
        _walk(dep, nodes, edges, depth + 1, pkg_key)


class UvPipAdapter(BaseAdapter):
    def detect(self, options: AdapterOptions) -> bool:
        return shutil.which("uv") is not None

    def fetch(self, options: AdapterOptions) -> DependencyGraph:
        cmd = ["uv", "pip", "tree", "--output-format", "json"]
        if options.python:
            cmd += ["--python", options.python]

        try:
            _, stdout, _ = run_subprocess(cmd, cwd=options.project_path, timeout=options.timeout)
        except SubprocessError as exc:
            log.error("uv pip tree failed: %s", exc)
            raise

        try:
            raw = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise ValueError(f"uv pip tree produced invalid JSON: {exc}") from exc

        nodes: List[PackageNode] = []
        edges: List[GraphEdge] = []
        roots: List[str] = []

        for item in raw if isinstance(raw, list) else [raw]:
            name = item.get("name", "")
            version = item.get("version", "")
            roots.append(f"{canonicalize(name)}=={version}")
            _walk(item, nodes, edges, 0, None)

        return DependencyGraph(
            nodes=nodes,
            edges=edges,
            source=SourceAdapter.uv_pip,
            complete=True,
            root_packages=roots,
        )
