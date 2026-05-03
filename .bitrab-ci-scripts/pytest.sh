#!/usr/bin/env bash
set -euo pipefail
source ./.bitrab-ci-scripts/setup.sh
uv run pytest tests -q -n auto --dist=loadfile \
    --cov=insecure_tree \
    --cov-report=xml:coverage/cobertura-coverage.xml \
    --cov-report=html:htmlcov \
    --junitxml=junit.xml \
    -o junit_family=legacy \
    --timeout=60
