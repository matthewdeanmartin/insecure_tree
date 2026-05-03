# insecure-tree CLI Spec

## 1. Summary

`insecure-tree` is a local CLI tool that audits the GitHub Actions security posture of the upstream repositories behind a Python dependency graph.

It discovers Python dependencies from supported sources, resolves each dependency’s package metadata, extracts claimed GitHub repository URLs, scans those repositories’ GitHub Actions workflows with `zizmor`, and writes both text and HTML reports.

The tool is intended for developer workstations and CI jobs. It is not a vulnerability scanner for package code. Its focus is: “Which of my Python dependencies claim GitHub repos, and do those repos have suspicious or insecure GitHub Actions workflows?”

## 2. Goals

* Build a dependency graph for a Python project or environment.
* Support dependency graphs from:

  * `uv` project mode.
  * `uv pip` environment mode.
  * Generic installed-environment mode using `pip inspect` plus local metadata parsing.
  * Optional external adapters such as `pipdeptree` when available.
* Fetch package metadata from PyPI-compatible JSON APIs.
* Identify packages that claim a GitHub repository in package metadata.
* Clone or fetch the claimed GitHub repositories safely.
* Run `zizmor` against the repositories’ GitHub Actions workflows.
* Produce deterministic text and HTML reports.
* Cache metadata, repository checkouts, and scan results.
* Make false positives and provenance ambiguity obvious in the report.

## 3. Non-goals

* Do not execute dependency package code.
* Do not install project dependencies unless explicitly requested by a future command.
* Do not judge whether PyPI metadata is truthful; only report claimed repositories and confidence.
* Do not scan non-GitHub CI systems in v1.
* Do not open pull requests or issues in upstream repositories in v1.
* Do not require GitHub authentication for public repositories, though authentication should be supported for rate-limit relief and private/internal dependency graphs.

## 4. CLI shape

```bash
insecure-tree scan [OPTIONS]
insecure-tree metadata [OPTIONS]
insecure-tree graph [OPTIONS]
insecure-tree report [OPTIONS]
insecure-tree cache [SUBCOMMAND]
```

### 4.1 Primary command

```bash
insecure-tree scan \
  --source auto \
  --project . \
  --output-dir ./insecure-tree-report \
  --format text --format html
```

`scan` runs the full pipeline:

1. Discover dependency graph.
2. Resolve package metadata.
3. Extract GitHub repo candidates.
4. Fetch workflows.
5. Run `zizmor`.
6. Write reports.

### 4.2 Dependency source options

```bash
--source auto|uv|uv-pip|pip-inspect|pipdeptree|requirements|json
--project PATH
--python PYTHON
--requirements FILE
--graph-json FILE
--include-dev
--exclude-dev
--extras EXTRA[,EXTRA...]
--groups GROUP[,GROUP...]
--depth N
--root PACKAGE[,PACKAGE...]
```

Recommended behavior:

* `auto`: detect in order:

  1. `uv.lock` + `pyproject.toml` → `uv` adapter.
  2. Active or specified Python environment with `uv pip tree` available → `uv-pip` adapter.
  3. Active or specified Python environment with `pip inspect` available → `pip-inspect` adapter.
  4. `pipdeptree` available → `pipdeptree` adapter.
  5. `requirements*.txt` → `requirements` adapter.
* `uv`: use `uv tree --output-format json` when available.
* `uv-pip`: use `uv pip tree --output-format json` when available.
* `pip-inspect`: use `python -m pip inspect` and derive graph edges from each distribution’s `requires_dist` metadata.
* `pipdeptree`: use `pipdeptree --json-tree` or equivalent.
* `requirements`: resolve package metadata for pinned or unpinned top-level requirements, but mark graph as incomplete unless lock data is also supplied.
* `json`: consume a previously generated `insecure-tree graph --format json` file.

## 5. Answer to “does pip have a native tree?”

No, not in the same sense as `uv tree`, `uv pip tree`, or `pipdeptree`.

Modern pip provides `pip inspect`, which emits a stable JSON report of installed distributions and their package metadata. That metadata includes `requires_dist`, so `insecure-tree` can reconstruct an environment-level dependency graph, but pip’s built-in command set does not provide a first-class hierarchical dependency tree command.

So v1 should treat pip support as:

* Metadata source: native `pip inspect`.
* Tree reconstruction: implemented by `insecure-tree`.
* Optional compatibility path: `pipdeptree` adapter when installed.

## 6. Data model

### 6.1 Package node

