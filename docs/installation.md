# Installation

## Prerequisites

insecure-tree shells out to [zizmor](https://github.com/woodruffw/zizmor) to analyze workflow files. Install it first:

```bash
# Via pip (recommended if you're already in Python land)
pip install zizmor

# Via cargo (if you have Rust)
cargo install zizmor
```

Confirm it's on your PATH:

```bash
zizmor --version
```

## Install insecure-tree

### pipx (recommended for CLI tools)

```bash
pipx install insecure_tree
```

### pip

```bash
pip install insecure_tree
```

### uv

```bash
uv tool install insecure_tree
```

## Install from source

```bash
git clone https://github.com/matthewdeanmartin/insecure_tree.git
cd insecure_tree
uv sync
uv run insecure-tree --version
```

## Verify the installation

```bash
insecure-tree --version
insecure-tree --help
```

## GitHub token (optional but recommended)

The GitHub API rate limit for unauthenticated requests is 60 per hour. For scanning more than a handful of dependencies, set a personal access token:

```bash
export GITHUB_TOKEN=ghp_...
insecure-tree scan
```

The token only needs **public repository read** access (`public_repo` scope, or no scope at all for a fine-grained token with no extra permissions — GitHub allows reading public repos without scopes).

You can also pass it directly (it will not appear in reports or logs):

```bash
insecure-tree scan --github-token "$GITHUB_TOKEN"
```
