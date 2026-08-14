"""Thin subprocess wrapper used to drive GTKWave's non-GUI helper binaries.

Modeled on the ``run_command`` idiom in the reference ``cbmc-mcp`` server, but
returns a small dataclass and raises typed errors so tools can surface clear,
actionable messages instead of stack traces.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Sequence


class HelperError(RuntimeError):
    """A helper binary failed, was missing, or timed out."""


@dataclass
class Result:
    ok: bool
    stdout: str
    stderr: str
    code: int


def run(argv: Sequence[str], timeout: int = 120, input_text: str | None = None) -> Result:
    """Run ``argv`` and capture output.

    Raises :class:`HelperError` when the binary cannot be found or the call
    times out. A non-zero exit is *not* raised here — callers inspect
    ``Result.ok`` so they can attach command-specific context.
    """
    try:
        proc = subprocess.run(
            list(argv),
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:  # binary not on disk / PATH
        raise HelperError(f"executable not found: {argv[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise HelperError(
            f"'{argv[0]}' timed out after {timeout}s"
        ) from exc

    return Result(
        ok=proc.returncode == 0,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        code=proc.returncode,
    )


def run_checked(argv: Sequence[str], timeout: int = 120, input_text: str | None = None) -> str:
    """Like :func:`run` but raise :class:`HelperError` on a non-zero exit,
    returning stdout on success."""
    res = run(argv, timeout=timeout, input_text=input_text)
    if not res.ok:
        detail = res.stderr.strip() or res.stdout.strip() or f"exit code {res.code}"
        raise HelperError(f"'{argv[0]}' failed: {detail}")
    return res.stdout
