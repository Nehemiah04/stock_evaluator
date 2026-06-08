# Daily Monitor Commands

Run small test:

```bash
cd ~/Desktop/stock_evaluator
source venv/bin/activate
python3 scripts/run_daily_monitor.py 5
```

Run full daily monitor:

```bash
cd ~/Desktop/stock_evaluator
source venv/bin/activate
python3 scripts/run_daily_monitor.py
```

Open app:

```bash
streamlit run app.py
```

Outputs:

```text
data/stocks.db
data/exports/daily_full_scan_*.csv
data/exports/daily_monitor_report_*.csv
```
