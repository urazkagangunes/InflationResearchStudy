#!/bin/bash
# Daily runner - use with cron or launchd
# crontab -e -> 0 11 * * * /path/to/run_daily.sh >> /path/to/cron.log 2>&1

cd "$(dirname "$0")/.."
echo "--- $(date '+%Y-%m-%d %H:%M:%S') ---"
python3 -m scripts.run_scraper
