"""Fetch package metadata from the PyPI JSON API."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from insecure_tree.cache import Cache
from insecure_tree.models import PackageMetadata

log = logging.getLogger(__name__)

_PYPI_BASE = "https://pypi.org/pypi"


def _parse_pypi_response(data: dict[str, Any]) -> PackageMetadata | None:
    try:
        info = data["info"]
        if not isinstance(info, dict):
            return None
        project_urls_raw = info.get("project_urls") or {}
        project_urls = (
            {str(key): str(value) for key, value in project_urls_raw.items() if value}
            if isinstance(project_urls_raw, dict)
            else {}
        )
        requires_dist_raw = info.get("requires_dist") or []
        requires_dist = [str(item) for item in requires_dist_raw] if isinstance(requires_dist_raw, list) else []
        return PackageMetadata(
            index_url=f"{_PYPI_BASE}/{info['name']}/{info['version']}/json",
            metadata_source="pypi-json",
            summary=info.get("summary") or "",
            home_page=info.get("home_page") or None,
            project_urls=project_urls,
            requires_dist=requires_dist,
            download_url=info.get("download_url") or None,
            docs_url=info.get("docs_url") or None,
            description=info.get("description") or "",
        )
    except (KeyError, TypeError) as exc:
        log.debug("Failed to parse PyPI response: %s", exc)
        return None


async def fetch_pypi_metadata(
    name: str,
    version: str | None,
    *,
    session: httpx.AsyncClient,
    cache: Cache,
    ttl: int,
) -> PackageMetadata | None:
    """Fetch metadata from PyPI JSON API with caching."""
    cache_key = f"{name}=={version}" if version else f"{name}==latest"

    cached = cache.get_json("pypi", cache_key)
    if cached is not None and isinstance(cached, dict):
        return _parse_pypi_response(cached)

    url = f"{_PYPI_BASE}/{name}/{version}/json" if version else f"{_PYPI_BASE}/{name}/json"

    try:
        resp = await session.get(url)
        if resp.status_code == 404 and version:
            # Fallback to latest
            log.debug("Exact version %s==%s not on PyPI, trying latest", name, version)
            resp = await session.get(f"{_PYPI_BASE}/{name}/json")
        if resp.status_code != 200:
            log.debug("PyPI returned %d for %s", resp.status_code, name)
            return None
        data = resp.json()
    except Exception as exc:
        log.warning("PyPI fetch failed for %s: %s", name, exc)
        return None

    cache.put_json("pypi", cache_key, data, ttl)
    if not isinstance(data, dict):
        return None
    return _parse_pypi_response(data)
