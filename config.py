"""Central configuration for the build agent.

Keeping every tunable in one place makes it obvious what to change when the
agent misbehaves (wrong model, timeouts too tight, paths in the wrong place)
without hunting through the pipeline modules.
"""

from pathlib import Path

# --- Claude -------------------------------------------------------------
# claude-opus-5 is the default per Anthropic's current guidance: strongest
# coding/agentic performance, and this agent's whole job is writing code.
MODEL_ID = "claude-opus-5"
EFFORT = "high"          # low | medium | high | xhigh | max
MAX_TOKENS = 16000        # generous ceiling for a full generated script
MAX_FIX_ATTEMPTS = 3      # initial generation + this many self-healing retries

# --- Execution ------------------------------------------------------------
EXEC_TIMEOUT_SECONDS = 120

# --- Paths ------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_REQUIREMENTS_PATH = PROJECT_ROOT / "user_requirements" / "requirements.md"
DEFAULT_INPUT_PATH = PROJECT_ROOT / "user_data" / "input.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "output" / "result.csv"
GENERATED_SCRIPT_PATH = PROJECT_ROOT / "generated" / "solution.py"
LOG_DIR = PROJECT_ROOT / "logs"

# How much of a large input file to show Claude when drafting the program.
# The generated program reads the real file itself at run time; this preview
# only has to be enough for Claude to infer the shape of the data.
INPUT_PREVIEW_CHARS = 4000
