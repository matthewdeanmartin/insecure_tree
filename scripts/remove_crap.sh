#!/usr/bin/env bash
#
# remove_crap.sh — purge accidentally-committed report/artifact dirs from the
# ENTIRE git history. These dirs contain scan reports that trip secret scanners
# (false positives) and should never have been tracked.
#
# Paths scrubbed (matches .gitignore):
#   .tmp-pages-test/
#   artifacts/
#   insecure-tree-forest-report/
#   insecure-tree-report/
#
# Also normalizes all author/committer identities (currently 3 variants, incl.
# a "GitHub <noreply@github.com>" web-UI committer) to a single canonical name.
#
# Tool: git-filter-repo (modern replacement for filter-branch / BFG).
# This REWRITES HISTORY. All commit hashes after the first affected commit
# change. Anyone with a clone must re-clone or hard-reset afterward.
#
# Usage:
#   bash scripts/remove_crap.sh
#
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

PATHS=(
  ".tmp-pages-test/"
  "artifacts/"
  "insecure-tree-forest-report/"
  "insecure-tree-report/"
)

# --- 0. Safety: refuse to run on a dirty tree -------------------------------
if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: working tree is dirty. Commit or stash changes first." >&2
  exit 1
fi

# --- 1. Ensure git-filter-repo is available ---------------------------------
if ! git filter-repo --version >/dev/null 2>&1; then
  echo ">> git-filter-repo not found; installing via pip..."
  # No --user: it conflicts with active virtualenvs. Installs into whatever
  # environment 'python' resolves to (venv if active, else user/system).
  python -m pip install git-filter-repo
  # filter-repo installs as a git subcommand if on PATH; verify.
  if ! git filter-repo --version >/dev/null 2>&1; then
    echo "ERROR: git-filter-repo installed but 'git filter-repo' still not found." >&2
    echo "       Ensure your pip --user bin dir is on PATH, or run via:" >&2
    echo "       python -m git_filter_repo ..." >&2
    exit 1
  fi
fi

# --- 2. Back up the whole repo (mirror clone) -------------------------------
# filter-repo is irreversible. Keep a full copy in case something goes wrong.
BACKUP_DIR="${REPO_ROOT}-backup-$(date +%Y%m%d-%H%M%S).git"
echo ">> Backing up to: $BACKUP_DIR"
git clone --mirror "$REPO_ROOT" "$BACKUP_DIR"

# --- 3. Build a mailmap to normalize all identities -------------------------
# History currently contains 3 identities (all the user's, but inconsistent),
# including a "GitHub <noreply@github.com>" committer from a web-UI commit.
# Canonical identity for every author AND committer:
CANONICAL="Matthew Dean Martin <matthewdeanmartin@gmail.com>"
MAILMAP_FILE="$(mktemp)"
trap 'rm -f "$MAILMAP_FILE"' EXIT
cat > "$MAILMAP_FILE" <<EOF
${CANONICAL} <matthewdeanmartin@gmail.com>
${CANONICAL} Matthew Martin <matthewdeanmartin@gmail.com>
${CANONICAL} GitHub <noreply@github.com>
EOF

# --- 4. Rewrite history: drop unwanted paths + normalize identities ---------
# --invert-paths => remove the listed paths instead of keeping only them.
# --mailmap      => remap author/committer name+email per the mailmap above.
# --force        => allow running against a repo that isn't a fresh clone.
echo ">> Rewriting history (removing dirs + normalizing author identity)..."
PATH_ARGS=()
for p in "${PATHS[@]}"; do
  PATH_ARGS+=(--path "$p")
done

git filter-repo --invert-paths "${PATH_ARGS[@]}" --mailmap "$MAILMAP_FILE" --force

# --- 5. Verify the paths are gone from all history --------------------------
echo ">> Verifying..."
LEFTOVER="$(git log --all --name-only --pretty=format: -- "${PATHS[@]}" | sort -u | grep -v '^$' || true)"
if [[ -n "$LEFTOVER" ]]; then
  echo "WARNING: paths still present in history:" >&2
  echo "$LEFTOVER" >&2
  exit 1
fi
echo ">> Clean. None of the target paths remain in history."

# --- 6. Verify all commits now carry the canonical identity -----------------
echo ">> Verifying author/committer identities..."
BAD_IDS="$(git log --all --format='%an <%ae>%n%cn <%ce>' | sort -u | grep -vF "$CANONICAL" || true)"
if [[ -n "$BAD_IDS" ]]; then
  echo "WARNING: non-canonical identities remain:" >&2
  echo "$BAD_IDS" >&2
  exit 1
fi
echo ">> All commits attributed to: $CANONICAL"

# --- 7. Re-add the remote (filter-repo strips it by design) -----------------
if ! git remote get-url origin >/dev/null 2>&1; then
  echo ">> Re-adding origin remote..."
  git remote add origin https://github.com/matthewdeanmartin/insecure_tree.git
fi

# --- 8. Force-push the rewritten history ------------------------------------
# REVIEW the local history first (git log, git status), THEN uncomment and run.
# This overwrites the remote. Coordinate with anyone else who has a clone.
#
#   git push origin --force --all
#   git push origin --force --tags
#
echo
echo ">> DONE rewriting locally. Backup at: $BACKUP_DIR"
echo ">> Review with: git log --oneline --stat"
echo ">> Then force-push manually:"
echo ">>     git push origin --force --all"
echo ">>     git push origin --force --tags"
