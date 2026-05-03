"""Plain-text report writer."""

from __future__ import annotations

from pathlib import Path

from insecure_tree.models import Report, ScanStatus

_SEV_BADGE = {"error": "[error]", "warning": "[warn ]", "note": "[note ]"}


def _badge(sev: str) -> str:
    return _SEV_BADGE.get(sev, f"[{sev[:5]:<5}]")


def _findings_summary(by_sev: dict[str, int]) -> str:
    parts = []
    for sev in ("error", "warning", "note"):
        count = by_sev.get(sev, 0)
        if count:
            parts.append(f"{count} {sev}{'s' if count != 1 else ''}")
    return ", ".join(parts) if parts else "none"


def write_text(report: Report, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []

    def h1(s: str) -> None:
        lines.append(s)
        lines.append("=" * len(s))

    def h2(s: str) -> None:
        lines.append(s)
        lines.append("-" * len(s))

    h1("insecure-tree report")
    lines.append(f"Project:  {report.project_path}")
    lines.append(f"Source:   {report.source_adapter}")
    lines.append(f"Scanned:  {report.scan_timestamp}")
    lines.append(f"Version:  insecure-tree {report.insecure_tree_version}")
    if report.zizmor_version:
        lines.append(f"          zizmor {report.zizmor_version}")
    lines.append("")

    s = report.summary
    h2("Summary")
    lines.append(f"{'Packages discovered:':<35}{s.total_packages:>5}")
    lines.append(f"{'Packages with GitHub repos:':<35}{s.packages_with_github:>5}")
    lines.append(f"{'Repositories scanned:':<35}{s.repos_scanned:>5}")
    lines.append(f"{'No workflows:':<35}{s.repos_no_workflows:>5}")
    lines.append(f"{'Repos with findings:':<35}{s.repos_with_findings:>5}")
    lines.append(f"{'Findings:':<35}  {_findings_summary(s.findings_by_severity)}")
    lines.append("")

    # Top findings
    top: list[tuple[str, str, str, str, int, str]] = []
    for pkg in report.packages:
        if pkg.scan and pkg.scan.findings:
            repo = pkg.selected_repo
            repo_str = f"{repo.owner}/{repo.repo}" if repo else "?"
            for f in pkg.scan.findings:
                top.append((f.severity, pkg.name, repo_str, f.path, f.line, f.rule_id))
    if top:
        _sev_order = {"error": 0, "warning": 1, "note": 2}
        top.sort(key=lambda t: (_sev_order.get(t[0], 9), t[1]))
        h2("Top findings")
        for sev, name, repo_str, fpath, fline, rule in top[:20]:
            lines.append(f"{_badge(sev)} {name:<20} -> {repo_str} {fpath}:{fline} {rule}")
        lines.append("")

    # Package table
    h2("Packages")
    header = f"{'Package':<35} {'Repo':<30} {'Status':<20} {'Findings'}"
    lines.append(header)
    lines.append("-" * len(header))
    for pkg in sorted(report.packages, key=lambda p: p.normalized_name):
        repo = pkg.selected_repo
        repo_str = f"{repo.owner}/{repo.repo}" if repo else "-"
        scan = pkg.scan
        if scan:
            status = scan.status.value
            findings_str = _findings_summary(scan.findings_by_severity) if scan.finding_count else "-"
        else:
            status = ScanStatus.no_repo.value
            findings_str = "-"
        name_ver = f"{pkg.name}=={pkg.version}"
        lines.append(f"{name_ver:<35} {repo_str:<30} {status:<20} {findings_str}")
    lines.append("")

    # Skips and failures
    failed = [p for p in report.packages if p.scan and p.scan.status not in (
        ScanStatus.scanned, ScanStatus.no_repo, ScanStatus.no_workflows, ScanStatus.skipped_cached
    )]
    if failed:
        h2("Failures")
        for pkg in failed:
            err = pkg.scan.error_message if pkg.scan else ""
            lines.append(f"  {pkg.name}=={pkg.version}: {pkg.scan.status.value if pkg.scan else '?'} {err}")
        lines.append("")

    # Full findings
    h2("Full findings")
    any_findings = False
    for pkg in report.packages:
        if not pkg.scan or not pkg.scan.findings:
            continue
        repo = pkg.selected_repo
        repo_str = f"{repo.owner}/{repo.repo}" if repo else "?"
        lines.append(f"\n{pkg.name}=={pkg.version} ({repo_str} @ {pkg.scan.repo_ref or '?'})")
        for f in pkg.scan.findings:
            lines.append(f"  {_badge(f.severity)} [{f.rule_id}] {f.path}:{f.line}")
            lines.append(f"          {f.message}")
            if f.url:
                lines.append(f"          {f.url}")
        any_findings = True
    if not any_findings:
        lines.append("  (no findings)")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
