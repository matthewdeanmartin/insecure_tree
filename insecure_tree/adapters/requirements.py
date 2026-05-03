"""Adapter that parses requirements.txt files."""

from __future__ import annotations

import logging
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement

from insecure_tree.adapters.base import AdapterOptions, BaseAdapter
from insecure_tree.models import DependencyGraph, PackageNode, SourceAdapter
from insecure_tree.normalize import canonicalize

log = logging.getLogger(__name__)


def _find_requirements_files(project_path: Path) -> list[Path]:
    patterns = ["requirements.txt", "requirements-*.txt", "requirements/*.txt"]
    found: list[Path] = []
    for pattern in patterns:
        found.extend(sorted(project_path.glob(pattern)))
    return found


class RequirementsAdapter(BaseAdapter):
    def detect(self, options: AdapterOptions) -> bool:
        if options.requirements_files:
            return True
        return bool(_find_requirements_files(options.project_path))

    def fetch(self, options: AdapterOptions) -> DependencyGraph:
        files: list[Path] = []
        if options.requirements_files:
            files = [Path(f) for f in options.requirements_files]
        else:
            files = _find_requirements_files(options.project_path)

        nodes: list[PackageNode] = []
        seen_norms: set[str] = set()

        for req_file in files:
            try:
                lines = req_file.read_text(encoding="utf-8").splitlines()
            except OSError as exc:
                log.warning("Cannot read %s: %s", req_file, exc)
                continue

            for line in lines:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                try:
                    req = Requirement(line)
                except InvalidRequirement:
                    continue
                norm = canonicalize(req.name)
                if norm in seen_norms:
                    continue
                seen_norms.add(norm)

                version = ""
                for spec in req.specifier:
                    if spec.operator == "==":
                        version = spec.version
                        break

                nodes.append(PackageNode(
                    name=req.name,
                    normalized_name=norm,
                    version=version,
                    source=SourceAdapter.requirements.value,
                    requested=True,
                    depth=0,
                ))

        return DependencyGraph(
            nodes=nodes,
            edges=[],
            source=SourceAdapter.requirements,
            complete=False,
            root_packages=[f"{n.normalized_name}=={n.version}" for n in nodes],
        )
