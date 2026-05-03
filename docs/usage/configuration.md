# Configuration

insecure-tree reads configuration from `pyproject.toml` (under `[tool.insecure-tree]`) or from a standalone `insecure-tree.toml` file in the project root. CLI flags always take precedence over file configuration.

## Example `pyproject.toml`

```toml
[tool.insecure-tree]
source = "auto"
output_dir = "insecure-tree-report"
formats = ["text", "html", "json"]
fail_on = "never"
report_min_severity = "note"
repo_fetch = "api"
concurrency = 16
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

[[tool.insecure-tree.ignore]]
package = "some-package"
rule = "excessive-permissions"
reason = "Upstream workflow only runs on release branches; accepted for now."
expires = "2026-08-01"
```

## All settings

### Top-level keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `source` | string | `"auto"` | Dependency source adapter |
| `output_dir` | string | `"insecure-tree-report"` | Report output directory |
| `formats` | list[string] | `["text","html","json"]` | Report formats to write |
| `fail_on` | string | `"never"` | Severity threshold for exit code 1 |
| `report_min_severity` | string | `"note"` | Minimum severity shown in reports |
| `repo_fetch` | string | `"api"` | Workflow fetch mode (`api`, `git`, `archive`, `auto`) |
| `concurrency` | int | `16` | Max concurrent metadata requests |
| `github_concurrency` | int | `8` | Max concurrent GitHub API requests |
| `metadata_ttl` | string or int | `"7d"` | Cache TTL for PyPI metadata |
| `repo_ttl` | string or int | `"1d"` | Cache TTL for workflow content |
| `no_cache` | bool | `false` | Disable caching |
| `offline` | bool | `false` | Use only cached data |
| `no_clone` | bool | `false` | Identify repos but skip scanning |
| `strict` | bool | `false` | Abort on first repo failure |
| `fail_on_partial` | bool | `false` | Exit 4 on partial scan failures |
| `depth` | int or null | null | Max dependency depth |
| `include_dev` | bool | `true` | Include dev dependencies |
| `timeout` | float | `30.0` | Per-request network timeout (seconds) |

TTL values accept `7d`, `12h`, `30m`, `60s`, or a plain integer (seconds).

### `[tool.insecure-tree.github]`

| Key | Default | Description |
|-----|---------|-------------|
| `token_env` | `"GITHUB_TOKEN"` | Environment variable name to read token from |
| `token` | — | Literal token value (not recommended; prefer env var) |

### `[tool.insecure-tree.zizmor]`

| Key | Default | Description |
|-----|---------|-------------|
| `bin` | `"zizmor"` | Path or name of the zizmor binary |
| `args` | `[]` | Extra arguments to pass on every invocation |

### `[tool.insecure-tree.repo_overrides]`

A table mapping package names (or normalized names) to canonical GitHub URLs. Use this when PyPI metadata points to the wrong repo or to a non-GitHub forge.

```toml
[tool.insecure-tree.repo_overrides]
"Pillow" = "https://github.com/python-pillow/Pillow"
```

### `[[tool.insecure-tree.ignore]]`

A list of ignore rules. Each rule can suppress findings by package, repo, and/or rule ID.

| Key | Type | Description |
|-----|------|-------------|
| `package` | string | Package name to ignore |
| `repo` | string | `owner/repo` to ignore |
| `rule` | string | zizmor rule ID to ignore |
| `reason` | string | Human-readable justification |
| `expires` | date string | ISO date after which the ignore is reported as expired |

At least one of `package`, `repo`, or `rule` is required.
