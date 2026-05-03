"""PEP 503 name normalization and version parsing utilities."""

from __future__ import annotations

from packaging.utils import canonicalize_name
from packaging.version import Version


def canonicalize(name: str) -> str:
    """Return the PEP 503 normalized package name."""
    return canonicalize_name(name)


def parse_version(v: str) -> Version:
    """Parse a version string into a packaging.Version."""
    return Version(v)
