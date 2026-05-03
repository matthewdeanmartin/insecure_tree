#!/usr/bin/env bash
set -euo pipefail
source ./.bitrab-ci-scripts/setup.sh
uv run isort --check-only insecure_tree tests
uv run black --check insecure_tree tests
uv run ruff check --quiet insecure_tree tests
uv run pylint --score=n --reports=n --rcfile=.pylintrc insecure_tree
uv run pylint --score=n --reports=n --rcfile=.pylintrc_tests tests
