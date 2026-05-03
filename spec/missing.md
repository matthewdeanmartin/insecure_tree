# Work Remaining (spec vs. implementation)

This file tracks features described in `spec/spec.md` that are not yet implemented in the codebase as of v0.1.0.

## Must-have items from spec §22 not yet implemented

### `uv-pip` adapter (spec §11.2)
**Status:** stub exists (`adapters/uv_pip.py`) but needs `detect()` and `fetch()` implemented.
- Run `uv pip tree --output-format json --python PYTHON`.
- Infer roots as packages not required by any other discovered package when uv does not expose requested/transitive explicitly.

### `pip-inspect` adapter (spec §11.3)
**Status:** stub exists (`adapters/pip_inspect.py`) but needs `detect()` and `fetch()` implemented.
- Run `python -m pip inspect`.
- Build graph nodes from `installed[]`.
- Reconstruct edges from `metadata.requires_dist`.
- Evaluate environment markers against the report environment.
- Mark `complete: false` when edge reconstruction is ambiguous.

### Ignore policy enforcement (spec §15)
**Status:** `IgnoreRule` model and config loading exist, but the pipeline does not apply ignore rules to filter findings.
- Filter `ScanFinding` objects before writing reports when a matching `[[tool.insecure-tree.ignore]]` rule exists.
- Warn in reports about expired ignore rules (where `expires` is in the past).
- Support `--ignore-package`, `--ignore-repo`, and `--ignore-finding PACKAGE:RULE_ID` CLI flags.

### `--ignore-repo OWNER/REPO` CLI flag (spec §15)
**Status:** not wired up. Model supports it; pipeline does not check it.

### `--ignore-finding PACKAGE:RULE_ID` CLI flag (spec §15)
**Status:** not wired up.

### CI fail-on-partial enforcement (spec §9.3)
**Status:** `--fail-on-partial` flag exists and exit code 4 is defined, but the partial-failure detection in `pipeline.py` may miss some `github_api_failed` statuses. Needs end-to-end test coverage.

---

## Nice-to-have items from spec §22 not yet implemented

### `pipdeptree` adapter (spec §11.4)
**Status:** stub exists (`adapters/pipdeptree.py`) but `detect()` and `fetch()` need implementation.
- Run `pipdeptree --json-tree`.
- Use only when `pipdeptree` is importable or on PATH.

### `requirements` adapter (spec §11.5)
**Status:** stub exists (`adapters/requirements.py`) but needs full implementation.
- Parse top-level requirements (pinned and unpinned).
- Resolve exact PyPI metadata for pinned packages.
- Resolve latest metadata for unpinned unless `--no-latest-fallback` is set.
- Mark graph `complete: false`.

### Repo deduplication in reports (spec §17)
**Status:** deduplication happens in the pipeline (one scan per `owner/repo@sha`) but the text and HTML reports do not yet have a dedicated "Repositories" section grouping all packages that share a repo.

### `--offline` mode improvements (spec §13)
**Status:** `--offline` flag skips the scan phase, but the graph and metadata phases still require network unless the cache is pre-populated. The `requirements` adapter will need a no-network mode for offline use.

---

## Post-v1 items (out of scope for now)

From spec §22 post-v1 list:

- SARIF output format.
- Release-tag / version-pinned scanning (`--scan-release-ref`).
- SBOM import/export.
- GitHub issue generation.
- Baseline/diff mode.
- `--repo-lock insecure-tree-repos.lock` for reproducible scans.

---

## Open questions from spec §21 not yet resolved

1. **Scan default branch vs. release ref** — v1 scans default branch; `--scan-release-ref` deferred.
2. **Non-GitHub repos in reports** — `non_github_repo` status exists in the model but is not always populated by the adapters.
3. **SARIF output** — JSON model is SARIF-compatible but a dedicated `--format sarif` output writer is not implemented.
4. **SHA pinning / repo lock file** — SHAs are recorded per-scan but there is no `insecure-tree-repos.lock` file or `--repo-lock` flag.
5. **Dependency path enumeration** — `GraphEdge` records exist but the report does not yet show N shortest dependency paths per package.

---

## Test coverage gaps (spec §20)

- No adapter fixture tests for uv pip tree JSON, pip inspect JSON, or pipdeptree JSON.
- No integration test for rate-limit simulation.
- No snapshot tests for text/HTML/JSON reports.
- No test for `--graph-json` / `json` source adapter.
- No test for expired ignore rules.
