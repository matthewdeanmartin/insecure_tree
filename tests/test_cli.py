"""Smoke tests for the CLI entry point."""

import insecure_tree
from insecure_tree.__about__ import __version__


def test_import() -> None:
    """Package can be imported."""
    assert insecure_tree is not None


def test_version() -> None:
    """Package exposes a version string."""
    assert isinstance(__version__, str)
    assert __version__
