"""Adapter for `uv tree` (text output)."""

from __future__ import annotations

import logging
import re
import shutil

from insecure_tree.adapters.base import AdapterOptions, BaseAdapter
from insecure_tree.models import DependencyGraph, GraphEdge, PackageNode, SourceAdapter
from insecure_tree.normalize import canonicalize
from insecure_tree.subprocess import SubprocessError, run_subprocess

log = logging.getLogger(__name__)

# Box-drawing chars used by uv tree: │ (U+2502), ├ (U+251C), └ (U+2514), ─ (U+2500)
_TREE_CHARS = frozenset("│├└─ \t")
_PKG_RE = re.compile(r"^(.+?)\s+v([\w.\-+]+)")


def _strip_tree_prefix(line: str) -> tuple[int, str]:
    """Return (depth, package_text) by consuming box-drawing prefix chars."""
    i = 0
    while i < len(line) and line[i] in _TREE_CHARS:
        i += 1
    prefix_len = i
    # Each nesting level is 4 chars wide: "│   ", "├── ", "└── "
    depth = prefix_len // 4
    return depth, line[i:]


def _parse_uv_tree(output: str) -> tuple[list[PackageNode], list[GraphEdge], list[str]]:
    nodes: list[PackageNode] = []
    edges: list[GraphEdge] = []
    roots: list[str] = []

    # Stack of (depth, pkg_key) for tracking parents
    parent_stack: list[tuple[int, str]] = []

    for raw_line in output.splitlines():
        # Skip blank lines and uv status lines ("Resolved N packages in Xms")
        stripped = raw_line.strip()
        if not stripped or stripped[0].isdigit() or stripped.startswith("Resolved"):
            continue

        depth, rest = _strip_tree_prefix(raw_line)

        # Strip trailing annotations like " (*)", " (extra: foo)", " (group: dev)"
        rest = re.sub(r"\s+\(.*\)\s*$", "", rest).strip()

        pm = _PKG_RE.match(rest)
        if not pm:
            continue

        name, version = pm.group(1).strip(), pm.group(2).strip()
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

        if depth == 0:
            roots.append(pkg_key)
            parent_stack = [(0, pkg_key)]
        else:
            # Pop stack back to the parent level
            while parent_stack and parent_stack[-1][0] >= depth:
                parent_stack.pop()
            if parent_stack:
                parent_key = parent_stack[-1][1]
                edges.append(GraphEdge(**{"from": parent_key, "to": pkg_key, "source": SourceAdapter.uv.value}))
            parent_stack.append((depth, pkg_key))

    return nodes, edges, roots


class UvAdapter(BaseAdapter):
    def detect(self, options: AdapterOptions) -> bool:
        if shutil.which("uv") is None:
            return False
        return (options.project_path / "uv.lock").exists() and (options.project_path / "pyproject.toml").exists()

    def fetch(self, options: AdapterOptions) -> DependencyGraph:
        cmd = ["uv", "tree", "--project", str(options.project_path)]
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

        nodes, edges, roots = _parse_uv_tree(stdout)

        return DependencyGraph(
            nodes=nodes,
            edges=edges,
            source=SourceAdapter.uv,
            complete=True,
            root_packages=roots,
        )
