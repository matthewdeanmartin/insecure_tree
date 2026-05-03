# insecure-tree

**insecure-tree** audits the GitHub Actions security posture of every Python package in your dependency tree.

It discovers your dependencies, resolves their PyPI metadata, finds claimed GitHub repositories, downloads their workflow files, and runs [zizmor](https://github.com/woodruffw/zizmor) against each one — then writes a unified text, HTML, and JSON report.

## Why this tool exists

A supply-chain attack doesn't have to compromise your code directly. A dependency's CI pipeline can be hijacked to poison releases, exfiltrate secrets, or introduce malware into artifacts. `insecure-tree` brings `zizmor`'s workflow-security analysis across your entire dependency graph so you can see the aggregate risk at a glance.

## Quick example

```bash
# Scan a uv project
insecure-tree scan --source uv --project .

# Scan the active virtualenv
insecure-tree scan --source pip-inspect

# Auto-detect the best source
insecure-tree scan
```

Reports land in `./insecure-tree-report/` as `insecure-tree.txt`, `insecure-tree.html`, and `insecure-tree.json`.

## Navigation

- [Installation](installation.md) — how to install insecure-tree and its dependency, zizmor
- [Quick Start](usage/quickstart.md) — your first scan in under five minutes
- [CLI Reference](usage/cli.md) — every command, flag, and exit code
- [Configuration](usage/configuration.md) — `pyproject.toml` and `insecure-tree.toml` options
- [How It Works](concepts/how_it_works.md) — pipeline internals, data model, caching
- [Dependency Sources](concepts/sources.md) — uv, pip-inspect, pipdeptree, requirements adapters
- [GitHub URL Extraction](concepts/github_urls.md) — confidence scoring and rejection rules
- [Reports](concepts/reports.md) — text, HTML, and JSON output formats
- [CI Integration](usage/ci.md) — fail thresholds, partial failures, exit codes
- [Contributing](extending/CONTRIBUTING.md)
- [Change Log](CHANGELOG.md)
