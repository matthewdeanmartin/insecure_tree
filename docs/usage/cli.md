# CLI Reference

## Global options

```
insecure-tree [--version] [-v / --verbose] <command>
```

| Flag | Description |
|------|-------------|
| `--version` | Print version and exit |
| `-v`, `--verbose` | Enable debug logging |

______________________________________________________________________

## `scan` — run the full audit pipeline

```bash
insecure-tree scan [OPTIONS]
```

Runs: dependency discovery → PyPI metadata → GitHub URL extraction → workflow fetch → zizmor → report.

### Source options

| Flag | Default | Description |
|------|---------|-------------|
| `--source` | `auto` | Dependency source: `auto`, `uv`, `uv-pip`, `pip-inspect`, `pipdeptree`, `requirements`, `json` |
| `--project PATH` | `.` | Project root directory |
| `--python PYTHON` | — | Python interpreter path (used by pip-inspect and uv-pip adapters) |
| `--requirements FILE` | — | requirements.txt file; can repeat for multiple files |
| `--depth N` | — | Maximum dependency depth |
| `--include-dev` | on | Include dev dependencies |
| `--exclude-dev` | — | Exclude dev dependencies |

`--source auto` detects in order: `uv.lock` → `uv pip tree` → `pip inspect` → `pipdeptree` → `requirements*.txt`.

### Output options

| Flag | Default | Description |
|------|---------|-------------|
| `--output-dir DIR` | `insecure-tree-report` | Directory for report files |
| `--format FORMAT` | text + html + json | Output format(s); repeatable: `text`, `html`, `json` |

### GitHub options

| Flag | Default | Description |
|------|---------|-------------|
| `--github-token TOKEN` | — | GitHub personal access token |
| `--github-token-env VAR` | `GITHUB_TOKEN` | Environment variable to read token from |
| `--repo-fetch MODE` | `api` | Workflow fetch strategy: `api`, `git`, `archive`, `auto` |

### zizmor options

| Flag | Default | Description |
|------|---------|-------------|
| `--zizmor-bin BIN` | `zizmor` | Path or name of the zizmor binary |
| `--zizmor-arg ARG` | — | Extra argument to pass to zizmor; repeatable |

### Behaviour options

| Flag | Default | Description |
|------|---------|-------------|
| `--fail-on LEVEL` | `never` | Exit 1 when findings at or above this severity: `error`, `warning`, `note`, `never` |
| `--report-min-severity LEVEL` | `note` | Minimum severity to include in report |
| `--no-cache` | — | Disable the cache for this run |
| `--refresh` | — | Ignore cached values and re-fetch everything |
| `--offline` | — | Use only cached data; make no network requests |
| `--no-clone` | — | Identify candidate repos but do not fetch or scan them |
| `--strict` | — | Abort the whole scan if any single repo fails |
| `--fail-on-partial` | — | Exit 4 when one or more repos fail to fetch or scan |
| `--concurrency N` | 16 | Max concurrent metadata requests |
| `--repo-override PKG=OWNER/REPO` | — | Override the repo URL for a package; repeatable |
| `--ignore-package PACKAGE` | — | Skip a package entirely; repeatable |

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Scan completed; no findings at or above `--fail-on` threshold |
| `1` | Scan completed; findings at or above threshold |
| `2` | CLI usage or config error |
| `3` | Infrastructure error (missing zizmor, invalid JSON, cache corruption) |
| `4` | Partial scan failure with `--fail-on-partial` enabled |

______________________________________________________________________

## `graph` — emit dependency graph only

```bash
insecure-tree graph [--source SOURCE] [--project PATH] [--format json|text]
```

Runs only the dependency discovery step and prints the graph.

```bash
# Emit JSON for later use
insecure-tree graph --source uv --format json > my-graph.json

# Quick text listing
insecure-tree graph --format text
```

______________________________________________________________________

## `metadata` — inspect PyPI metadata for a package

```bash
insecure-tree metadata PACKAGE [--version VERSION]
```

Fetches and pretty-prints PyPI metadata for a single package, then lists the GitHub repository candidates found and their confidence scores.

```bash
insecure-tree metadata requests
insecure-tree metadata requests --version 2.32.3
```

______________________________________________________________________

## `report` — re-render a report from saved JSON

```bash
insecure-tree report --input JSON_FILE [--output-dir DIR] [--format FORMAT]
```

Reads a previously produced `insecure-tree.json` and writes new report files without re-running any scans.

```bash
insecure-tree report \
  --input insecure-tree-report/insecure-tree.json \
  --format html
```

______________________________________________________________________

## `cache` — manage the local cache

```bash
insecure-tree cache dir
insecure-tree cache clean [--older-than DURATION]
```

| Subcommand | Description |
|-----------|-------------|
| `dir` | Print the cache directory path |
| `clean` | Remove expired entries (or all entries older than `DURATION`) |

`DURATION` format: `30d`, `12h`, `90m`, `3600s`, or a plain integer (seconds).

Cache location:

| Platform | Path |
|----------|------|
| Windows | `%LOCALAPPDATA%\insecure-tree\Cache\cache.db` |
| macOS | `~/Library/Caches/insecure-tree/cache.db` |
| Linux | `$XDG_CACHE_HOME/insecure-tree/cache.db` (falls back to `~/.cache/insecure-tree/cache.db`) |
