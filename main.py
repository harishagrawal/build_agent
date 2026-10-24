#!/usr/bin/env python3
"""CLI entry point for the build agent.

    python3 main.py
    python3 main.py --requirements user_requirements/requirements.md \\
                     --input user_data/input.json \\
                     --output output/result.csv
"""

import argparse
import sys
from pathlib import Path

import config
from agent import orchestrator


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--requirements", type=Path, default=config.DEFAULT_REQUIREMENTS_PATH,
                        help="Markdown file describing what the generated program should do.")
    parser.add_argument("--input", type=Path, default=config.DEFAULT_INPUT_PATH,
                        help="Input data file (.json or .txt) for the generated program to process.")
    parser.add_argument("--output", type=Path, default=config.DEFAULT_OUTPUT_PATH,
                        help="Where the generated program should write its result (.csv or .json).")
    parser.add_argument("--max-attempts", type=int, default=config.MAX_FIX_ATTEMPTS,
                        help="Initial attempt plus up to this many self-healing retries on failure.")
    args = parser.parse_args()

    result = orchestrator.run(
        requirements_path=args.requirements,
        input_path=args.input,
        output_path=args.output,
        max_attempts=args.max_attempts,
    )

    print(f"\nGenerated program: {result.generated_script_path}")
    if result.success:
        print(f"Succeeded on attempt {result.attempts}/{args.max_attempts}.")
        print(f"Output: {result.output_path}")
        print(result.summary)
        return 0

    print(f"FAILED after {result.attempts} attempt(s).", file=sys.stderr)
    print(result.summary, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
