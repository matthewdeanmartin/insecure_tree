# GitHub URL Extraction

insecure-tree inspects several PyPI metadata fields to find which GitHub repository a package claims as its source. Because PyPI metadata is user-controlled and often inaccurate, each candidate is scored by confidence.

## Fields inspected

In descending priority:

1. **`project_urls`** — the most reliable field. Each entry has a label (e.g. `Source`, `Homepage`) and a URL.
2. **`home_page`** — the legacy homepage field.
3. **`download_url`** — low confidence; may point to a release archive rather than the repo root.
4. **`docs_url`** — very low confidence.
5. **`description`** — the package long-description text is scanned with a regex. Low confidence.

## Confidence levels

| Level | Criteria |
|-------|----------|
| `high` | `project_urls` label is `Source`, `Source Code`, `Repository`, `Code`, `GitHub`, `Homepage`, or `Home` |
| `medium` | `home_page` field, or a `project_urls` entry with a changelog/history label |
| `low` | `download_url`, `docs_url`, or a GitHub URL found in the description |
| `rejected` | Explicit reject labels, or a URL that points to a sub-page rather than a repo root |

## Reject labels

The following `project_urls` labels are rejected outright:

- `Bug Tracker`, `Issues`, `Issue Tracker`
- `CI`
- `Funding`

The `Documentation` / `Docs` labels produce a `low`-confidence candidate (rather than rejection) because some projects host their docs on GitHub Pages within the same repo.

## URL normalization and path rejection

insecure-tree accepts and normalizes all of these forms to `https://github.com/OWNER/REPO.git`:

```
https://github.com/OWNER/REPO
https://github.com/OWNER/REPO.git
git+https://github.com/OWNER/REPO.git
git@github.com:OWNER/REPO.git
ssh://git@github.com/OWNER/REPO.git
```

A URL is rejected (regardless of label) if its path points to a sub-page rather than the repository root:

| Rejected path component | Reason |
|------------------------|--------|
| `/issues`, `/pulls` | Issue/PR tracker |
| `/actions` | Actions tab |
| `/releases` | Release listing |
| `/wiki` | Wiki |
| `/blob/...`, `/tree/...` | Specific file or directory |
| `/topics`, `/search` | GitHub search pages |

Organization profiles (`github.com/OWNER` with no repo) and gist URLs are also rejected.

## Multiple candidates and deduplication

A single package may produce several candidates from different fields. insecure-tree keeps all candidates but deduplicates by `owner/repo` (case-insensitive), keeping the highest-confidence entry for each unique repo. The `selected_repo` used for scanning is the highest-confidence candidate overall.

## Repo overrides

When PyPI metadata is wrong or missing, override the selected repo in configuration:

```toml
[tool.insecure-tree.repo_overrides]
"Pillow" = "https://github.com/python-pillow/Pillow"
```

Or on the command line:

```bash
insecure-tree scan --repo-override Pillow=python-pillow/Pillow
```

Overrides always receive `high` confidence and `source_field = "config_override"`.
