# Contributing

## Development setup

```bash
git clone https://github.com/matthewdeanmartin/insecure_tree.git
cd insecure_tree
uv sync
```

This installs all runtime and development dependencies into a local virtualenv managed by uv.

## Running the test suite

```bash
make test
# or directly:
uv run pytest
```

Tests are in `tests/`. Unit tests cover name normalization, marker evaluation, GitHub URL extraction, cache logic, and the data models. Integration tests are marked with `@pytest.mark.integration` and require network access.

```bash
# Run only unit tests (no network)
uv run pytest -m "not integration"

# Run integration tests
uv run pytest -m integration
```

## Running all quality checks

```bash
make check
```

This runs ruff, mypy, bandit, and the test suite.

## Before submitting a PR

```bash
make prerelease
```

This runs the full quality gate: linting, type checking, security scanning, tests, and documentation build checks. Address any failures before opening a pull request.

## Architecture overview

```
insecure_tree/
  cli.py           # argparse entry point; one function per subcommand
  pipeline.py      # async orchestration of the full scan pipeline
  config.py        # Config model + TOML loader
  models.py        # Pydantic domain models (PackageNode, ScanResult, etc.)
  cache.py         # SQLite-backed TTL cache
  normalize.py     # PEP 503 package name normalization
  marker_eval.py   # PEP 508 environment marker evaluation
  adapters/        # dependency graph adapters (uv, pip-inspect, etc.)
  metadata/        # PyPI metadata fetching and GitHub URL extraction
  github/          # GitHub REST API client and workflow file fetcher
  scanners/        # zizmor subprocess wrapper + SARIF parser
  report/          # text, HTML, and JSON report writers
```

## Adding a new dependency adapter

1. Create `insecure_tree/adapters/my_source.py` implementing `BaseAdapter`.
2. Override `detect(options)` to return `True` when your source is available.
3. Override `fetch(options)` to return a `DependencyGraph`.
4. Register the adapter in `pipeline._auto_detect_adapter` and `_choose_adapter`.
5. Add a `SourceAdapter.my_source` enum value in `models.py`.
6. Add a CLI choice in `cli._add_common_source_args`.
7. Add adapter fixtures and tests in `tests/`.

## Code style

- Line length: 120 (enforced by black and ruff).
- Type annotations required on all public functions.
- No comments unless the WHY is non-obvious.
- No docstrings on trivial methods.
