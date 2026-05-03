# insecure-tree

**insecure-tree** audits the GitHub Actions security posture of the upstream repositories behind your Python dependency graph.

Given a Python project or environment, it:

1. Builds the full transitive dependency graph (using `uv`, `pip inspect`, `pipdeptree`, or a `requirements.txt`).
1. Fetches package metadata from PyPI to find claimed GitHub repository URLs.
1. Downloads `.github/workflows/*.yml` files for each repository via the GitHub API.
1. Runs [zizmor](https://github.com/woodruffw/zizmor) against each set of workflow files.
1. Writes a unified report — text, HTML, and JSON — showing all findings and which packages they came from.

## What it is not

insecure-tree is not a vulnerability scanner for package code. It does not inspect Python source, run pip audit, or check for known CVEs. Its focus is a single question: *do the GitHub Actions pipelines of my dependencies have security weaknesses that could enable a supply-chain attack?*

## Requirements

- Python 3.10 or later
- [zizmor](https://github.com/woodruffw/zizmor) installed and on `PATH` (or configured via `--zizmor-bin`)
- Network access to PyPI and GitHub (or a populated cache for offline use)

## Status

Alpha. The core pipeline — uv adapter, pip-inspect adapter, PyPI metadata, GitHub API workflow fetch, zizmor scanning, text/HTML/JSON reports, and SQLite-backed caching — is implemented and functional.
