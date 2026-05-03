"""PEP 508 environment marker evaluation."""

from __future__ import annotations

from packaging.markers import Marker, default_environment


def default_env() -> dict[str, str]:
    """Return the current environment marker dict."""
    return {key: str(value) for key, value in default_environment().items()}


def evaluate_marker(marker_str: str, env: dict[str, str] | None = None) -> bool:
    """Evaluate a PEP 508 marker string against env (defaults to current env)."""
    if not marker_str:
        return True
    marker = Marker(marker_str)
    return bool(marker.evaluate(env or default_env()))
