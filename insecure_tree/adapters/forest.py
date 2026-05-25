"""Adapter that scans the 'whole forest': all Python envs found in well-known locations.

Rather than inspecting a single project, this adapter discovers every Python
interpreter and virtual environment it can find in well-known machine-wide
locations (system site-packages, user site-packages, common venv roots, conda
environments, pipx venvs, uv tool envs, pyenv versions, etc.) and unions their
installed packages into one deduplicated graph.

Searching is deliberately limited to well-known paths so the scan finishes in
reasonable time; it does NOT do a full filesystem walk.
"""

from __future__ import annotations

import logging
import os
import platform
import sys
from pathlib import Path

from insecure_tree.adapters.base import AdapterOptions, BaseAdapter
from insecure_tree.models import DependencyGraph, GraphEdge, PackageNode, SourceAdapter
from insecure_tree.normalize import canonicalize

log = logging.getLogger(__name__)

_SYSTEM = platform.system()


# ---------------------------------------------------------------------------
# Well-known location discovery
# ---------------------------------------------------------------------------


def _windows_well_known_pythons() -> list[Path]:
    """Return candidate python.exe paths on Windows."""
    candidates: list[Path] = []

    # Python Launcher registry / standard install dirs
    for base in [
        Path(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python"),
        Path("C:/Python"),
        Path("C:/Program Files/Python"),
        Path("C:/Program Files (x86)/Python"),
    ]:
        if base.exists():
            for child in sorted(base.iterdir()):
                exe = child / "python.exe"
                if exe.is_file():
                    candidates.append(exe)

    # pyenv-win
    pyenv_root = Path(os.environ.get("PYENV_ROOT", "")) or Path.home() / ".pyenv"
    versions_dir = pyenv_root / "versions"
    if versions_dir.exists():
        for ver in sorted(versions_dir.iterdir()):
            exe = ver / "python.exe"
            if exe.is_file():
                candidates.append(exe)

    return candidates


def _posix_well_known_pythons() -> list[Path]:
    """Return candidate python paths on Linux/macOS."""
    candidates: list[Path] = []

    # System pythons
    for pattern_base in [Path("/usr/bin"), Path("/usr/local/bin"), Path("/opt/homebrew/bin")]:
        if pattern_base.exists():
            for exe in sorted(pattern_base.glob("python3*")):
                if exe.is_file() and not exe.name.endswith(("-config", "-build")):
                    candidates.append(exe)

    # pyenv
    pyenv_root = Path(os.environ.get("PYENV_ROOT", Path.home() / ".pyenv"))
    versions_dir = pyenv_root / "versions"
    if versions_dir.exists():
        for ver in sorted(versions_dir.iterdir()):
            for suffix in ["bin/python", "bin/python3"]:
                exe = ver / suffix
                if exe.is_file():
                    candidates.append(exe)
                    break

    # asdf python
    asdf_data = Path(os.environ.get("ASDF_DATA_DIR", Path.home() / ".asdf"))
    asdf_py = asdf_data / "installs" / "python"
    if asdf_py.exists():
        for ver in sorted(asdf_py.iterdir()):
            exe = ver / "bin" / "python3"
            if exe.is_file():
                candidates.append(exe)

    return candidates


_VENV_NAMES = {".venv", "venv", "env", ".env", ".tox"}


def _is_venv(path: Path) -> bool:
    return (path / "pyvenv.cfg").exists()


def _venv_python(venv_dir: Path) -> Path:
    return (venv_dir / "Scripts" / "python.exe") if _SYSTEM == "Windows" else (venv_dir / "bin" / "python")


def _find_venvs_in_dirs(roots: list[Path], depth: int = 1) -> list[Path]:
    """Scan roots for directories that look like venvs, up to *depth* levels deep.

    depth=1 (default): only immediate children of each root.
    depth=2: also scan named subdirs (`.venv`, `venv`, etc.) inside each child —
             useful when roots is a collection of project repos.
    """
    venv_pythons: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        try:
            children = list(root.iterdir())
        except PermissionError:
            continue
        for child in children:
            if not child.is_dir():
                continue
            if _is_venv(child):
                exe = _venv_python(child)
                if exe.is_file():
                    venv_pythons.append(exe)
            elif depth >= 2:
                # Treat child as a project repo root; look for named venv subdirs
                for vname in _VENV_NAMES:
                    sub = child / vname
                    if sub.is_dir() and _is_venv(sub):
                        exe = _venv_python(sub)
                        if exe.is_file():
                            venv_pythons.append(exe)
    return venv_pythons


def _conda_envs() -> list[Path]:
    """Return python executables from conda/mamba/micromamba environments."""
    pythons: list[Path] = []
    conda_roots: list[Path] = []

    for env_var in ("CONDA_ROOT", "MAMBA_ROOT_PREFIX"):
        val = os.environ.get(env_var)
        if val:
            conda_roots.append(Path(val))

    for base in [
        Path.home() / "anaconda3",
        Path.home() / "miniconda3",
        Path.home() / "mambaforge",
        Path.home() / "miniforge3",
        Path("/opt/anaconda3"),
        Path("/opt/miniconda3"),
        Path("/usr/local/anaconda3"),
    ]:
        if base.exists():
            conda_roots.append(base)

    for root in conda_roots:
        envs_dir = root / "envs"
        if envs_dir.exists():
            for env_dir in sorted(envs_dir.iterdir()):
                if not env_dir.is_dir():
                    continue
                exe = (env_dir / "python.exe") if _SYSTEM == "Windows" else (env_dir / "bin" / "python")
                if exe.is_file():
                    pythons.append(exe)
        # base env itself
        base_exe = (root / "python.exe") if _SYSTEM == "Windows" else (root / "bin" / "python")
        if base_exe.is_file():
            pythons.append(base_exe)

    return pythons


def _pipx_venvs() -> list[Path]:
    """Return python executables from pipx-managed venvs."""
    if _SYSTEM == "Windows":
        pipx_home = Path(os.environ.get("PIPX_HOME", Path(os.environ.get("LOCALAPPDATA", "")) / "pipx" / "venvs"))
    else:
        pipx_home = Path(os.environ.get("PIPX_HOME", Path.home() / ".local" / "pipx" / "venvs"))

    return _find_venvs_in_dirs([pipx_home])


def _uv_tool_venvs() -> list[Path]:
    """Return python executables from uv tool-managed venvs."""
    if _SYSTEM == "Windows":
        uv_home = Path(os.environ.get("UV_TOOL_DIR", Path(os.environ.get("LOCALAPPDATA", "")) / "uv" / "tools"))
    else:
        uv_home = Path(os.environ.get("UV_TOOL_DIR", Path.home() / ".local" / "share" / "uv" / "tools"))

    return _find_venvs_in_dirs([uv_home])


def _common_venv_roots() -> list[Path]:
    """User-level directories where people commonly keep venvs."""
    roots = [
        Path.home() / ".venvs",
        Path.home() / "venvs",
        Path.home() / "envs",
        Path.home() / ".virtualenvs",  # virtualenvwrapper default
        Path.home() / "Envs",  # virtualenvwrapper on Windows
        Path.home() / ".tox",  # tox puts test envs here by default
    ]
    # workon_home for virtualenvwrapper
    workon = os.environ.get("WORKON_HOME")
    if workon:
        roots.append(Path(workon))
    return roots


def discover_all_pythons(extra_paths: list[Path] | None = None) -> list[Path]:
    """Return a deduplicated list of Python executables to inspect."""
    seen: set[Path] = set()
    result: list[Path] = []

    def _add(p: Path) -> None:
        try:
            resolved = p.resolve()
        except Exception:
            resolved = p
        if resolved not in seen:
            seen.add(resolved)
            result.append(p)

    # Always include the interpreter running right now
    _add(Path(sys.executable))

    # System-level / version-manager pythons
    if _SYSTEM == "Windows":
        for p in _windows_well_known_pythons():
            _add(p)
    else:
        for p in _posix_well_known_pythons():
            _add(p)

    # Virtualenvs in common roots
    for p in _find_venvs_in_dirs(_common_venv_roots()):
        _add(p)

    # Tool-specific env managers
    for p in _conda_envs():
        _add(p)
    for p in _pipx_venvs():
        _add(p)
    for p in _uv_tool_venvs():
        _add(p)

    # Caller-supplied extra paths — search two levels deep so that a directory
    # full of project repos (e.g. /c/github) finds venvs inside each repo.
    for ep in extra_paths or []:
        if ep.is_file():
            _add(ep)
        elif ep.is_dir():
            for p in _find_venvs_in_dirs([ep], depth=2):
                _add(p)

    return result


# ---------------------------------------------------------------------------
# pip inspect → PackageNode list (minimal, no graph edges needed per env)
# ---------------------------------------------------------------------------


def _packages_via_uv(python: Path, timeout: float) -> list[tuple[str, str, str]] | None:
    """Try `uv pip list --format json` for this interpreter. Returns None if uv unavailable."""
    import json
    import shutil

    if not shutil.which("uv"):
        return None

    from insecure_tree.subprocess import run_subprocess

    cmd = ["uv", "pip", "list", "--python", str(python), "--format", "json"]
    try:
        rc, stdout, _ = run_subprocess(cmd, timeout=timeout, check=False)
    except Exception as exc:
        log.debug("uv pip list failed for %s: %s", python, exc)
        return None

    if rc != 0 or not stdout.strip():
        return None

    try:
        raw = json.loads(stdout)
    except Exception:
        return None

    if not isinstance(raw, list):
        return None

    return [(item["name"], item["version"], canonicalize(item["name"])) for item in raw if item.get("name") and item.get("version")]


def _packages_via_pip_inspect(python: Path, timeout: float) -> list[tuple[str, str, str]]:
    """Return [(name, version, normalized_name)] via `pip inspect`.

    Returns an empty list on any failure.
    """
    import json

    from insecure_tree.subprocess import run_subprocess

    cmd = [str(python), "-m", "pip", "inspect", "--isolated"]
    try:
        _, stdout, _ = run_subprocess(cmd, timeout=timeout, check=False)
    except Exception as exc:
        log.debug("pip inspect failed for %s: %s", python, exc)
        return []

    if not stdout.strip():
        return []

    try:
        raw = json.loads(stdout)
    except Exception:
        return []

    packages: list[tuple[str, str, str]] = []
    for dist in raw.get("installed", []):
        meta = dist.get("metadata", {})
        name = meta.get("name") or dist.get("name") or ""
        version = meta.get("version") or dist.get("version") or ""
        if name and version:
            packages.append((name, version, canonicalize(name)))
    return packages


def _pip_inspect_packages(python: Path, timeout: float) -> list[tuple[str, str, str]]:
    """Return packages for this interpreter, trying uv first then pip inspect."""
    result = _packages_via_uv(python, timeout)
    if result is not None:
        return result
    return _packages_via_pip_inspect(python, timeout)


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class ForestAdapter(BaseAdapter):
    """Scan the whole machine: unions packages from all discoverable Python envs."""

    def detect(self, options: AdapterOptions) -> bool:
        return False  # never auto-selected; must be requested explicitly

    def fetch(self, options: AdapterOptions) -> DependencyGraph:
        extra_paths = getattr(options, "forest_search_paths", None) or []
        pythons = discover_all_pythons(extra_paths)

        log.info("Forest scan: found %d Python interpreters to inspect", len(pythons))

        # Deduplicate packages across all envs by (normalized_name, version)
        seen: dict[tuple[str, str], PackageNode] = {}

        for python in pythons:
            log.debug("Forest: inspecting %s", python)
            pkgs = _pip_inspect_packages(python, options.timeout)
            for name, version, norm in pkgs:
                key = (norm, version)
                if key not in seen:
                    seen[key] = PackageNode(
                        name=name,
                        normalized_name=norm,
                        version=version,
                        source=SourceAdapter.forest.value,
                        requested=True,
                        depth=0,
                    )

        nodes = list(seen.values())
        edges: list[GraphEdge] = []
        roots = [f"{n.normalized_name}=={n.version}" for n in nodes]

        log.info("Forest scan: %d unique packages discovered across all environments", len(nodes))

        return DependencyGraph(
            nodes=nodes,
            edges=edges,
            source=SourceAdapter.forest,
            complete=False,  # flat union; no dependency graph edges
            root_packages=roots,
        )
