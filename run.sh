#!/usr/bin/env bash
# Interactive wrapper for the Java → Python Migration Orchestrator.
# Usage:
#   ./run.sh                  # fully interactive
#   ./run.sh sample_java/     # pre-fill source dir, still interactive

set -euo pipefail

# ── Helpers ───────────────────────────────────────────────────────────────────

bold()  { printf '\033[1m%s\033[0m' "$*"; }
cyan()  { printf '\033[36m%s\033[0m' "$*"; }
green() { printf '\033[32m%s\033[0m' "$*"; }
yellow(){ printf '\033[33m%s\033[0m' "$*"; }
dim()   { printf '\033[2m%s\033[0m'  "$*"; }

hr() { printf '%0.s─' {1..60}; echo; }

# ── Header ────────────────────────────────────────────────────────────────────

echo
echo "$(bold '╔══════════════════════════════════════════════════════════╗')"
echo "$(bold '║')"
printf "$(bold '║')  $(cyan 'Java → Python Migration Orchestrator')\n"
echo "$(bold '║')  $(dim 'Hub & Spoke · Test-Driven · MCP Infrastructure')"
echo "$(bold '║')"
echo "$(bold '╚══════════════════════════════════════════════════════════╝')"
echo

# ── Source directory ──────────────────────────────────────────────────────────

if [ -n "${1:-}" ]; then
    SOURCE_DIR="$1"
    echo "Source directory : $(bold "$SOURCE_DIR")"
else
    read -rp "Source directory : " SOURCE_DIR
fi

if [ ! -d "$SOURCE_DIR" ]; then
    echo "$(yellow "Warning: '$SOURCE_DIR' does not exist yet — will be resolved at runtime.")"
fi

# ── Derive output directory (mirrors config.py / main.py logic) ───────────────

DATA_FOLDER="${DATA_FOLDER:-$HOME/data_code_conversion}"
PROJECT_NAME="$(basename "${SOURCE_DIR%/}")"
OUTPUT_DIR="$DATA_FOLDER/$PROJECT_NAME"
STATE_FILE="$OUTPUT_DIR/migration_state.json"

echo "Output directory : $(bold "$OUTPUT_DIR")"
echo

# ── Detect existing state ─────────────────────────────────────────────────────

START_STEP="1a"
SUGGESTED=""

if [ -f "$STATE_FILE" ]; then
    hr
    echo "$(green 'Existing migration state found:')"
    echo

    # Parse state with Python and print a summary + derive suggestion
    SUGGESTED=$(python3 - "$STATE_FILE" <<'PYEOF'
import json, sys

STATUS_TO_NEXT = {
    "pending":         ("1a", "no prior run"),
    "analyzing":       ("1a", "was mid-analysis — re-run 1-A"),
    "documented":      ("1c", "spec done — resume at 1-C Architect"),
    "architected":     ("2",  "Step 1 done — resume at Step 2 Tests"),
    "human_review":    ("2",  "resume at Step 2 Tests"),
    "tests_generated": ("3",  "Steps 1+2 done — resume at Step 3 Convert"),
    "converting":      ("3",  "was mid-conversion — re-run Step 3"),
    "completed":       ("1a", "already completed — re-run from scratch"),
    "failed":          ("1a", "failed — re-run from scratch"),
}

with open(sys.argv[1]) as f:
    state = json.load(f)

modules = state.get("modules", {})
suggestion = "1a"
for mname, m in modules.items():
    status = m.get("status", "pending")
    next_step, reason = STATUS_TO_NEXT.get(status, ("1a", "unknown"))
    artifacts = m.get("artifacts", {})
    artifact_list = "  ".join(f"{k}" for k in artifacts) if artifacts else "none"
    print(f"  Module : {mname}")
    print(f"  Status : {status}  →  {reason}")
    print(f"  Files  : {artifact_list}")
    print()
    suggestion = next_step   # last module wins if multiple

print(suggestion, end="")
PYEOF
    )

    # The last line printed by python is the suggestion; the rest is display text.
    # We captured it all in SUGGESTED; split it now.
    DISPLAY="${SUGGESTED%$'\n'*}"       # everything except last line
    SUGGESTED_STEP="${SUGGESTED##*$'\n'}" # last line only

    # Print the module summary (everything except the last bare token line)
    echo "$DISPLAY"

    hr
    read -rp "Resume from existing state? [Y/n] " RESUME_ANS
    RESUME_ANS="${RESUME_ANS:-y}"

    if [[ "$RESUME_ANS" =~ ^[Yy] ]]; then
        echo
        echo "$(bold 'Where would you like to resume?')"
        echo
        echo "  $(bold '1)')  1-A  $(cyan 'Understand')    — re-run LLM analysis from scratch"
        echo "  $(bold '2)')  1-B  $(cyan 'Document')      — reload analysis, re-run spec writer"
        echo "  $(bold '3)')  1-C  $(cyan 'Architect')     — reload analysis + spec, re-run architect"
        echo "  $(bold '4)')   2   $(cyan 'Generate Tests')— skip all of Step 1"
        echo "  $(bold '5)')   3   $(cyan 'Convert Code')  — skip Steps 1 and 2"
        echo
        echo "  $(dim "(suggested based on current state: $SUGGESTED_STEP)")"
        echo

        read -rp "  Choice [${SUGGESTED_STEP}] : " CHOICE
        CHOICE="${CHOICE:-$SUGGESTED_STEP}"

        case "$CHOICE" in
            1|1a|1A) START_STEP="1a" ;;
            2|1b|1B) START_STEP="1b" ;;
            3|1c|1C) START_STEP="1c" ;;
            4|"2")   START_STEP="2"  ;;
            5|"3")   START_STEP="3"  ;;
            *)
                echo "$(yellow "Unrecognised choice '$CHOICE' — defaulting to $SUGGESTED_STEP")"
                START_STEP="$SUGGESTED_STEP"
                ;;
        esac
    fi
fi

# ── Other options ─────────────────────────────────────────────────────────────

echo
hr
echo

read -rp "Max retries for Step 3 [3] : " MAX_RETRIES
MAX_RETRIES="${MAX_RETRIES:-3}"

read -rp "Log level (DEBUG/INFO/WARNING) [DEBUG] : " LOG_LEVEL
LOG_LEVEL="${LOG_LEVEL:-DEBUG}"

# ── Summary & confirm ─────────────────────────────────────────────────────────

echo
hr
echo
echo "  Source      : $(bold "$SOURCE_DIR")"
echo "  Output      : $(bold "$OUTPUT_DIR")"
echo "  Start step  : $(bold "$START_STEP")"
echo "  Retries     : $(bold "$MAX_RETRIES")"
echo "  Log level   : $(bold "$LOG_LEVEL")"
echo
hr
read -rp "$(bold 'Start migration? [Y/n] ')" GO
GO="${GO:-y}"
if [[ ! "$GO" =~ ^[Yy] ]]; then
    echo "Aborted."
    exit 0
fi

# ── Run ───────────────────────────────────────────────────────────────────────

echo
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

exec python main.py "$SOURCE_DIR" \
    --start-step "$START_STEP" \
    --retries    "$MAX_RETRIES" \
    --log-level  "$LOG_LEVEL"
