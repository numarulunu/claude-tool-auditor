#!/bin/bash
set -uo pipefail

# run-audit.sh — Run tool audit and save report
# Can be scheduled weekly or run manually.
#
# Usage:
#   ./run-audit.sh              # Audit all tools
#   ./run-audit.sh "Finance"    # Audit one tool

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="/c/Python314/python"
REPORT="$SCRIPT_DIR/_last-audit.md"
LOGFILE="$SCRIPT_DIR/_audit.log"

exec >> "$LOGFILE" 2>&1
echo "=== Tool Audit — $(date) ==="

if [ -n "${1:-}" ]; then
    $PYTHON "$SCRIPT_DIR/audit.py" --tool "$1" --output "$REPORT"
else
    $PYTHON "$SCRIPT_DIR/audit.py" --output "$REPORT"
fi

if [ $? -ne 0 ]; then
    echo "ERROR: Audit failed."
    exit 1
fi

echo "Report saved to $REPORT"
echo "=== Done $(date) ==="
