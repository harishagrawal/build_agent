"""Runs the generated program as a subprocess and captures the result.

Security note: this executes AI-generated code directly on the local
machine with no sandboxing. Only point this agent at requirements you trust
-- see the README's "Safety" section before running it against anything
sensitive.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import config


@dataclass
class ExecutionResult:
    success: bool
    stdout: str
    stderr: str
    returncode: int | None  # None on timeout


def run_generated_script(script_path: Path, input_path: Path, output_path: Path) -> ExecutionResult:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        completed = subprocess.run(
            [sys.executable, str(script_path), "--input", str(input_path), "--output", str(output_path)],
            capture_output=True,
            text=True,
            timeout=config.EXEC_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        return ExecutionResult(
            success=False,
            stdout=exc.stdout or "",
            stderr=(exc.stderr or "") + f"\n[killed: exceeded {config.EXEC_TIMEOUT_SECONDS}s timeout]",
            returncode=None,
        )

    return ExecutionResult(
        success=completed.returncode == 0,
        stdout=completed.stdout,
        stderr=completed.stderr,
        returncode=completed.returncode,
    )