```json
{
  "name": "requests",
  "normalized_name": "requests",
  "version": "2.32.3",
  "source": "uv",
  "requested": true,
  "depth": 0,
  "dependency_groups": ["default"],
  "extras": [],
  "markers_applied": true,
  "metadata": {
    "index_url": "https://pypi.org/pypi/requests/2.32.3/json",
    "metadata_source": "pypi-json",
    "summary": "...",
    "home_page": "...",
    "project_urls": {},
    "requires_dist": []
  },
  "repo_candidates": [],
  "selected_repo": null,
  "scan": null
}
```

### 6.2 Graph edge

```json
{
  "from": "requests==2.32.3",
  "to": "urllib3==2.2.2",
  "requirement": "urllib3<3,>=1.21.1",
  "extra": null,
  "marker": null,
  "source": "uv"
}
```

### 6.3 Repository candidate

```json
{
  "url": "https://github.com/psf/requests",
  "owner": "psf",
  "repo": "requests",
  "source_field": "project_urls.Source",
  "confidence": "high",
  "reason": "Project-URL label matched source/repository and URL is GitHub HTTPS URL",
  "normalized_clone_url": "https://github.com/psf/requests.git",
  "default_branch": null,
  "archived": null
}
```

Confidence levels:

* `high`: explicit source/repository/changelog/docs field pointing to GitHub project root.
* `medium`: homepage points to GitHub project root.
* `low`: GitHub URL found in description or miscellaneous URL field.
* `rejected`: GitHub URL is issue, pull request, release asset, user profile, organization page, gist, or docs-only URL.

### 6.4 Scan result

```json
{
  "status": "scanned|no_repo|no_workflows|clone_failed|zizmor_failed|skipped|cached",
  "zizmor_version": "1.24.1",
  "repo_ref": "owner/repo@sha",
  "workflow_count": 4,
  "finding_count": 3,
  "findings_by_severity": {
    "error": 1,
    "warning": 2,
    "note": 0
  },
  "findings": [
    {
      "rule_id": "template-injection",
      "severity": "error",
      "title": "Template injection risk",
      "path": ".github/workflows/ci.yml",
      "line": 42,
      "column": 13,
      "message": "...",
      "url": "https://github.com/owner/repo/blob/sha/.github/workflows/ci.yml#L42"
    }
  ],
  "raw_output_path": "raw/zizmor/owner__repo.json"
}
```

## 7. Metadata resolution

### 7.1 Package metadata sources

Resolution order:

1. Local installed distribution metadata from `pip inspect` or importlib metadata.
2. PyPI JSON API for exact package version.
3. PyPI JSON API latest release fallback, only if exact version unavailable.
4. User-provided metadata override file.

### 7.2 Fields to inspect for GitHub URLs

Inspect at least:

* `project_url` / `project_urls`
* `home_page`
* `download_url`
* `docs_url`, with lower confidence
* `description`, with lower confidence
* `direct_url` for direct VCS installs

Preferred labels:

* `Source`
* `Source Code`
* `Repository`
* `Homepage`
* `Code`
* `GitHub`

Reject labels likely to be non-source:

* `Bug Tracker`
* `Issues`
* `CI`
* `Documentation`, unless no better candidate exists
* `Funding`
* `Changelog`, unless it maps to a repo root after normalization

### 7.3 GitHub URL normalization

Accept forms:

```text
https://github.com/OWNER/REPO
https://github.com/OWNER/REPO.git
git+https://github.com/OWNER/REPO.git
git@github.com:OWNER/REPO.git
ssh://git@github.com/OWNER/REPO.git
```

Normalize to:

```text
https://github.com/OWNER/REPO.git
OWNER/REPO
```

Strip:

* `.git`
* trailing slash
* `tree/<branch>`
* `blob/<branch>/...`
* `issues`, `pulls`, `actions`, `releases`, `wiki`, when they can safely collapse to repo root

Reject:

* GitHub organization/user profile only
* GitHub topic/search URLs
* Gist URLs
* Links to individual action repos that are not the package’s source repo, unless explicitly marked as source

## 8. Repository fetching

### 8.1 Fetch modes

```bash
--repo-fetch auto|api|git|archive
```

* `api`: use GitHub API to list and download `.github/workflows/*` only.
* `git`: shallow clone repository, default depth 1.
* `archive`: download default branch tarball/zipball.
* `auto`: prefer API for public GitHub repos; fall back to git.

Recommended v1 default: `api`, because `zizmor` only needs workflow files and this avoids cloning full repositories.

### 8.2 Authentication

