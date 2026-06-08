# Daily Monitor Schedule

## Manual Run

```bash
cd ~/Desktop/stock_evaluator
./scripts/run_daily_monitor.sh
```

## View Logs

```bash
tail -n 80 logs/daily_monitor.log
```

## View Schedule

```bash
crontab -l
```

## Install Schedule

This writes your full Mac path into cron.

```bash
cd ~/Desktop/stock_evaluator
./scripts/install_daily_monitor_cron.sh
```

## Current Schedule

Runs every weekday at 6:30 AM:

```cron
30 6 * * 1-5 /Users/yourname/Desktop/stock_evaluator/scripts/run_daily_monitor.sh
```

## Remove Schedule

```bash
cd ~/Desktop/stock_evaluator
./scripts/remove_daily_monitor_cron.sh
```

## Output Locations

```text
data/stocks.db
data/exports/
logs/daily_monitor.log
```
