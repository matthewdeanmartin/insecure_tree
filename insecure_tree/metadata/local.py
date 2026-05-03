"""Read installed distribution metadata via importlib.metadata."""

from __future__ import annotations

import logging
from typing import Optional

from insecure_tree.models import PackageMetadata
from insecure_tree.normalize import canonicalize

log = logging.getLogger(__name__)


def read_local_dist_metadata(name: str) -> Optional[PackageMetadata]:
    """Return PackageMetadata from the locally installed distribution, or None."""
    try:
        from importlib.metadata import PackageNotFoundError, metadata
    except ImportError:
        return None

    try:
        meta = metadata(name)
    except PackageNotFoundError:
        try:
            meta = metadata(canonicalize(name))
        except PackageNotFoundError:
            return None
    except Exception as exc:
        log.debug("importlib.metadata error for %s: %s", name, exc)
        return None

    project_urls: dict = {}
    for line in meta.get_all("Project-URL") or []:
        if ", " in line:
            label, url = line.split(", ", 1)
            project_urls[label.strip()] = url.strip()

    requires = meta.get_all("Requires-Dist") or []

    return PackageMetadata(
        metadata_source="local",
        summary=meta.get("Summary") or "",
        home_page=meta.get("Home-page") or None,
        project_urls=project_urls,
        requires_dist=list(requires),
        download_url=meta.get("Download-URL") or None,
        description=meta.get_payload() if hasattr(meta, "get_payload") else "",
    )