```bash
--github-token TOKEN
--github-token-env GITHUB_TOKEN
```

Default behavior:

* Use `GITHUB_TOKEN` if present.
* Otherwise unauthenticated GitHub API for public repos.
* Do not print token values.

### 8.3 Pinning scanned content

For each repository, record:

* Owner/repo.
* Default branch.
* Commit SHA scanned.
* Workflow file paths and blob SHAs.
* Fetch timestamp.

Reports must distinguish “scanned current default branch at time of scan” from “scanned package release source.”

## 9. Running zizmor

### 9.1 Invocation

```bash
zizmor --format json PATH_TO_REPO_OR_WORKFLOWS
```

`insecure-tree` should discover the installed `zizmor` binary or run through a configured command.

```bash
--zizmor-bin zizmor
--zizmor-arg ARG
--offline-zizmor
```

### 9.2 Scan target strategy

If using API workflow fetch:

* Create a temporary directory:

```text
.tmp/repos/owner__repo/.github/workflows/*.yml
```

* Run `zizmor` against that temporary repo-like directory.

If using git clone:

* Run `zizmor` against the clone root.

### 9.3 Failure handling

A single failed repository must not fail the whole scan unless `--strict` is set.

Statuses:

* `clone_failed`
* `metadata_failed`
* `github_api_failed`
* `zizmor_failed`
* `no_workflows`
* `no_repo`
* `skipped_cached`

Exit codes:

* `0`: scan completed; no findings at or above fail threshold.
* `1`: scan completed; findings at or above fail threshold.
* `2`: CLI usage/config error.
* `3`: scan infrastructure error, such as missing `zizmor`, invalid JSON, cache corruption.
* `4`: partial scan with one or more repository fetch/scan failures and `--fail-on-partial` enabled.

### 9.4 Severity thresholds

```bash
--fail-on error|warning|note|never
--report-min-severity error|warning|note
```

Default:

```text
--fail-on never
--report-min-severity note
```

Rationale: the tool is initially exploratory and should not break CI unless the user opts in.

## 10. Output

### 10.1 Output directory

```text
insecure-tree-report/
  insecure-tree.txt
  insecure-tree.html
  insecure-tree.json
  raw/
    graph.json
    metadata/
    repos/
    zizmor/
```

Even though the user asked for text and HTML, v1 should also write a machine-readable JSON report by default because it enables debugging, future diffs, and CI integrations.

### 10.2 Text report

Text report sections:

1. Header

   * project path
   * source adapter
   * scan timestamp
   * insecure-tree version
   * zizmor version
2. Summary

   * total packages
   * packages with claimed GitHub repos
   * packages scanned
   * packages skipped
   * repos with findings
   * total findings by severity
3. Highest-risk findings
4. Package table
5. Repository ambiguity table
6. Skips and failures
7. Full findings

Example text layout:

```text
insecure-tree report
====================
Project: /src/example
Source: uv
Scanned: 2026-05-03T14:10:00-04:00

Summary
-------
Packages discovered:          143
Packages with GitHub repos:    96
Repositories scanned:          91
No workflows:                  23
Repos with findings:           12
Findings:                      31 warnings, 4 errors

Top findings
------------
[error] requests -> psf/requests .github/workflows/ci.yml:42 template-injection
[warn ] rich     -> Textualize/rich .github/workflows/release.yml:18 excessive-permissions

Packages
--------
requests==2.32.3     psf/requests       scanned       1 error
urllib3==2.2.2       urllib3/urllib3     no_workflows  -
...
```

### 10.3 HTML report

HTML report requirements:

* Single self-contained HTML file by default.
* No external JS/CDN by default.
* Collapsible package rows.
* Sortable tables using minimal inline JS.
* Summary cards.
* Severity filters.
* Clearly show provenance:

  * package name/version
  * dependency path(s)
  * metadata field used to infer repo
  * repo URL
  * commit SHA scanned
* Link to GitHub workflow lines when commit SHA is known.
* Include raw JSON download/embed section optionally.

```bash
--html-assets inline|directory|none
```

Default: `inline`.

## 11. Dependency graph support details

### 11.1 uv project adapter

Command:

```bash
uv tree --output-format json --project PATH
```

Optional flags:

```bash
--depth N
--package PACKAGE
--no-dev
--group GROUP
--extra EXTRA
```

Adapter responsibilities:

* Preserve dependency hierarchy from uv JSON.
* Mark workspace/project roots.
* Preserve groups/extras where uv exposes them.
* Normalize package names according to PEP 503.

