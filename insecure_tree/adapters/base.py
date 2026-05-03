"""Base adapter interface and option types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from insecure_tree.models import DependencyGraph


@dataclass
class AdapterOptions:
    project_path: Path = field(default_factory=Path)
    python: str | None = None
    depth: int | None = None
    include_dev: bool = True
    extras: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    requirements_files: list[str] = field(default_factory=list)
    timeout: float = 60.0


class BaseAdapter(ABC):
    @abstractmethod
    def detect(self, options: AdapterOptions) -> bool:
        """Return True if this adapter can handle the project at options.project_path."""

    @abstractmethod
    def fetch(self, options: AdapterOptions) -> DependencyGraph:
        """Build and return the dependency graph."""
