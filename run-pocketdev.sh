#!/bin/bash
set -uo pipefail

# run-pocketdev.sh — Run pocketDEV in any mode.
#
# Usage:
#   ./run-pocketdev.sh                            # Agent mode (default)
#   ./run-pocketdev.sh agent                      # Agent mode (explicit)
#   ./run-pocketdev.sh snapshot                   # Generate snapshot only
#   ./run-pocketdev.sh audit                      # Audit all tools
#   ./run-pocketdev.sh audit "Finance"            # Audit one tool
#   ./run-pocketdev.sh review "Finance"           # Deep review
#   ./run-pocketdev.sh diagnose "Transcriptor"    # Diagnose breakage

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="/c/Python314/python"
LOGFILE="$SCRIPT_DIR/_pocketdev.log"

MODE="${1:-agent}"
TOOL="${2:-}"

exec >> "$LOGFILE" 2>&1
echo "=== pocketDEV $MODE — $(date) ==="

case "$MODE" in
    agent)
        # Phase 1: Generate snapshot
        echo "[phase 1] Generating snapshot..."
        $PYTHON "$SCRIPT_DIR/pocketdev.py" snapshot --output "$SCRIPT_DIR/_snapshot.json"
        if [ $? -ne 0 ]; then
            echo "ERROR: Snapshot generation failed. Aborting agent run."
            exit 1
        fi

        # Ensure state files exist
        touch "$SCRIPT_DIR/_backlog.md"
        touch "$SCRIPT_DIR/_changelog.md"

        # Phase 2: Launch Claude headless
        echo "[phase 2] Launching Claude headless session..."
        claude -p \
            --append-system-prompt-file "$SCRIPT_DIR/agent-prompt.md" \
            --allowedTools "Read,Glob,Grep,Edit,Write,Bash(git log:*),Bash(git diff:*),Bash(git show:*)" \
            --max-budget-usd 5 \
            "You are pocketDEV running your daily improvement cycle.

Read these files to get your context:
1. $SCRIPT_DIR/_snapshot.json (structured repo data)
2. $SCRIPT_DIR/_changelog.md (history of past changes)
3. $SCRIPT_DIR/_backlog.md (current improvement proposals)

Then read the actual source code of repos that need attention. Propose improvements by editing _backlog.md. If anything is urgent, write _urgent.md.

Today is $(date '+%Y-%m-%d'). Work directory: $SCRIPT_DIR"
        ;;
    snapshot)
        $PYTHON "$SCRIPT_DIR/pocketdev.py" snapshot --output "$SCRIPT_DIR/_snapshot.json"
        ;;
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
        echo "Unknown mode: $MODE. Use: agent, snapshot, audit, review, diagnose"
        exit 1
        ;;
esac

STATUS=$?
if [ $STATUS -ne 0 ]; then
    echo "ERROR: pocketDEV $MODE failed (exit $STATUS)."
    exit 1
fi

echo "=== Done $(date) ==="
