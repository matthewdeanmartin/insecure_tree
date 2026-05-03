#!/usr/bin/env bash
set -euo pipefail
source ./.bitrab-ci-scripts/setup.sh
# Requires UV_PUBLISH_TOKEN to be set (trusted publishing via PyPI OIDC is preferred).
uv publish dist/*
