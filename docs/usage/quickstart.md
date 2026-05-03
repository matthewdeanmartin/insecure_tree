# Quick Start

## 1. Install zizmor and insecure-tree

```bash
pip install zizmor
pipx install insecure_tree
```

## 2. Run your first scan

From the root of a `uv`-managed project:

```bash
insecure-tree scan --source uv --project .
```

From an active virtualenv:

```bash
insecure-tree scan --source pip-inspect
```

Let insecure-tree detect the best source automatically:

```bash
insecure-tree scan
```

## 3. Read the report

By default, reports are written to `./insecure-tree-report/`:

```
insecure-tree-report/
  insecure-tree.txt    # human-readable summary
  insecure-tree.html   # self-contained HTML with sortable tables
  insecure-tree.json   # full machine-readable data
  raw/                 # raw graph and zizmor output
```

Open `insecure-tree.html` in a browser for the interactive view, or read `insecure-tree.txt` in a terminal:

```bash
cat insecure-tree-report/insecure-tree.txt
```

## 4. Set a GitHub token

Without a token, the GitHub API allows 60 requests per hour — enough for a small project. For larger dependency trees:

```bash
export GITHUB_TOKEN=ghp_...
insecure-tree scan
```

## 5. Common options at a glance

```bash
# Scan only direct dependencies (depth 1)
insecure-tree scan --depth 1

# Fail CI if any error-level findings are found
insecure-tree scan --fail-on error

# Skip the network; use only cached data
insecure-tree scan --offline

# Report which repos would be scanned without scanning them
insecure-tree scan --no-clone

# Re-render HTML from a previous JSON report
insecure-tree report --input insecure-tree-report/insecure-tree.json --format html
```

See [CLI Reference](cli.md) for the full option list.
