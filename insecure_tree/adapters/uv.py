"""Adapter for `uv tree --output-format json`."""

from __future__ import annotations

import json
import logging
import shutil
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
    _parent_key: str | None,
) -> None:
    name = node.get("name", "")
    version = node.get("version", "")
    norm = canonicalize(name)
    pkg_key = f"{norm}=={version}"

    if not any(n.normalized_name == norm and n.version == version for n in nodes):
        nodes.append(
            PackageNode(
                name=name,
                normalized_name=norm,
                version=version,
                source=SourceAdapter.uv.value,
                requested=(depth == 0),
                depth=depth,
            )
        )

    for dep in node.get("dependencies", []):
        dep_name = dep.get("name", "")
        dep_version = dep.get("version", "")
        dep_norm = canonicalize(dep_name)
        edge = GraphEdge(**{"from": pkg_key, "to": f"{dep_norm}=={dep_version}", "source": SourceAdapter.uv.value})
        edges.append(edge)
        _walk(dep, nodes, edges, depth + 1, pkg_key)


class UvAdapter(BaseAdapter):
    def detect(self, options: AdapterOptions) -> bool:
        if shutil.which("uv") is None:
            return False
        return (options.project_path / "uv.lock").exists() and (options.project_path / "pyproject.toml").exists()

    def fetch(self, options: AdapterOptions) -> DependencyGraph:
        cmd = ["uv", "tree", "--output-format", "json", "--project", str(options.project_path)]
        if options.depth is not None:
            cmd += ["--depth", str(options.depth)]
        if not options.include_dev:
            cmd.append("--no-dev")
        for extra in options.extras:
            cmd += ["--extra", extra]
        for group in options.groups:
            cmd += ["--group", group]

        try:
            _, stdout, _ = run_subprocess(cmd, cwd=options.project_path, timeout=options.timeout)
        except SubprocessError as exc:
            log.error("uv tree failed: %s", exc)
            raise

        try:
            raw = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise ValueError(f"uv tree produced invalid JSON: {exc}") from exc

        nodes: list[PackageNode] = []
        edges: list[GraphEdge] = []
        roots: list[str] = []

        # uv tree JSON is a list of root packages
        if isinstance(raw, list):
            for item in raw:
                name = item.get("name", "")
                version = item.get("version", "")
                roots.append(f"{canonicalize(name)}=={version}")
                _walk(item, nodes, edges, 0, None)
        elif isinstance(raw, dict):
            # single-package workspace
            name = raw.get("name", "")
            version = raw.get("version", "")
            roots.append(f"{canonicalize(name)}=={version}")
            _walk(raw, nodes, edges, 0, None)

        return DependencyGraph(
            nodes=nodes,
            edges=edges,
            source=SourceAdapter.uv,
            complete=True,
            root_packages=roots,
        )
