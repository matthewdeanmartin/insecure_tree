# Reports

insecure-tree writes three report formats to the output directory (default: `insecure-tree-report/`). All three are produced by default; use `--format` to select a subset.

## Text report (`insecure-tree.txt`)

A human-readable plain-text file structured as follows:

```
insecure-tree report
====================
Project:   /home/user/myproject
Source:    uv
Scanned:   2026-05-03T14:10:00+00:00
Version:   0.1.0
zizmor:    1.24.1

Summary
-------
Packages discovered:          143
Packages with GitHub repos:    96
Repositories scanned:          91
No workflows:                  23
Repos with findings:           12
Findings:          31 warnings, 4 errors

Top findings
------------
[error] requests -> psf/requests  .github/workflows/ci.yml:42  template-injection
[warn ] rich     -> Textualize/rich  .github/workflows/release.yml:18  excessive-permissions

Packages
--------
requests==2.32.3     psf/requests         scanned        1 error
urllib3==2.2.2       urllib3/urllib3       no_workflows   -
certifi==2024.2.2    certifi/python-certifi  scanned     0
...
```

Sections:

1. **Header** — project path, source adapter, timestamp, tool versions.
2. **Summary** — package counts, scan counts, finding totals.
3. **Top findings** — highest-severity findings across all packages.
4. **Packages** — one row per package with status and finding count.
5. **Skips and failures** — packages that could not be scanned and why.
6. **Full findings** — all findings grouped by package.

## HTML report (`insecure-tree.html`)

A self-contained HTML file. No external JavaScript or CDN resources are required — everything is inlined.

Features:

- **Summary cards** — package/scan/finding counts at a glance.
- **Sortable tables** — click column headers to sort by name, status, finding count.
- **Collapsible rows** — click a package row to expand and see its findings.
- **Severity filters** — filter table to show only packages with errors, warnings, or notes.
- **Provenance columns** — package name/version, dependency path(s), the metadata field used to infer the repo, the repo URL, and the commit SHA scanned.
- **Line links** — each finding links directly to the workflow file line on GitHub using the pinned commit SHA.

## JSON report (`insecure-tree.json`)

The complete machine-readable report. Always written, even when not included in `--format`.

Top-level structure:

```json
{
  "project_path": "/home/user/myproject",
  "source_adapter": "uv",
  "scan_timestamp": "2026-05-03T14:10:00+00:00",
  "insecure_tree_version": "0.1.0",
  "zizmor_version": "1.24.1",
  "summary": { ... },
  "packages": [ ... ],
  "graph": {
    "nodes": [ ... ],
    "edges": [ ... ],
    "source": "uv",
    "complete": true
  },
  "has_findings_above_threshold": false,
  "has_partial_failures": false
}
```

Each package entry in `packages` includes:

- Package name, version, depth, dependency groups.
- Full metadata (project_urls, home_page, etc.).
- All repo candidates with confidence scores.
- The selected repo.
- The full `ScanResult`, including every `ScanFinding`.

## Re-rendering a report

You can re-render HTML or text from a saved JSON report without re-running the scan:

```bash
insecure-tree report \
  --input insecure-tree-report/insecure-tree.json \
  --format html \
  --output-dir new-report/
```

## Output directory layout

```
insecure-tree-report/
  insecure-tree.txt
  insecure-tree.html
  insecure-tree.json
  raw/                 # reserved for raw zizmor output and graph data
```
