"""Reading the user's requirements/input, and sanity-checking the output.

This module never does the actual CSV/JSON *generation* -- that's the job of
the Python program Claude writes. It only prepares what Claude needs to see
(a preview of the input) and later confirms the generated program actually
produced something sane.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class InputPreview:
    path: Path
    detected_format: str   # "json" or "text"
    preview_text: str      # truncated, human/LLM-readable sample
    full_char_count: int


def load_requirements(path: Path) -> str:
    """Read the user's markdown requirements file as plain text."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Requirements file not found: {path}. "
            "Write what the program should do in Markdown there first."
        )
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Requirements file is empty: {path}")
    return text


def load_input_preview(path: Path, preview_chars: int) -> InputPreview:
    """Detect the input format and build a short preview for the prompt.

    The generated program reads the real file itself at run time -- this
    preview just needs to be enough for Claude to infer field names/shape.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    raw = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()

    if suffix == ".json":
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Input file {path} has a .json extension but isn't valid JSON: {exc}") from exc

        if isinstance(data, list):
            sample = data[:5]
        elif isinstance(data, dict):
            sample = {k: data[k] for k in list(data)[:5]}
        else:
            sample = data
        pretty = json.dumps(sample, indent=2, ensure_ascii=False)
        preview = pretty[:preview_chars]
        if isinstance(data, list):
            preview += f"\n... ({len(data)} total records)" if len(data) > 5 else ""
        return InputPreview(path, "json", preview, len(raw))

    # Treat everything else (.txt, .csv, no extension, ...) as plain text.
    preview = raw[:preview_chars]
    if len(raw) > preview_chars:
        preview += "\n... (truncated)"
    return InputPreview(path, "text", preview, len(raw))


def validate_output(path: Path, expected_format: str) -> str:
    """Confirm the generated program produced a non-empty, parseable file.

    Returns a short human-readable summary on success; raises on failure so
    the orchestrator can feed the problem back to Claude as a fix prompt.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Expected output file was not created: {path}")

    if path.stat().st_size == 0:
        raise ValueError(f"Output file {path} was created but is empty")

    if expected_format == "json":
        data = json.loads(path.read_text(encoding="utf-8"))
        count = len(data) if isinstance(data, (list, dict)) else 1
        return f"Valid JSON with {count} top-level item(s)."

    if expected_format == "csv":
        with path.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        if not rows:
            raise ValueError(f"Output CSV {path} has no rows at all (not even a header)")
        return f"Valid CSV with header {rows[0]!r} and {len(rows) - 1} data row(s)."

    raise ValueError(f"Unknown expected_format: {expected_format!r}")


def infer_output_format(output_path: Path) -> str:
    """Decide json vs csv purely from the requested output file's extension."""
    suffix = Path(output_path).suffix.lower().lstrip(".")
    if suffix not in ("json", "csv"):
        raise ValueError(
            f"Output path {output_path} must end in .json or .csv (got {suffix!r})"
        )
    return suffix
