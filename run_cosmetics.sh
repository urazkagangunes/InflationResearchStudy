#!/bin/bash
# run_cosmetics.sh — Runs all cosmetics scrapers sequentially
# Cron: 0 3 * * * /root/InflationResearchStudy/run_cosmetics.sh >> /root/InflationResearchStudy/logs/cosmetics/cron.log 2>&1

BASE="$(cd "$(dirname "$0")" && pwd)"
COSMETICS_DIR="$BASE/InflationItems/Codes/13_Personal_Care/Cosmetics"
DATE=$(date +%Y-%m-%d)
LOG_DIR="$BASE/logs/cosmetics"
mkdir -p "$LOG_DIR"

echo ""
echo "========================================"
echo "  Cosmetics Scraping Run: $DATE"
echo "========================================"

# Python environment — activate venv if present
if [ -f "$BASE/.venv/bin/activate" ]; then
    source "$BASE/.venv/bin/activate"
    echo "[venv] Activated."
fi

# --- Scraper runner function ---
run_scraper() {
    local name="$1"
    local script="$2"
    local workdir="$3"
    local timeout_secs="${4:-7200}"
    local log="$LOG_DIR/${name}_${DATE}.log"

    echo ""
    echo "--- Starting: $name ---"
    if [ ! -f "$script" ]; then
        echo "[$name] SKIPPED — script not found: $script"
        return
    fi

    pushd "$workdir" > /dev/null
    timeout "$timeout_secs" python3 -u "$script" > "$log" 2>&1
    local exit_code=$?
    popd > /dev/null

    if [ $exit_code -eq 124 ]; then
        echo "[$name] ⏱ TIMEOUT (${timeout_secs}s exceeded) — log: $log"
    elif [ $exit_code -eq 0 ]; then
        echo "[$name] ✓ SUCCESS"
    else
        echo "[$name] ✗ ERROR (exit code: $exit_code) — log: $log"
        tail -5 "$log" | sed 's/^/    /'
    fi
}

# =============================================
# SCRAPERS
# =============================================

run_scraper "Avon" \
    "$COSMETICS_DIR/Avon/avon.py" \
    "$COSMETICS_DIR/Avon"

run_scraper "BeymenBeauty" \
    "$COSMETICS_DIR/Beymen Beauty/beymen_scraper.py" \
    "$COSMETICS_DIR/Beymen Beauty"

# Boyner is paused due to Cloudflare Turnstile datacenter challenge
# run_scraper "Boyner" \
#     "$COSMETICS_DIR/Boyner/run_all_boyner.py" \
#     "$COSMETICS_DIR/Boyner"

run_scraper "Dermoeczanem" \
    "$COSMETICS_DIR/Dermoeczanem/dermoeczanem_scraper.py" \
    "$COSMETICS_DIR/Dermoeczanem"

run_scraper "Kozmela" \
    "$COSMETICS_DIR/Kozmela/kozmela_scraper.py" \
    "$COSMETICS_DIR/Kozmela"

run_scraper "Eveshop" \
    "$COSMETICS_DIR/Eveshop/eveshop_scraper.py" \
    "$COSMETICS_DIR/Eveshop"

run_scraper "Flormar" \
    "$COSMETICS_DIR/Flormar/flormar_scraper.py" \
    "$COSMETICS_DIR/Flormar"

run_scraper "Gratis" \
    "$COSMETICS_DIR/Gratis/gratis_scraper.py" \
    "$COSMETICS_DIR/Gratis" \
    12600

run_scraper "Dermomarket" \
    "$COSMETICS_DIR/Dermomarket/dermomarket_scraper.py" \
    "$COSMETICS_DIR/Dermomarket"

run_scraper "GoldenRose" \
    "$COSMETICS_DIR/GoldenRose/scripts/run_scraper.py" \
    "$COSMETICS_DIR/GoldenRose"

run_scraper "LOccitane" \
    "$COSMETICS_DIR/Loccitane/loccitane_scraper.py" \
    "$COSMETICS_DIR/Loccitane"

run_scraper "MandS" \
    "$COSMETICS_DIR/M&S/m&s.py" \
    "$COSMETICS_DIR/M&S"

run_scraper "Pazarium" \
    "$COSMETICS_DIR/Pazarium/pazarium_scraper.py" \
    "$COSMETICS_DIR/Pazarium"

run_scraper "Rossmann" \
    "$COSMETICS_DIR/Rossmann/scripts/main.py" \
    "$COSMETICS_DIR/Rossmann"

run_scraper "Watsons" \
    "$COSMETICS_DIR/Watsons/watsons_scraper.py" \
    "$COSMETICS_DIR/Watsons"

# =============================================
# GROUP 13 SERVICES, JEWELLERY & DAYCARE SCRAPERS
# =============================================
echo ""
echo "--- Group 13 Services, Jewellery & Daycare Scrapers ---"
python3 -u "$BASE/InflationItems/Codes/13_Personal_Care/PersonalCareServices/run_all_group13_scrapers.py" --services-only 2>&1 || true

# =============================================
# INFLATION CALCULATION
# =============================================
echo ""
echo "--- Cosmetics Inflation Calculation ---"
python3 "$BASE/Inflations/Codes/13_Personal_Care/Cosmetics/cosmetics_inflation.py" --date "$DATE" 2>&1 || true

echo ""
echo "--- TÜİK Group 13 Unified Inflation Calculation ---"
python3 "$BASE/Inflations/Codes/13_Personal_Care/PersonalCareServices/group13_inflation.py" --date "$DATE" 2>&1 || true

# =============================================
# GIT PUSH
# =============================================
echo ""
echo "--- Git push ---"
cd "$BASE"
git add InflationItems/Datas/13_Personal_Care/ \
        Inflations/Datas/13_Personal_Care/ 2>/dev/null || true

if git diff --cached --quiet; then
    echo "No new data to commit. Skipping push."
else
    git commit -m "daily group 13 scrape and inflation $DATE"
    git push origin master 2>&1 || git push
    echo "Git push: ✓ SUCCESS"
fi

# =============================================
# DATA RETENTION CLEANUP (Keep max 2 days on server)
# =============================================
echo ""
echo "--- Data Retention Cleanup (Purging files older than 2 days) ---"
DATAS_COSMETICS="$BASE/InflationItems/Datas/13_Personal_Care/Cosmetics"

# Remove CSV data files older than 2 days (48 hours)
if [ -d "$DATAS_COSMETICS" ]; then
    find "$DATAS_COSMETICS" -type f -name "*.csv" -mtime +2 -exec rm -f {} +
    echo "[Cleanup] Purged CSV files older than 2 days from server."
fi

# Remove log files older than 2 days (48 hours)
if [ -d "$LOG_DIR" ]; then
    find "$LOG_DIR" -type f -name "*.log" -mtime +2 -exec rm -f {} +
    echo "[Cleanup] Purged log files older than 2 days from server."
fi

echo ""
echo "========================================"
echo "  Finished: $DATE"
echo "========================================"
