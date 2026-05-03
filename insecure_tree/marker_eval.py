"""PEP 508 environment marker evaluation."""

from __future__ import annotations

from typing import Dict, Optional

from packaging.markers import Marker, default_environment


def default_env() -> Dict[str, str]:
    """Return the current environment marker dict."""
    return default_environment()


def evaluate_marker(marker_str: str, env: Optional[Dict[str, str]] = None) -> bool:
    """Evaluate a PEP 508 marker string against env (defaults to current env)."""
    if not marker_str:
        return True
    marker = Marker(marker_str)
    return bool(marker.evaluate(env or default_env()))
