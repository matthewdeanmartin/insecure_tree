"""Adapter for `python -m pip inspect` (reconstructs graph from requires_dist)."""

from __future__ import annotations

import json
import logging
import shutil
import sys
from typing import Dict, List, Optional, Set

from packaging.requirements import Requirement

from insecure_tree.adapters.base import AdapterOptions, BaseAdapter
from insecure_tree.marker_eval import default_env, evaluate_marker
from insecure_tree.models import DependencyGraph, GraphEdge, PackageNode, SourceAdapter
from insecure_tree.normalize import canonicalize
from insecure_tree.subprocess import SubprocessError

log = logging.getLogger(__name__)


def _recover_partial_pip_inspect(stdout: str) -> Optional[dict]:
    """Recover valid JSON from truncated pip inspect output.

    pip inspect writes a JSON object where installed[] may be truncated mid-entry.
    Find the last complete entry by scanning backwards for a complete object boundary.
    """
    # Find the last occurrence of a pattern that ends a complete installed entry:
    # "    }," or "    }" followed by whitespace/newline
    import re
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
                return json.loads(trimmed + suffix)
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
            import subprocess as _subprocess
            # pip inspect may exit non-zero on some platforms while still writing valid JSON.
            proc = _subprocess.run(cmd, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace",
                                   cwd=options.project_path, timeout=options.timeout)
            stdout = proc.stdout
            if not stdout.strip() and proc.returncode != 0:
                raise SubprocessError(cmd, proc.returncode, proc.stderr)
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

        env = default_env()
        installed = raw.get("installed", [])

        # Build a map of normalized_name -> (name, version, requires_dist)
        pkg_map: Dict[str, tuple] = {}
        for dist in installed:
            meta = dist.get("metadata", {})
            name = meta.get("name") or dist.get("name") or ""
            version = meta.get("version") or dist.get("version") or ""
            requires_dist = meta.get("requires_dist") or []
            norm = canonicalize(name)
            pkg_map[norm] = (name, version, requires_dist)

        nodes: List[PackageNode] = []
        edges: List[GraphEdge] = []

        # Build nodes first
        depended_on: Set[str] = set()
        edge_list: List[tuple] = []

        for norm, (name, version, requires_dist) in pkg_map.items():
            from_key = f"{norm}=={version}"
            for req_str in requires_dist:
                try:
                    req = Requirement(req_str)
                except Exception:
                    continue
                if req.marker and not evaluate_marker(str(req.marker), env):
                    continue
                dep_norm = canonicalize(req.name)
                if dep_norm in pkg_map:
                    dep_version = pkg_map[dep_norm][1]
                    to_key = f"{dep_norm}=={dep_version}"
                    depended_on.add(dep_norm)
                    edge_list.append((from_key, to_key, req_str, req.extras, req.marker))

        roots: List[str] = []
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
            edges.append(GraphEdge(
                **{
                    "from": from_key,
                    "to": to_key,
                    "requirement": req_str,
                    "extra": ",".join(sorted(str(e) for e in extras)) if extras else None,
                    "marker": str(marker) if marker else None,
                    "source": SourceAdapter.pip_inspect.value,
                }
            ))

        return DependencyGraph(
            nodes=nodes,
            edges=edges,
            source=SourceAdapter.pip_inspect,
            complete=True,
            root_packages=roots,
        )
