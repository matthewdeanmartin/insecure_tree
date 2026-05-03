"""Tests for configuration parsing and merging."""

from pathlib import Path

import pytest

from insecure_tree.config import _parse_ttl, load_config
from insecure_tree.models import ReportFormat, SourceAdapter


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (120, 120),
        ("90", 90),
        ("45s", 45),
        ("30m", 1800),
        ("2h", 7200),
        ("7d", 604800),
    ],
)
def test_parse_ttl(value: object, expected: int) -> None:
    assert _parse_ttl(value) == expected


def test_load_config_reads_pyproject_tool_settings(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.insecure-tree]
source = "requirements"
formats = ["json"]
metadata_ttl = "2h"
repo_ttl = "30m"
fail_on = "warning"

[tool.insecure-tree.github]
token_env = "ALT_GITHUB_TOKEN"

[tool.insecure-tree.zizmor]
bin = "custom-zizmor"
args = ["--offline"]
""".strip(),
        encoding="utf-8",
    )

    config = load_config(tmp_path)

    assert config.source == SourceAdapter.requirements
    assert config.formats == [ReportFormat.json]
    assert config.metadata_ttl == 7200
    assert config.repo_ttl == 1800
    assert config.fail_on == "warning"
    assert config.github.token_env == "ALT_GITHUB_TOKEN"
    assert config.zizmor.bin == "custom-zizmor"
    assert config.zizmor.args == ["--offline"]


def test_load_config_merges_pyproject_and_insecure_tree_toml(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.insecure-tree]
project = "from-pyproject"
output_dir = "pyproject-report"
metadata_ttl = "1h"
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "insecure-tree.toml").write_text(
        """
source = "uv-pip"
metadata_ttl = "5m"

[github]
token = "secret-token"

[zizmor]
args = ["--pedantic"]

[[ignore]]
package = "requests"
rule = "artipacked"
reason = "known test fixture"

[repo_overrides]
requests = "https://github.com/psf/requests"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(tmp_path)

    assert config.project == "from-pyproject"
    assert config.output_dir == "pyproject-report"
    assert config.source == SourceAdapter.uv_pip
    assert config.metadata_ttl == 300
    assert config.github.token == "secret-token"
    assert config.zizmor.args == ["--pedantic"]
    assert len(config.ignore) == 1
    assert config.ignore[0].package == "requests"
    assert config.ignore[0].rule == "artipacked"
    assert config.repo_overrides == {"requests": "https://github.com/psf/requests"}
