# insecure-tree

Audit the GitHub Actions security posture of your entire Python dependency tree.

insecure-tree discovers your transitive dependencies, resolves their PyPI metadata, identifies claimed GitHub
repositories, downloads workflow files, and runs [zizmor](https://github.com/woodruffw/zizmor) against each one — then
produces a unified text, HTML, and JSON report showing every finding and which package it came from.

## Demo page

[Demo](https://matthewdeanmartin.github.io/insecure_tree/) of scan against insecure-tree's own dependencies (including
development dependencies)

## Installation

```bash
# Install zizmor first (required)
pip install zizmor

# Install insecure-tree
pipx install insecure_tree
```

Or with pip:

```bash
pip install insecure_tree
```

## Quick start

```bash
# Scan a uv project
insecure-tree scan --source uv --project .

# Scan the active virtualenv
insecure-tree scan --source pip-inspect

# Auto-detect the best source
insecure-tree scan
```

Reports land in `./insecure-tree-report/` as `insecure-tree.txt`, `insecure-tree.html`, and `insecure-tree.json`.

## GitHub Pages self-scan

The checked-in GitHub Pages report lives in `pages/`, not `docs/`, so it does not interfere with the MkDocs / Read the
Docs site.

Regenerate it with:

```bash
uv run make build-pages-report
```

The `Publish GitHub Pages` workflow rebuilds that self-scan report and deploys `pages/index.html`.

## CI usage

```bash
insecure-tree scan \
  --source auto \
  --format text \
  --format html \
  --fail-on error \
  --output-dir artifacts/insecure-tree
```

Exit codes: `0` clean, `1` findings above threshold, `2` config error, `3` infrastructure error, `4` partial scan
failure.

## All commands

| Command                             | Description                                                 |
|-------------------------------------|-------------------------------------------------------------|
| `insecure-tree scan`                | Run the full audit pipeline                                 |
| `insecure-tree graph`               | Emit the dependency graph as JSON or text                   |
| `insecure-tree metadata PACKAGE`    | Inspect PyPI metadata and GitHub candidates for one package |
| `insecure-tree report --input FILE` | Re-render a report from a saved JSON file                   |
| `insecure-tree cache dir`           | Print the cache directory path                              |
| `insecure-tree cache clean`         | Remove expired cache entries                                |

## Configuration

Configuration is read from `pyproject.toml` under `[tool.insecure-tree]` or from `insecure-tree.toml`:

```toml
[tool.insecure-tree]
source = "auto"
fail_on = "never"
report_min_severity = "note"

[tool.insecure-tree.github]
token_env = "GITHUB_TOKEN"

[tool.insecure-tree.repo_overrides]
"Pillow" = "https://github.com/python-pillow/Pillow"

[[tool.insecure-tree.ignore]]
package = "some-package"
rule = "excessive-permissions"
reason = "Accepted risk — only runs on release branches."
expires = "2026-12-01"
```

## Documentation

Full documentation is at [insecure-tree.readthedocs.io](https://insecure_tree.readthedocs.io/en/latest/).

- [Installation](https://insecure_tree.readthedocs.io/en/latest/installation/)
- [Quick Start](https://insecure_tree.readthedocs.io/en/latest/usage/quickstart/)
- [CLI Reference](https://insecure_tree.readthedocs.io/en/latest/usage/cli/)
- [Configuration](https://insecure_tree.readthedocs.io/en/latest/usage/configuration/)
- [How It Works](https://insecure_tree.readthedocs.io/en/latest/concepts/how_it_works/)
- [CI Integration](https://insecure_tree.readthedocs.io/en/latest/usage/ci/)

## Contributing

See [CONTRIBUTING.md](docs/extending/CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
