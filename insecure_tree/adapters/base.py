"""Base adapter interface and option types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from insecure_tree.models import DependencyGraph


@dataclass
class AdapterOptions:
    project_path: Path = field(default_factory=Path)
    python: Optional[str] = None
    depth: Optional[int] = None
    include_dev: bool = True
    extras: List[str] = field(default_factory=list)
    groups: List[str] = field(default_factory=list)
    requirements_files: List[str] = field(default_factory=list)
    timeout: float = 60.0


class BaseAdapter(ABC):
    @abstractmethod
    def detect(self, options: AdapterOptions) -> bool:
        """Return True if this adapter can handle the project at options.project_path."""

    @abstractmethod
    def fetch(self, options: AdapterOptions) -> DependencyGraph:
        """Build and return the dependency graph."""
