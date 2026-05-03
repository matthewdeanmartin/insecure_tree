"""Safe subprocess execution wrapper."""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"gh[ps]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{82,}")


class SubprocessError(Exception):
    def __init__(self, cmd: List[str], returncode: int, stderr: str) -> None:
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"Command {cmd[0]!r} exited {returncode}: {stderr[:200]}")


def _redact(s: str) -> str:
    return _TOKEN_RE.sub("***", s)


def run_subprocess(
    cmd: List[str],
    *,
    cwd: Optional[Path] = None,
    timeout: float = 60.0,
    env: Optional[Dict[str, str]] = None,
) -> Tuple[int, str, str]:
    """Run a subprocess and return (returncode, stdout, stderr).

    Raises SubprocessError on non-zero exit.  Never uses shell=True.
    """
    safe_cmd = [_redact(arg) for arg in cmd]
    log.debug("run: %s", " ".join(safe_cmd))

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
        timeout=timeout,
        env=env,
        shell=False,
    )

    if result.returncode != 0:
        raise SubprocessError(cmd, result.returncode, _redact(result.stderr))

    return result.returncode, result.stdout, result.stderr
