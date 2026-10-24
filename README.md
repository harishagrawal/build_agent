# build_agent

An AI agent that reads a **markdown requirements file** + an **input data
file**, writes a **Python program** to satisfy the requirements, runs it
against the input, and produces **CSV/JSON output** — self-correcting if the
first attempt doesn't run.

## How it works

```
user_requirements/requirements.md ──┐
                                     ├─> Claude (claude-opus-5) ─> generated/solution.py
user_data/input.json / .txt ────────┘                                   │
                                                                          v
                                                        runs as: python3 solution.py
                                                           --input <file> --output <file>
                                                                          │
                                         failed? ──yes──> send traceback back to Claude,
                                             │              ask it to fix the code
                                             │              (up to --max-attempts times)
                                             no
                                             v
                                   output/result.csv or .json
```

Every attempt's prompt, generated code, and execution log is written under
`logs/<run-timestamp>/` so you can see exactly what Claude was asked and
what it produced.

## Project structure

```
build_agent/
├── main.py                       # CLI entry point
├── config.py                     # model id, paths, retry/timeout limits
├── agent/
│   ├── orchestrator.py           # the run() loop: generate -> execute -> validate -> retry
│   ├── prompt_builder.py         # builds the code-gen and fix-it prompts
│   ├── claude_client.py          # calls Claude, extracts the code block, typed error handling
│   ├── code_executor.py          # runs generated/solution.py as a subprocess
│   └── io_handlers.py            # reads requirements.md/input file, validates the output file
├── user_requirements/
│   └── requirements.md           # <- you write what the program should do, here
├── user_data/
│   └── input.json                # <- you provide the data to process, here (.json or .txt)
├── generated/
│   └── solution.py               # <- Claude's program lands here (overwritten each run)
├── output/
│   └── result.csv                # <- final result (.csv or .json, by extension)
├── logs/
│   └── <timestamp>/              # prompt + generated code + execution log per attempt
└── tests/
    └── test_orchestrator.py      # exercises the full pipeline with a mocked Claude client
```

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...      # or: ant auth login
```

## Running it

A sample requirement + input are already in place (customer spend summary).
Run as-is:

```bash
python3 main.py
```

Or point it at your own files:

```bash
python3 main.py \
  --requirements user_requirements/requirements.md \
  --input user_data/input.json \
  --output output/result.csv \
  --max-attempts 3
```

- `--input` may be `.json` or any text format (`.txt`, `.csv`, ...) — the
  agent detects it and previews it for Claude.
- `--output` extension decides the format: `.csv` or `.json`.
- The generated program always takes `--input`/`--output` CLI args itself,
  so `generated/solution.py` is also runnable on its own afterwards.

## Design notes / known limitations

- **No sandboxing.** `generated/solution.py` runs as a normal local
  subprocess with your user's permissions. Only point this at requirements
  you trust — don't run it unattended against untrusted requirement text.
- **Standard library only.** Generated programs are instructed to avoid
  third-party packages (no pandas/numpy/requests/...) so they run reliably
  without an install step. If your task genuinely needs a library, loosen
  that constraint in `agent/prompt_builder.py`.
- **A fresh script per run.** `generated/solution.py` is overwritten every
  time `main.py` runs; look in `logs/` for the history of past attempts.
- **Self-healing retries, not infinite ones.** `--max-attempts` (default 3)
  caps how many times the agent will re-prompt Claude with the traceback
  before giving up and reporting the last error.

## Tests

```bash
python3 -m pytest tests/ -v
```

These mock `claude_client.generate_code` (no API key or network needed) and
verify the full generate → execute → validate → retry-on-failure wiring,
including that a buggy first attempt gets fixed on retry.
