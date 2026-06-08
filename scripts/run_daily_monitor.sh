#!/bin/bash

PROJECT_DIR="$HOME/Desktop/stock_evaluator"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/daily_monitor.log"

mkdir -p "$LOG_DIR"

echo "============================================================" >> "$LOG_FILE"
echo "Daily Monitor started: $(date)" >> "$LOG_FILE"
echo "============================================================" >> "$LOG_FILE"

cd "$PROJECT_DIR" || exit 1

"$PROJECT_DIR/venv/bin/python3" "$PROJECT_DIR/scripts/run_daily_monitor.py" >> "$LOG_FILE" 2>&1

EXIT_CODE=$?

echo "Daily Monitor finished: $(date)" >> "$LOG_FILE"
echo "Exit code: $EXIT_CODE" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

exit $EXIT_CODE
