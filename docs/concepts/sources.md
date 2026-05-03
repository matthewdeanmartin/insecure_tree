# Dependency Sources

insecure-tree supports multiple adapters for building the dependency graph. Use `--source auto` (the default) to let it pick the best available adapter, or specify one explicitly.

## Auto-detection order

With `--source auto`, insecure-tree probes in this order and uses the first adapter that succeeds:

1. `uv` — if `uv.lock` and `pyproject.toml` exist in the project root.
2. `uv-pip` — if `uv pip tree` is available for the active or specified Python.
3. `pip-inspect` — if `pip inspect` is available.
4. `pipdeptree` — if `pipdeptree` is installed.
5. `requirements` — if any `requirements*.txt` file exists.

## `uv` adapter

**Command:** `uv tree --output-format json --project PATH`

Best choice for `uv`-managed projects. Produces a full transitive dependency graph with workspace awareness, optional group/extra filtering, and accurate depth information.

```bash
insecure-tree scan --source uv --project .
insecure-tree scan --source uv --depth 2
```

The adapter preserves dependency groups and extras as reported by uv.

## `uv-pip` adapter

**Command:** `uv pip tree --output-format json --python PYTHON`

Scans the packages installed in a virtualenv managed by `uv pip`. Pass `--python` to point at a specific environment.

```bash
insecure-tree scan --source uv-pip --python .venv/bin/python
```

## `pip-inspect` adapter

**Command:** `python -m pip inspect`

Reads the installed distributions from any Python environment using pip's stable JSON introspection format. Reconstructs the dependency graph from each distribution's `Requires-Dist` metadata.

```bash
insecure-tree scan --source pip-inspect
insecure-tree scan --source pip-inspect --python /path/to/.venv/bin/python
```

**Limitations:** the reconstructed graph is environment-level, not lockfile-level. With complex extras or unusual installs the edge set may be incomplete. insecure-tree marks such graphs as having `complete: false`.

## `pipdeptree` adapter

**Command:** `pipdeptree --json-tree`

Used when `pipdeptree` is installed and no better source is available (or when explicitly selected). Provides a tree structure similar to `uv tree`.

```bash
insecure-tree scan --source pipdeptree
```

Install pipdeptree separately: `pip install pipdeptree`.

## `requirements` adapter

Reads one or more `requirements.txt` files and resolves metadata for the listed packages.

```bash
insecure-tree scan --source requirements --requirements requirements.txt
insecure-tree scan --source requirements \
  --requirements requirements.txt \
  --requirements requirements-dev.txt
```

**Limitations:** only top-level requirements are discovered. The graph is marked `complete: false`. Transitive dependencies are not resolved unless lock data is also supplied. Use `uv` or `pip-inspect` for full transitive analysis.

## `json` adapter

Reads a previously generated `insecure-tree graph --format json` file:

```bash
insecure-tree graph --source uv --format json > my-graph.json
insecure-tree scan --source json --graph-json my-graph.json
```

Useful for air-gapped environments or when you want to separate the graph-building step from the scan step.

## Common source options

These options work with every adapter:

| Option | Description |
|--------|-------------|
| `--project PATH` | Project root directory (default: current directory) |
| `--python PYTHON` | Python interpreter or virtualenv path |
| `--depth N` | Maximum dependency depth to include |
| `--include-dev` / `--exclude-dev` | Include or exclude dev dependencies |
| `--requirements FILE` | Additional requirements file(s) |