### 11.2 uv pip adapter

Command:

```bash
uv pip tree --output-format json --python PYTHON
```

Adapter responsibilities:

* Treat active environment packages as installed graph.
* Preserve requested vs transitive if exposed; otherwise infer roots as packages not required by any other discovered package.

### 11.3 pip inspect adapter

Command:

```bash
python -m pip inspect
```

Adapter responsibilities:

* Parse stable JSON report.
* Build nodes from `installed`.
* Build edges from each distribution’s `metadata.requires_dist`.
* Evaluate environment markers against the report environment.
* Normalize names and resolve installed versions.
* Mark `requested` when provided.

Limitations:

* The reconstructed graph is environment-level, not lockfile-level.
* Dependency edges may be ambiguous when extras are involved.
* If multiple installed distributions satisfy a requirement strangely, report ambiguity rather than hiding it.

### 11.4 pipdeptree adapter

Command:

```bash
pipdeptree --json-tree
```

Use this only when installed or explicitly selected.

### 11.5 requirements adapter

Inputs:

```bash
-r requirements.txt
-r requirements-dev.txt
```

Behavior:

* Parse top-level requirements.
* If pinned, resolve exact PyPI metadata.
* If unpinned, resolve latest metadata unless `--no-latest-fallback` is set.
* Mark graph completeness as `partial`.
* Recommend using uv lock, uv tree, pip inspect, or pipdeptree for full transitive graph.

## 12. Caching

Cache location:

```text
${XDG_CACHE_HOME}/insecure-tree
~/Library/Caches/insecure-tree
%LOCALAPPDATA%\insecure-tree\Cache
```

Cache keys:

* Package metadata: `index_url + normalized_name + version`.
* GitHub repo metadata: `owner/repo + default_branch + token_scope(public/private flag only)`.
* Workflow content: `owner/repo + commit_sha`.
* zizmor result: `zizmor_version + owner/repo + commit_sha + config_hash`.

CLI:

```bash
insecure-tree cache dir
insecure-tree cache clean
insecure-tree cache clean --older-than 30d
```

Freshness options:

```bash
--metadata-ttl 7d
--repo-ttl 1d
--no-cache
--refresh
```

## 13. Security and privacy

* Never execute untrusted package code.
* Prefer static metadata and remote APIs.
* Do not run repository build scripts.
* Shallow clone with blob filtering where possible if cloning is needed.
* Redact tokens from logs, errors, reports, and command traces.
* Do not upload local dependency graphs anywhere.
* Include `--offline` mode that only uses existing graph JSON and cache.
* Include `--no-clone` mode that only reports candidate repos without scanning.
* Treat PyPI metadata as untrusted user-controlled input; escape everything in HTML.
* Bound concurrency and file sizes.
* Set network timeouts.

## 14. Configuration file

Default config path:

```text
pyproject.toml: [tool.insecure-tree]
insecure-tree.toml
```

Example:

```toml
[tool.insecure-tree]
source = "auto"
output_dir = "insecure-tree-report"
formats = ["text", "html", "json"]
fail_on = "never"
report_min_severity = "note"
repo_fetch = "api"
concurrency = 8
metadata_ttl = "7d"
repo_ttl = "1d"

[tool.insecure-tree.github]
token_env = "GITHUB_TOKEN"

[tool.insecure-tree.zizmor]
bin = "zizmor"
args = []

[tool.insecure-tree.repo_overrides]
"Pillow" = "https://github.com/python-pillow/Pillow"
"beautifulsoup4" = "https://code.launchpad.net/beautifulsoup"
```

## 15. Repo overrides and ignore policy

Support overrides for metadata inaccuracies:

```bash
--repo-override PACKAGE=OWNER/REPO
--ignore-package PACKAGE
--ignore-repo OWNER/REPO
--ignore-finding PACKAGE:RULE_ID
```

Ignore records should require optional reasons in config:

```toml
[[tool.insecure-tree.ignore]]
package = "example"
rule = "excessive-permissions"
reason = "Upstream workflow only runs on release branches; accepted for now."
expires = "2026-08-01"
```

Expired ignores should be reported as warnings.

## 16. Concurrency and performance

Options:

```bash
--concurrency N
--github-concurrency N
--zizmor-concurrency N
--timeout 30s
```

Defaults:

* metadata requests: 16
* GitHub requests: 8
* zizmor scans: number of CPU cores, capped at 8
* per-request timeout: 30 seconds
* per-repo scan timeout: 120 seconds

Use a work queue:

