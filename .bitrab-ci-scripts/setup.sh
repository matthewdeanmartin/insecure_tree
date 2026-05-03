#!/usr/bin/env bash
set -euo pipefail
curl -LsSf https://astral.sh/uv/install.sh | sh -s -- -y
export PATH="$HOME/.local/bin:$PATH"
uv --version
uv sync --all-extras
