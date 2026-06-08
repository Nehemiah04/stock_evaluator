#!/bin/bash

PROJECT_DIR="$HOME/Desktop/stock_evaluator"
RUNNER="$PROJECT_DIR/scripts/run_daily_monitor.sh"
CRON_JOB="30 6 * * 1-5 $RUNNER"

if [ ! -x "$RUNNER" ]; then
  echo "Daily monitor runner is not executable: $RUNNER"
  echo "Run: chmod +x $RUNNER"
  exit 1
fi

(crontab -l 2>/dev/null | grep -v "run_daily_monitor.sh"; echo "$CRON_JOB") | crontab -

echo "Installed daily monitor cron schedule:"
crontab -l | grep "run_daily_monitor.sh"
