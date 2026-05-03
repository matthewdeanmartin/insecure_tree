# How insecure-tree Works

## Pipeline overview

A `scan` run executes six sequential stages:

```
1. Discover dependency graph
        ↓
2. Resolve PyPI metadata (concurrent)
        ↓
3. Extract GitHub repo candidates
        ↓
4. Fetch workflow files from GitHub API (concurrent, deduplicated per repo)
        ↓
5. Run zizmor against workflow files (concurrent)
        ↓
6. Write text / HTML / JSON reports
```

## Stage 1 — Dependency discovery

An *adapter* builds the dependency graph as a set of `PackageNode` objects and `GraphEdge` objects. Each node carries the package name, version, depth in the tree, and which dependency groups it belongs to. See [Dependency Sources](sources.md) for details on each adapter.

## Stage 2 — PyPI metadata resolution

For each package node, insecure-tree fetches metadata from:

1. Local installed distribution metadata (via `importlib.metadata`).
1. PyPI JSON API for the exact version (`https://pypi.org/pypi/{name}/{version}/json`).
1. PyPI JSON API latest release, as a fallback only.

Results are cached in a local SQLite database with a configurable TTL (default: 7 days).

## Stage 3 — GitHub URL extraction

From each package's metadata fields (`project_urls`, `home_page`, `download_url`, `docs_url`, `description`), insecure-tree extracts all GitHub URLs and scores them by confidence:

| Confidence | Criteria |
|-----------|----------|
| `high` | `project_urls` label is `Source`, `Source Code`, `Repository`, `Code`, `GitHub`, or `Homepage` |
| `medium` | `home_page` field, or a changelog/history label in `project_urls` |
| `low` | `download_url`, `docs_url`, or a GitHub URL found in the description text |
| `rejected` | Issues/pulls/actions/releases page, gist, organization profile, or explicit reject labels like `Bug Tracker` |

The highest-confidence candidate becomes the `selected_repo` for a package. See [GitHub URL Extraction](github_urls.md) for full details.

## Stage 4 — Workflow fetch

insecure-tree contacts the GitHub REST API to:

1. Get repository metadata (default branch, archived status).
1. Get the HEAD commit SHA for the default branch.
1. List `.github/workflows/*.yml` and `*.yaml` files.
1. Download each file's content.

Files are written to a temporary directory structured as `owner__repo/.github/workflows/*.yml`, which zizmor can scan as if it were a real repository checkout.

**Deduplication:** if multiple packages claim the same `owner/repo`, workflows are fetched only once and the scan result is fanned back out to all matching packages.

## Stage 5 — zizmor scanning

insecure-tree calls `zizmor --format sarif <workflow_dir>` as a subprocess and parses the SARIF JSON output. The result includes:

- `rule_id` — the zizmor rule that fired (e.g. `template-injection`, `excessive-permissions`).
- `severity` — `error`, `warning`, or `note`.
- `path` / `line` / `column` — location in the workflow file.
- `url` — direct link to the line on GitHub (using the pinned commit SHA).

Scan results are cached keyed by `zizmor_version + owner/repo + commit_sha`. A single failing repository does not abort the scan unless `--strict` is set.

## Stage 6 — Report generation

Three report formats are written to the output directory:

- **`insecure-tree.txt`** — plain-text summary suitable for terminal and CI logs.
- **`insecure-tree.html`** — self-contained HTML with sortable tables, collapsible rows, and severity filters. No external CDN dependencies.
- **`insecure-tree.json`** — full machine-readable data including the complete dependency graph, all package nodes, and all findings.

See [Reports](reports.md) for format details.

## Caching

insecure-tree uses a thread-safe SQLite cache stored in the platform cache directory:

| Platform | Path |
|----------|------|
| Windows | `%LOCALAPPDATA%\insecure-tree\Cache\cache.db` |
| macOS | `~/Library/Caches/insecure-tree/cache.db` |
| Linux | `$XDG_CACHE_HOME/insecure-tree/cache.db` |

Cache domains and default TTLs:

| Domain | Key | Default TTL |
|--------|-----|-------------|
| `pypi` | `index_url + name + version` | 7 days |
| `github_repo` | `owner/repo + token scope` | 1 day |
| `workflows` | `owner/repo + commit_sha` | 7 days |
| `zizmor` | `zizmor_version + owner/repo + commit_sha` | 7 days |

Use `insecure-tree cache clean` to remove expired entries, `--no-cache` to bypass caching for a run, or `--refresh` to re-fetch everything while still writing new results to the cache.

## Data model

### `PackageNode`

The core record for each discovered package. After pipeline completion it carries:

- `name`, `normalized_name`, `version`, `source`, `depth`
- `metadata` — PyPI fields (project_urls, home_page, requires_dist, etc.)
- `repo_candidates` — all GitHub URL candidates, scored by confidence
- `selected_repo` — the winning `RepoCandidate`
- `scan` — the `ScanResult` from zizmor (or a status explaining why no scan was performed)

### `ScanResult` statuses

| Status | Meaning |
|--------|---------|
| `scanned` | zizmor ran successfully |
| `no_repo` | No GitHub repo identified in metadata |
| `no_workflows` | Repo has no `.github/workflows/*.yml` files |
| `clone_failed` | Repository could not be fetched |
| `github_api_failed` | GitHub API returned an error |
| `zizmor_failed` | zizmor invocation failed or produced unparseable output |
| `metadata_failed` | PyPI metadata fetch failed |
| `skipped` | Skipped (e.g. `--no-clone` set) |
| `skipped_cached` | Result served from cache |
| `non_github_repo` | Package claims a non-GitHub VCS URL |
