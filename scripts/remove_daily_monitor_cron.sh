#!/bin/bash

crontab -l 2>/dev/null | grep -v "run_daily_monitor.sh" | crontab -

echo "Removed daily monitor cron schedule if it existed."
echo "Remaining daily monitor cron entries:"
crontab -l 2>/dev/null | grep "run_daily_monitor.sh" || true
