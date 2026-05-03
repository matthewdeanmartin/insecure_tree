#!/usr/bin/env bash
set -euo pipefail
source ./.bitrab-ci-scripts/setup.sh
echo "=== uv audit ==="
uv audit
echo "=== pip-audit ==="
uv run pip-audit
