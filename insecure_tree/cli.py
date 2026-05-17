"""Command-line entry point for insecure-tree."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from insecure_tree.__about__ import __version__

log = logging.getLogger("insecure_tree")

if TYPE_CHECKING:
    from insecure_tree.config import Config


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def _is_interactive() -> bool:
    """Return True only when both stdin and stdout are real TTYs."""
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except Exception:
        return False


def _prompt(message: str, default: str = "", password: bool = False) -> str:
    """Prompt interactively via prompt_toolkit when on a TTY, else return default."""
    if not _is_interactive():
        return default
    try:
        from prompt_toolkit import prompt as pt_prompt

        result = pt_prompt(message, is_password=password, default=default)
        return result.strip()
    except Exception:
        return default


def _prompt_choices(message: str, choices: list[str], default: str) -> str:
    """Prompt with tab-completion for a fixed set of choices."""
    if not _is_interactive():
        return default
    try:
        from prompt_toolkit import prompt as pt_prompt
        from prompt_toolkit.completion import WordCompleter

        completer = WordCompleter(choices, ignore_case=True)
        result = pt_prompt(message, completer=completer, default=default)
        result = result.strip()
        return result if result in choices else default
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Subcommand: scan
# ---------------------------------------------------------------------------


def _add_common_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source",
        default="auto",
        choices=["auto", "uv", "uv-pip", "pip-inspect", "pipdeptree", "requirements", "json"],
        help="Dependency source adapter",
    )
    parser.add_argument("--project", default=".", metavar="PATH", help="Project root directory")
    parser.add_argument("--python", default=None, metavar="PYTHON", help="Python interpreter path")
    parser.add_argument(
        "--requirements", action="append", default=[], metavar="FILE", help="requirements.txt file(s); repeatable"
    )
    parser.add_argument("--depth", type=int, default=None, metavar="N", help="Max dependency depth")
    parser.add_argument("--include-dev", action="store_true", default=True)
    parser.add_argument("--exclude-dev", dest="include_dev", action="store_false")


def _add_output_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output-dir", default="insecure-tree-report", metavar="DIR")
    parser.add_argument(
        "--format",
        action="append",
        dest="formats",
        default=[],
        choices=["text", "html", "json"],
        help="Output format(s); repeatable (default: text html json)",
    )


def _add_github_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--github-token", default=None, metavar="TOKEN")
    parser.add_argument("--github-token-env", default="GITHUB_TOKEN", metavar="VAR")
    parser.add_argument("--repo-fetch", default="api", choices=["auto", "api", "git", "archive"])


def _add_zizmor_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--zizmor-bin", default="zizmor", metavar="BIN")
    parser.add_argument("--zizmor-arg", action="append", dest="zizmor_args", default=[], metavar="ARG")


def _add_behavior_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--fail-on", default="never", choices=["error", "warning", "note", "never"])
    parser.add_argument("--report-min-severity", default="note", choices=["error", "warning", "note"])
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--no-clone", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--fail-on-partial", action="store_true")
    parser.add_argument("--concurrency", type=int, default=None)
    parser.add_argument("--repo-override", action="append", default=[], metavar="PKG=OWNER/REPO")
    parser.add_argument("--ignore-package", action="append", default=[], metavar="PACKAGE")


def _build_config(args: argparse.Namespace) -> Config:
    from insecure_tree.config import load_config
    from insecure_tree.models import FetchMode, ReportFormat, SourceAdapter

    project_path = Path(getattr(args, "project", ".")).resolve()
    config = load_config(project_path)

    # Map CLI args onto config
    source_raw = getattr(args, "source", "auto")
    with contextlib.suppress(ValueError):
        config = config.model_copy(update={"source": SourceAdapter(source_raw)})

    config = config.model_copy(update={"project": str(project_path)})

    if getattr(args, "python", None):
        config = config.model_copy(update={"python": args.python})
    if getattr(args, "depth", None) is not None:
        config = config.model_copy(update={"depth": args.depth})
    if hasattr(args, "include_dev"):
        config = config.model_copy(update={"include_dev": args.include_dev})
    if getattr(args, "requirements", []):
        config = config.model_copy(update={"requirements": args.requirements})
    if getattr(args, "output_dir", None):
        config = config.model_copy(update={"output_dir": args.output_dir})
    if getattr(args, "fail_on", None):
        config = config.model_copy(update={"fail_on": args.fail_on})
    if getattr(args, "report_min_severity", None):
        config = config.model_copy(update={"report_min_severity": args.report_min_severity})
    if getattr(args, "no_cache", False):
        config = config.model_copy(update={"no_cache": True})
    if getattr(args, "refresh", False):
        config = config.model_copy(update={"refresh": True})
    if getattr(args, "offline", False):
        config = config.model_copy(update={"offline": True})
    if getattr(args, "no_clone", False):
        config = config.model_copy(update={"no_clone": True})
    if getattr(args, "strict", False):
        config = config.model_copy(update={"strict": True})
    if getattr(args, "fail_on_partial", False):
        config = config.model_copy(update={"fail_on_partial": True})
    if getattr(args, "concurrency", None) is not None:
        config = config.model_copy(update={"concurrency": args.concurrency})

    # formats
    formats_raw = getattr(args, "formats", [])
    if formats_raw:
        config = config.model_copy(update={"formats": [ReportFormat(f) for f in formats_raw]})

    # GitHub
    token = getattr(args, "github_token", None) or os.environ.get(getattr(args, "github_token_env", "GITHUB_TOKEN"))
    from insecure_tree.models import GitHubConfig

    gh = GitHubConfig(token_env=getattr(args, "github_token_env", "GITHUB_TOKEN"), token=token)
    config = config.model_copy(update={"github": gh})

    # zizmor
    from insecure_tree.models import ZizmorphConfig

    zizmor_bin = getattr(args, "zizmor_bin", "zizmor")
    zizmor_args = getattr(args, "zizmor_args", [])
    config = config.model_copy(update={"zizmor": ZizmorphConfig(bin=zizmor_bin, args=zizmor_args)})

    # repo overrides
    overrides = dict(config.repo_overrides)
    for item in getattr(args, "repo_override", []):
        if "=" in item:
            pkg, url = item.split("=", 1)
            overrides[pkg.strip()] = url.strip()
    config = config.model_copy(update={"repo_overrides": overrides})

    # repo fetch mode
    fetch_raw = getattr(args, "repo_fetch", "api")
    config = config.model_copy(update={"repo_fetch": FetchMode(fetch_raw)})

    return config


def _interactive_fill_scan_args(args: argparse.Namespace) -> None:
    """Prompt for commonly-missing scan arguments when running interactively."""
    if not sys.stdin.isatty():
        return

    # GitHub token
    token_env = getattr(args, "github_token_env", "GITHUB_TOKEN")
    if not getattr(args, "github_token", None) and not os.environ.get(token_env):
        token = _prompt("GitHub token (leave blank to skip private repos): ", password=True)
        if token:
            args.github_token = token

    # Project path (only prompt if explicitly "." and a uv.lock/pyproject doesn't exist there)
    project = Path(getattr(args, "project", ".")).resolve()
    if not (project / "uv.lock").exists() and not (project / "pyproject.toml").exists():
        given = _prompt(f"Project path [{project}]: ", default=str(project))
        if given:
            args.project = given


def cmd_scan(args: argparse.Namespace) -> int:
    from insecure_tree.models import ReportFormat
    from insecure_tree.pipeline import run_scan
    from insecure_tree.report.html import write_html
    from insecure_tree.report.json import write_json
    from insecure_tree.report.text import write_text
    from insecure_tree.scanners.zizmor import ScanInfraError

    _interactive_fill_scan_args(args)
    config = _build_config(args)
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    _show_progress = sys.stdout.isatty()

    try:
        report = asyncio.run(run_scan(config))
    except ScanInfraError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("Hint: install zizmor via 'pip install zizmor' or 'cargo install zizmor'", file=sys.stderr)
        return 3
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        log.exception("Scan infrastructure error")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3

    formats = config.formats
    if not formats:
        formats = [ReportFormat.text, ReportFormat.html, ReportFormat.json]

    # Always write JSON
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(exist_ok=True)

    for fmt in formats:
        if fmt == ReportFormat.json:
            write_json(report, output_dir / "insecure-tree.json")
        elif fmt == ReportFormat.text:
            write_text(report, output_dir / "insecure-tree.txt")
        elif fmt == ReportFormat.html:
            write_html(report, output_dir / "insecure-tree.html")

    # Always write JSON if not already
    if ReportFormat.json not in formats:
        write_json(report, output_dir / "insecure-tree.json")

    # Print summary to stdout
    s = report.summary
    print("\ninsecure-tree scan complete")
    print(f"  Packages: {s.total_packages}  GitHub repos: {s.packages_with_github}  Scanned: {s.repos_scanned}")
    findings_str = ", ".join(f"{v} {k}" for k, v in s.findings_by_severity.items() if v) or "none"
    print(f"  Findings: {findings_str}")
    print(f"  Report:   {output_dir}")

    if report.has_findings_above_threshold:
        return 1
    if report.has_partial_failures and config.fail_on_partial:
        return 4
    return 0


# ---------------------------------------------------------------------------
# Subcommand: graph
# ---------------------------------------------------------------------------


def cmd_graph(args: argparse.Namespace) -> int:
    from insecure_tree.adapters.base import AdapterOptions

    config = _build_config(args)
    project_path = Path(config.project).resolve()
    options = AdapterOptions(
        project_path=project_path,
        python=config.python,
        depth=config.depth,
        include_dev=config.include_dev,
        requirements_files=config.requirements,
        timeout=config.timeout,
    )

    from insecure_tree.pipeline import _choose_adapter

    adapter = _choose_adapter(config.source, options, config)
    graph = adapter.fetch(options)

    out_format = getattr(args, "graph_format", "json")
    if out_format == "json":
        print(graph.model_dump_json(indent=2))
    else:
        for node in graph.nodes:
            print(f"{node.name}=={node.version}")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: metadata
# ---------------------------------------------------------------------------


def cmd_metadata(args: argparse.Namespace) -> int:
    from insecure_tree.cache import Cache
    from insecure_tree.metadata.github_urls import extract_github_candidates
    from insecure_tree.metadata.pypi import fetch_pypi_metadata

    package = args.package
    version = getattr(args, "version", None)

    async def _run() -> None:
        cache = Cache()
        async with httpx.AsyncClient(timeout=30) as session:
            meta = await fetch_pypi_metadata(package, version, session=session, cache=cache, ttl=3600)
        if meta is None:
            print(f"No metadata found for {package}", file=sys.stderr)
            return
        print(json.dumps(meta.model_dump(), indent=2))
        candidates = extract_github_candidates(meta)
        print(f"\nGitHub candidates ({len(candidates)}):")
        for c in candidates:
            print(f"  [{c.confidence.value}] {c.url}  (from {c.source_field})")

    asyncio.run(_run())
    return 0


# ---------------------------------------------------------------------------
# Subcommand: report
# ---------------------------------------------------------------------------


def cmd_report(args: argparse.Namespace) -> int:
    from insecure_tree.models import Report
    from insecure_tree.report.html import write_html
    from insecure_tree.report.json import write_json
    from insecure_tree.report.text import write_text

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: {input_path} not found", file=sys.stderr)
        return 2

    report = Report.model_validate_json(input_path.read_text(encoding="utf-8"))
    output_dir = Path(getattr(args, "output_dir", "insecure-tree-report"))
    output_dir.mkdir(parents=True, exist_ok=True)

    for fmt in getattr(args, "formats", []) or ["text", "html"]:
        if fmt == "json":
            write_json(report, output_dir / "insecure-tree.json")
        elif fmt == "text":
            write_text(report, output_dir / "insecure-tree.txt")
        elif fmt == "html":
            write_html(report, output_dir / "insecure-tree.html")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: cache
# ---------------------------------------------------------------------------


def cmd_cache(args: argparse.Namespace) -> int:
    from insecure_tree.cache import Cache, platform_cache_dir

    subcmd = getattr(args, "cache_cmd", "dir")
    if subcmd == "dir":
        print(platform_cache_dir())
    elif subcmd == "clean":
        older_than = getattr(args, "older_than", None)
        cache = Cache()
        if older_than:
            seconds = _parse_duration(older_than)
            n = cache.evict_older_than(seconds)
        else:
            n = cache.clean()
        print(f"Removed {n} cache entries")
    return 0


def _parse_duration(s: str) -> int:
    units = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    for suffix, mult in units.items():
        if s.endswith(suffix):
            return int(s[:-1]) * mult
    return int(s)


# ---------------------------------------------------------------------------
# Parser assembly
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="insecure-tree",
        description="Audit GitHub Actions security posture of your Python dependency tree",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true")

    sub = parser.add_subparsers(dest="command")

    # scan
    scan_p = sub.add_parser("scan", help="Run the full audit pipeline")
    _add_common_source_args(scan_p)
    _add_output_args(scan_p)
    _add_github_args(scan_p)
    _add_zizmor_args(scan_p)
    _add_behavior_args(scan_p)

    # graph
    graph_p = sub.add_parser("graph", help="Emit dependency graph only")
    _add_common_source_args(graph_p)
    graph_p.add_argument("--format", dest="graph_format", default="json", choices=["json", "text"])

    # metadata
    meta_p = sub.add_parser("metadata", help="Inspect PyPI metadata and GitHub candidates for a package")
    meta_p.add_argument("package", help="Package name")
    meta_p.add_argument("--version", dest="version", default=None)

    # report
    report_p = sub.add_parser("report", help="Re-render a report from saved JSON")
    report_p.add_argument("--input", required=True, metavar="JSON_FILE")
    _add_output_args(report_p)

    # cache
    cache_p = sub.add_parser("cache", help="Manage the local cache")
    cache_sub = cache_p.add_subparsers(dest="cache_cmd")
    cache_sub.add_parser("dir", help="Print cache directory")
    clean_p = cache_sub.add_parser("clean", help="Clean expired cache entries")
    clean_p.add_argument("--older-than", metavar="DURATION", help="e.g. 30d, 12h")

    return parser


def main() -> None:
    """Run the insecure-tree CLI."""
    parser = _build_parser()
    args = parser.parse_args()
    _setup_logging(getattr(args, "verbose", False))

    command = getattr(args, "command", None)

    if command is None:
        parser.print_help()
        sys.exit(0)

    handlers = {
        "scan": cmd_scan,
        "graph": cmd_graph,
        "metadata": cmd_metadata,
        "report": cmd_report,
        "cache": cmd_cache,
    }

    handler = handlers.get(command)
    if handler is None:
        parser.print_help()
        sys.exit(2)

    try:
        exit_code = handler(args)
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
