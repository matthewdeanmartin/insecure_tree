"""Safe subprocess execution wrapper."""

from __future__ import annotations

import logging
import re
import subprocess  # nosec B404
from pathlib import Path

log = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"gh[ps]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{82,}")


class SubprocessError(Exception):
    def __init__(self, cmd: list[str], returncode: int, stderr: str) -> None:
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"Command {cmd[0]!r} exited {returncode}: {stderr[:200]}")


def _redact(s: str) -> str:
    return _TOKEN_RE.sub("***", s)


def run_subprocess(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    timeout: float = 60.0,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> tuple[int, str, str]:
    """Run a subprocess and return (returncode, stdout, stderr).

    Raises SubprocessError on non-zero exit.  Never uses shell=True.
    """
    safe_cmd = [_redact(arg) for arg in cmd]
    log.debug("run: %s", " ".join(safe_cmd))

    try:
        result = subprocess.run(  # nosec B603
            cmd,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd,
            timeout=timeout,
            env=env,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"Command {cmd[0]!r} timed out after {timeout}s") from exc

    if check and result.returncode != 0:
        raise SubprocessError(cmd, result.returncode, _redact(result.stderr))

    return result.returncode, result.stdout, result.stderr
