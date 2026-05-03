"""Adapter for `python -m pip inspect` (reconstructs graph from requires_dist)."""

from __future__ import annotations

import json
import logging
import re
import shutil
import sys
from typing import Any, cast

from packaging.requirements import InvalidRequirement, Requirement

from insecure_tree.adapters.base import AdapterOptions, BaseAdapter
from insecure_tree.marker_eval import default_env, evaluate_marker
from insecure_tree.models import DependencyGraph, GraphEdge, PackageNode, SourceAdapter
from insecure_tree.normalize import canonicalize
from insecure_tree.subprocess import SubprocessError, run_subprocess

log = logging.getLogger(__name__)


def _recover_partial_pip_inspect(stdout: str) -> dict[str, Any] | None:
    """Recover valid JSON from truncated pip inspect output.

    pip inspect writes a JSON object where installed[] may be truncated mid-entry.
    Find the last complete entry by scanning backwards for a complete object boundary.
    """
    # Find the last occurrence of a pattern that ends a complete installed entry:
    # "    }," or "    }" followed by whitespace/newline
    # Try successively truncating at the last top-level object boundary in installed[]
    s = stdout.rstrip()
    # Attempt to close the truncated JSON by finding last complete top-level "}" that
    # closes an entry in the installed list
    pattern = re.compile(r'\}\s*,?\s*\n?\s*\{', re.DOTALL)
    # Find the position of the last "}, {" pair — that's where the last complete entry ends
    best_cut = -1
    for m in pattern.finditer(s):
        best_cut = m.start() + 1  # position right after the closing }

    if best_cut > 0:
        trimmed = s[:best_cut].rstrip().rstrip(",")
        # Try each closing suffix
        for suffix in ["\n  ]\n}", "\n  ]}", "]}", "]"]:
            try:
                recovered = json.loads(trimmed + suffix)
                if isinstance(recovered, dict):
                    return recovered
            except json.JSONDecodeError:
                pass

    return None


class PipInspectAdapter(BaseAdapter):
    def detect(self, options: AdapterOptions) -> bool:
        python = options.python or sys.executable
        if not python:
            return False
        return shutil.which(python) is not None or python == sys.executable

    def fetch(self, options: AdapterOptions) -> DependencyGraph:
        python = options.python or sys.executable
        cmd = [python, "-m", "pip", "inspect", "--isolated"]

        try:
            # pip inspect may exit non-zero on some platforms while still writing valid JSON.
            returncode, stdout, stderr = run_subprocess(
                cmd,
                cwd=options.project_path,
                timeout=options.timeout,
                check=False,
            )
            if not stdout.strip() and returncode != 0:
                raise SubprocessError(cmd, returncode, stderr)
        except SubprocessError:
            raise
        except Exception as exc:
            log.error("pip inspect failed: %s", exc)
            raise

        try:
            raw = json.loads(stdout)
        except json.JSONDecodeError as exc:
            # Some pip versions emit truncated JSON if a package description contains
            # unusual characters. Try to recover the installed list from the partial output.
            log.warning("pip inspect produced invalid JSON (%s); attempting partial parse", exc)
            raw = _recover_partial_pip_inspect(stdout)
            if raw is None:
                raise ValueError(f"pip inspect produced invalid JSON and partial parse failed: {exc}") from exc

        if not isinstance(raw, dict):
            raise ValueError("pip inspect returned an unexpected JSON payload")

        env = default_env()
        installed = raw.get("installed", [])

        # Build a map of normalized_name -> (name, version, requires_dist)
        pkg_map: dict[str, tuple[str, str, list[str]]] = {}
        for dist in installed:
            meta = dist.get("metadata", {})
            name = meta.get("name") or dist.get("name") or ""
            version = meta.get("version") or dist.get("version") or ""
            requires_dist_raw = meta.get("requires_dist") or []
            requires_dist = [str(item) for item in requires_dist_raw] if isinstance(requires_dist_raw, list) else []
            norm = canonicalize(name)
            pkg_map[norm] = (name, version, requires_dist)

        nodes: list[PackageNode] = []
        edges: list[GraphEdge] = []

        # Build nodes first
        depended_on: set[str] = set()
        edge_list: list[tuple[str, str, str, list[str], str | None]] = []

        for norm, (_name, version, requires_dist) in pkg_map.items():
            from_key = f"{norm}=={version}"
            for req_str in requires_dist:
                try:
                    req = Requirement(req_str)
                except InvalidRequirement:
                    continue
                if req.marker and not evaluate_marker(str(req.marker), env):
                    continue
                dep_norm = canonicalize(req.name)
                if dep_norm in pkg_map:
                    dep_version = pkg_map[dep_norm][1]
                    to_key = f"{dep_norm}=={dep_version}"
                    depended_on.add(dep_norm)
                    edge_list.append(
                        (from_key, to_key, req_str, sorted(req.extras), str(req.marker) if req.marker else None)
                    )

        roots: list[str] = []
        for norm, (name, version, _) in pkg_map.items():
            is_root = norm not in depended_on
            pkg_key = f"{norm}=={version}"
            if is_root:
                roots.append(pkg_key)
            nodes.append(PackageNode(
                name=name,
                normalized_name=norm,
                version=version,
                source=SourceAdapter.pip_inspect.value,
                requested=is_root,
                depth=0 if is_root else 1,
            ))

        for from_key, to_key, req_str, extras, marker in edge_list:
            edges.append(
                GraphEdge.model_validate(
                    cast(
                        dict[str, str | None],
                        {
                            "from": from_key,
                            "to": to_key,
                            "requirement": req_str,
                            "extra": ",".join(extras) if extras else None,
                            "marker": marker,
                            "source": SourceAdapter.pip_inspect.value,
                        },
                    )
                )
            )

        return DependencyGraph(
            nodes=nodes,
            edges=edges,
            source=SourceAdapter.pip_inspect,
            complete=True,
            root_packages=roots,
        )