1. Resolve all package metadata.
2. Deduplicate repo candidates.
3. Fetch workflows once per repo.
4. Scan once per unique repo SHA.
5. Fan results back out to packages.

## 17. Package/repo deduplication

Multiple packages may claim the same repo. The report should group by repository and show all packages pointing at it.

Examples:

```text
repo: pydantic/pydantic
packages:
  - pydantic==2.8.2
  - pydantic-core==2.20.1
```

Scanning should happen once per unique `owner/repo@sha`.

## 18. UX examples

### 18.1 Scan a uv project

```bash
insecure-tree scan --source uv --project .
```

### 18.2 Scan current virtualenv using pip metadata

```bash
insecure-tree scan --source pip-inspect --python .venv/bin/python
```

### 18.3 Scan current environment, auto-detecting best source

```bash
insecure-tree scan
```

### 18.4 Generate only dependency graph JSON

```bash
insecure-tree graph --source uv --format json > graph.json
```

### 18.5 Re-render report from prior JSON

```bash
insecure-tree report --input insecure-tree-report/insecure-tree.json --format html
```

### 18.6 CI usage

```bash
insecure-tree scan \
  --source auto \
  --format text \
  --format html \
  --fail-on error \
  --output-dir artifacts/insecure-tree
```

## 19. Implementation architecture

Recommended language: Python.

Recommended package layout:

```text
insecure_tree/
  __init__.py
  cli.py
  config.py
  models.py
  adapters/
    base.py
    uv.py
    uv_pip.py
    pip_inspect.py
    pipdeptree.py
    requirements.py
  metadata/
    pypi.py
    local.py
    github_urls.py
  github/
    client.py
    fetch.py
  scanners/
    zizmor.py
  report/
    text.py
    html.py
    json.py
  cache.py
  subprocess.py
  marker_eval.py
  normalize.py
```

Recommended libraries:

* `typer` or `click` for CLI.
* `pydantic` or dataclasses plus `cattrs` for internal models.
* `packaging` for requirement parsing, markers, and name normalization.
* `httpx` for async HTTP.
* `jinja2` for HTML templates.
* `rich` for optional terminal progress.

## 20. Test plan

### 20.1 Unit tests

* Package name normalization.
* Requirement parsing and marker evaluation.
* GitHub URL extraction and rejection.
* Metadata source priority.
* Repo candidate confidence scoring.
* Zizmor JSON parsing.
* HTML escaping.
* Cache key generation.

### 20.2 Adapter fixtures

* uv project tree JSON.
* uv pip tree JSON.
* pip inspect JSON.
* pipdeptree JSON.
* requirements file with pinned, unpinned, extras, markers, direct URLs.

### 20.3 Integration tests

* Small real project with 5–10 dependencies.
* Project with dependencies sharing one repo.
* Package with no GitHub metadata.
* Package with GitHub issue URL but no repo URL.
* Repo with no workflows.
* Repo with known zizmor finding fixture.
* GitHub API rate-limit simulation.
* Missing `zizmor` binary.

### 20.4 Snapshot tests

* Text report snapshots.
* HTML report snapshots after normalizing timestamps.
* JSON schema snapshots.

## 21. Open questions

1. Should v1 scan only default branches, or try to map package versions to Git tags?

   * Recommendation: default branch in v1; add `--scan-release-ref` later.
2. Should reports include packages with non-GitHub repos?

   * Recommendation: yes, under “not scanned,” with reason `non_github_repo`.
3. Should `insecure-tree` expose SARIF output?

   * Recommendation: not required for v1 text/HTML, but keep JSON model compatible enough to add SARIF later.
4. Should scans be reproducible by pinning GitHub SHAs?

   * Recommendation: always record SHAs; support `--repo-lock insecure-tree-repos.lock` in v2.
5. Should dependency paths be fully enumerated?

   * Recommendation: include up to N shortest paths per package, default 3, to avoid huge reports.

## 22. Suggested v1 milestone cut

Must-have:

* `scan` command.
* `uv` adapter.
* `pip-inspect` adapter.
* PyPI metadata fetch.
* GitHub URL extraction.
* GitHub API workflow fetch.
* `zizmor` JSON invocation.
* text, HTML, and JSON output.
* cache.
* basic config.

Nice-to-have:

* `uv-pip` adapter.
* `pipdeptree` adapter.
* ignore policy.
* repo overrides.
* CI fail thresholds.

Post-v1:

* SARIF output.
* release-tag scanning.
* SBOM import/export.
* GitHub issue generation.
* baseline/diff mode.
