# CI Integration

insecure-tree is designed to run in CI without breaking existing pipelines by default. Use opt-in flags to add enforcement.

## Basic CI job

```yaml
- name: Audit dependency GitHub Actions
  run: |
    insecure-tree scan \
      --source auto \
      --format text \
      --format html \
      --output-dir artifacts/insecure-tree
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

This will always exit 0 (informational scan, never fails the build).

## Fail on error-level findings

```bash
insecure-tree scan --fail-on error
```

Exit codes:

| Code | Meaning |
|------|---------|
| `0` | Clean or only below-threshold findings |
| `1` | Findings at or above `--fail-on` severity |
| `2` | CLI/config error |
| `3` | Infrastructure error (zizmor missing, etc.) |
| `4` | Partial scan failure + `--fail-on-partial` |

## Save reports as CI artifacts

```yaml
- name: Scan dependencies
  run: insecure-tree scan --fail-on error --output-dir insecure-tree-report
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

- name: Upload report
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: insecure-tree-report
    path: insecure-tree-report/
```

Using `if: always()` ensures reports are uploaded even when the scan fails.

## Caching between CI runs

insecure-tree caches PyPI metadata (7 days TTL) and workflow content (1 day TTL). In CI you can persist the cache between runs:

```yaml
- name: Cache insecure-tree data
  uses: actions/cache@v4
  with:
    path: ~/.cache/insecure-tree   # Linux; adjust for macOS/Windows
    key: insecure-tree-${{ hashFiles('uv.lock') }}
    restore-keys: insecure-tree-
```

## Offline mode for air-gapped environments

If you pre-populate the cache in a prior step, you can run offline:

```bash
insecure-tree scan --offline
```

## Soft introduction workflow

Start with informational mode and tighten thresholds over time:

1. Run `--fail-on never` — collect data, do not break builds.
2. Review `insecure-tree.html`, add `ignore` rules for accepted risks.
3. Switch to `--fail-on warning`, fix or suppress remaining warnings.
4. Switch to `--fail-on error` for long-term CI enforcement.
