"""The agent's main loop: requirements + input -> generated program -> output.

    requirements.md ──┐
                       ├─> prompt_builder ─> claude_client ─> generated/solution.py
    input preview ─────┘                                            │
                                                                      v
                                                          code_executor (subprocess)
                                                                      │
                                              success? ──no──> prompt_builder.build_fix_prompt
                                                 │                    (loop, up to MAX_FIX_ATTEMPTS)
                                                 v
                                          io_handlers.validate_output
                                                 │
                                                 v
                                           output/result.*
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import config
from agent import claude_client, code_executor, io_handlers, prompt_builder


@dataclass
class RunResult:
    success: bool
    attempts: int
    output_path: Path
    summary: str
    generated_script_path: Path


def _timestamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _write_log(log_dir: Path, name: str, content: str) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / name).write_text(content, encoding="utf-8")


def run(
    requirements_path: Path = config.DEFAULT_REQUIREMENTS_PATH,
    input_path: Path = config.DEFAULT_INPUT_PATH,
    output_path: Path = config.DEFAULT_OUTPUT_PATH,
    generated_script_path: Path = config.GENERATED_SCRIPT_PATH,
    max_attempts: int = config.MAX_FIX_ATTEMPTS,
) -> RunResult:
    requirements_path = Path(requirements_path)
    input_path = Path(input_path)
    output_path = Path(output_path)
    generated_script_path = Path(generated_script_path)
    run_id = _timestamp()
    run_log_dir = config.LOG_DIR / run_id

    requirements_md = io_handlers.load_requirements(requirements_path)
    input_preview = io_handlers.load_input_preview(input_path, config.INPUT_PREVIEW_CHARS)
    output_format = io_handlers.infer_output_format(output_path)

    client = claude_client.get_client()

    code = None
    last_error = None

    for attempt in range(1, max_attempts + 1):
        if attempt == 1:
            prompt = prompt_builder.build_initial_prompt(requirements_md, input_preview, output_format)
        else:
            prompt = prompt_builder.build_fix_prompt(code, last_error, requirements_md)

        _write_log(run_log_dir, f"attempt_{attempt}_prompt.md", prompt)

        try:
            code = claude_client.generate_code(client, prompt_builder.SYSTEM_PROMPT, prompt)
        except claude_client.CodeGenerationError as exc:
            # Nothing to retry against Claude for (auth/network/refusal) --
            # fail fast rather than burning attempts on the same error.
            return RunResult(False, attempt, output_path, f"Code generation failed: {exc}", generated_script_path)

        _write_log(run_log_dir, f"attempt_{attempt}_solution.py", code)
        generated_script_path.parent.mkdir(parents=True, exist_ok=True)
        generated_script_path.write_text(code, encoding="utf-8")

        exec_result = code_executor.run_generated_script(generated_script_path, input_path, output_path)
        _write_log(
            run_log_dir,
            f"attempt_{attempt}_execution.log",
            f"returncode: {exec_result.returncode}\n\n--- stdout ---\n{exec_result.stdout}\n\n--- stderr ---\n{exec_result.stderr}",
        )

        if not exec_result.success:
            last_error = exec_result.stderr or f"Process exited with code {exec_result.returncode} and no stderr output."
            continue

        try:
            summary = io_handlers.validate_output(output_path, output_format)
        except (FileNotFoundError, ValueError) as exc:
            last_error = f"Program ran successfully but produced a bad output file: {exc}"
            continue

        return RunResult(True, attempt, output_path, summary, generated_script_path)

    return RunResult(
        False,
        max_attempts,
        output_path,
        f"Gave up after {max_attempts} attempts. Last error:\n{last_error}",
        generated_script_path,
    )
