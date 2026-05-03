"""Read installed distribution metadata via importlib.metadata."""

from __future__ import annotations

import logging

from insecure_tree.models import PackageMetadata as ProjectMetadata
from insecure_tree.normalize import canonicalize

log = logging.getLogger(__name__)


def read_local_dist_metadata(name: str) -> ProjectMetadata | None:
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

    meta_values: dict[str, str] = {key: meta[key] for key in meta}
    project_urls: dict[str, str] = {}
    for line in meta.get_all("Project-URL") or []:
        if ", " in line:
            label, url = line.split(", ", 1)
            project_urls[label.strip()] = url.strip()

    requires = meta.get_all("Requires-Dist") or []

    return ProjectMetadata(
        metadata_source="local",
        summary=meta_values.get("Summary", ""),
        home_page=meta_values.get("Home-page"),
        project_urls=project_urls,
        requires_dist=list(requires),
        download_url=meta_values.get("Download-URL"),
        description=meta.get_payload() if hasattr(meta, "get_payload") else "",
    )
