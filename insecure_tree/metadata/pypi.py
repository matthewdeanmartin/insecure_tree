"""Fetch package metadata from the PyPI JSON API."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from insecure_tree.cache import Cache
from insecure_tree.models import PackageMetadata

log = logging.getLogger(__name__)

_PYPI_BASE = "https://pypi.org/pypi"


def _parse_pypi_response(data: dict, version: Optional[str]) -> Optional[PackageMetadata]:
    try:
        info = data["info"]
        project_urls: dict = info.get("project_urls") or {}
        requires_dist = info.get("requires_dist") or []
        return PackageMetadata(
            index_url=f"{_PYPI_BASE}/{info['name']}/{info['version']}/json",
            metadata_source="pypi-json",
            summary=info.get("summary") or "",
            home_page=info.get("home_page") or None,
            project_urls={k: v for k, v in project_urls.items() if v},
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
    version: Optional[str],
    *,
    session: httpx.AsyncClient,
    cache: Cache,
    ttl: int,
) -> Optional[PackageMetadata]:
    """Fetch metadata from PyPI JSON API with caching."""
    cache_key = f"{name}=={version}" if version else f"{name}==latest"

    cached = cache.get_json("pypi", cache_key)
    if cached is not None and isinstance(cached, dict):
        return _parse_pypi_response(cached, version)

    if version:
        url = f"{_PYPI_BASE}/{name}/{version}/json"
    else:
        url = f"{_PYPI_BASE}/{name}/json"

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
    return _parse_pypi_response(data, version)
