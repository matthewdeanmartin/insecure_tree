"""Tests for safe subprocess execution."""

import sys
from pathlib import Path

import pytest

from insecure_tree.subprocess import SubprocessError, _redact, run_subprocess


def test_redact_masks_github_tokens() -> None:
    token = f"ghp_{'a' * 36}"

    redacted = _redact(f"prefix {token} suffix")

    assert token not in redacted
    assert redacted == "prefix *** suffix"


def test_run_subprocess_returns_captured_output(tmp_path: Path) -> None:
    returncode, stdout, stderr = run_subprocess(
        [sys.executable, "-c", "print('ok')"],
        cwd=tmp_path,
    )

    assert returncode == 0
    assert stdout.strip() == "ok"
    assert stderr == ""


def test_run_subprocess_raises_redacted_error_output() -> None:
    token = f"ghp_{'a' * 36}"

    with pytest.raises(SubprocessError) as excinfo:
        run_subprocess(
            [
                sys.executable,
                "-c",
                f"import sys; sys.stderr.write('{token} failure'); raise SystemExit(2)",
            ]
        )

    err = excinfo.value
    assert err.returncode == 2
    assert err.stderr == "*** failure"
    assert token not in str(err)
