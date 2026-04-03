#!/bin/bash
set -uo pipefail

# run-pocketdev.sh — Run pocketDEV in any mode.
#
# Usage:
#   ./run-pocketdev.sh audit                   # Audit all tools
#   ./run-pocketdev.sh audit "Finance"          # Audit one tool
#   ./run-pocketdev.sh review "Finance"         # Deep review
#   ./run-pocketdev.sh diagnose "Transcriptor"  # Diagnose breakage

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="/c/Python314/python"
LOGFILE="$SCRIPT_DIR/_pocketdev.log"

MODE="${1:-audit}"
TOOL="${2:-}"

exec >> "$LOGFILE" 2>&1
echo "=== pocketDEV $MODE — $(date) ==="

case "$MODE" in
    audit)
        if [ -n "$TOOL" ]; then
            $PYTHON "$SCRIPT_DIR/pocketdev.py" audit --tool "$TOOL" --output "$SCRIPT_DIR/_last-audit.md"
        else
            $PYTHON "$SCRIPT_DIR/pocketdev.py" audit --output "$SCRIPT_DIR/_last-audit.md"
        fi
        ;;
    review)
        if [ -z "$TOOL" ]; then
            echo "ERROR: review requires a tool name."
            exit 1
        fi
        $PYTHON "$SCRIPT_DIR/pocketdev.py" review "$TOOL" --output "$SCRIPT_DIR/_last-review.md"
        ;;
    diagnose)
        if [ -z "$TOOL" ]; then
            echo "ERROR: diagnose requires a tool name."
            exit 1
        fi
        $PYTHON "$SCRIPT_DIR/pocketdev.py" diagnose "$TOOL" --output "$SCRIPT_DIR/_last-diagnose.md"
        ;;
    *)
        echo "Unknown mode: $MODE. Use: audit, review, diagnose"
        exit 1
        ;;
esac

STATUS=$?
if [ $STATUS -ne 0 ]; then
    echo "ERROR: pocketDEV $MODE failed (exit $STATUS)."
    exit 1
fi

echo "=== Done $(date) ==="
