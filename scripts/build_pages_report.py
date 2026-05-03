"""Build the checked-in GitHub Pages report for a self-scan."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PAGES_DIRNAME = "pages"
REPORT_FILENAME = "insecure-tree.html"
INDEX_FILENAME = "index.html"


def _repo_root() -> Path:
    """Return the repository root."""
    return Path(__file__).resolve().parent.parent


def _run_self_scan(repo_root: Path, output_dir: Path) -> None:
    """Run insecure-tree against this repository and write HTML output to output_dir."""
    command = [
        sys.executable,
        "-m",
        "insecure_tree.cli",
        "scan",
        "--source",
        "pipdeptree",
        "--project",
        str(repo_root),
        "--format",
        "html",
        "--output-dir",
        str(output_dir),
    ]
    subprocess.run(command, check=True, cwd=repo_root)


def build_pages_report() -> Path:
    """Generate the GitHub Pages site contents and return the index path."""
    repo_root = _repo_root()
    pages_dir = repo_root / PAGES_DIRNAME

    with tempfile.TemporaryDirectory(prefix="insecure-tree-pages-", dir=repo_root) as temp_dir:
        temp_root = Path(temp_dir)
        scan_output_dir = temp_root / "scan-output"
        site_dir = temp_root / "site"
        scan_output_dir.mkdir()
        site_dir.mkdir()

        _run_self_scan(repo_root, scan_output_dir)
        shutil.copy2(scan_output_dir / REPORT_FILENAME, site_dir / INDEX_FILENAME)
        (site_dir / ".nojekyll").write_text("", encoding="utf-8")

        if pages_dir.exists():
            shutil.rmtree(pages_dir)
        shutil.copytree(site_dir, pages_dir)

    return pages_dir / INDEX_FILENAME


def main() -> int:
    """Build the checked-in Pages report."""
    index_path = build_pages_report()
    print(f"Pages report written to {index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
