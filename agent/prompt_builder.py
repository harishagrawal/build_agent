"""Builds the prompts sent to Claude: the initial code-gen request, and the
follow-up "fix this traceback" request used by the self-healing retry loop.
"""

from __future__ import annotations

from agent.io_handlers import InputPreview

SYSTEM_PROMPT = """\
You are a senior Python engineer embedded in an automated pipeline. Your \
only job is to write ONE complete, self-contained Python program that \
satisfies the user's requirements below. The program you write will be \
executed automatically with no human review, so it must run correctly the \
first time and must not require any manual steps.

Hard constraints on the program you write:
- Python 3 standard library only (json, csv, argparse, re, collections, \
  datetime, itertools, statistics, etc.). No pip installs, no third-party \
  imports (no pandas/numpy/requests/...) -- the execution environment is not \
  guaranteed to have them.
- It must accept exactly two command-line arguments: `--input <path>` and \
  `--output <path>`, parsed with argparse.
- It must read the input file from the `--input` path (not a hardcoded \
  path), in the format described below.
- It must write the result to the `--output` path, in the exact format \
  described below (CSV via the `csv` module, or JSON via the `json` \
  module), and must create the file even if the computed result is empty.
- Wrap the main logic so that any unexpected input produces a clear \
  non-zero-exit error with a readable message on stderr, rather than an \
  unhandled stack trace with no context.
- Do not print the output data to stdout; only write it to the output file. \
  Brief progress/status lines on stdout are fine.

Respond with NOTHING but the code: a single fenced code block starting with \
```python and ending with ```. No prose before or after it, no explanation, \
no markdown headings.
"""


def _input_section(preview: InputPreview) -> str:
    return f"""\
## Input

- Path will be passed as `--input` at runtime.
- Detected format: {preview.detected_format}
- File size: {preview.full_char_count} characters.
- Preview of the actual file content (may be truncated; the real file could \
have more records than shown here -- do not hardcode anything from this \
preview, only use it to infer field names and structure):

```
{preview.preview_text}
```
"""


def build_initial_prompt(
    requirements_md: str,
    input_preview: InputPreview,
    output_format: str,
) -> str:
    return f"""\
## Requirements

{requirements_md}

{_input_section(input_preview)}

## Output

- Path will be passed as `--output` at runtime.
- Required format: {output_format.upper()}
{"- Use the csv module (csv.writer or csv.DictWriter), with a header row." if output_format == "csv" else "- Use the json module (json.dump), UTF-8, indent=2 for readability."}

Write the complete Python program now, following every constraint in the \
system prompt.
"""


def build_fix_prompt(
    previous_code: str,
    error_output: str,
    requirements_md: str,
) -> str:
    return f"""\
The Python program below was run and it failed. Fix it.

## Original requirements (unchanged)

{requirements_md}

## Program that failed

```python
{previous_code}
```

## Error captured when running it (stderr / exception)

```
{error_output.strip()[-4000:]}
```

Diagnose the root cause and return the complete corrected program. Keep the \
same `--input`/`--output` CLI contract and the same output format. Respond \
with NOTHING but the corrected code: a single fenced ```python code block, \
no prose before or after it.
"""
