#!/bin/bash
# run_cosmetics.sh — Tüm kozmetik scraperlarını çalıştırır
# Cron: 0 2 * * * /path/to/run_cosmetics.sh >> /path/to/logs/cron_cosmetics.log 2>&1

BASE="$(cd "$(dirname "$0")" && pwd)"
COSMETICS_DIR="$BASE/InflationItems/Codes/Cosmetics"
DATE=$(date +%Y-%m-%d)
LOG_DIR="$BASE/logs/cosmetics"
mkdir -p "$LOG_DIR"

echo ""
echo "========================================"
echo "  Kozmetik Scrape: $DATE"
echo "========================================"

# Python ortamı — venv varsa aktif et
if [ -f "$BASE/.venv/bin/activate" ]; then
    source "$BASE/.venv/bin/activate"
    echo "[venv] Aktif edildi."
fi

# --- Scraper çalıştırma fonksiyonu ---
run_scraper() {
    local name="$1"
    local script="$2"
    local workdir="$3"
    local log="$LOG_DIR/${name}_${DATE}.log"

    echo ""
    echo "--- $name başlıyor ---"
    if [ ! -f "$script" ]; then
        echo "[$name] ATLANILDI — script bulunamadı: $script"
        return
    fi

    pushd "$workdir" > /dev/null
    timeout 7200 python3 -u "$script" > "$log" 2>&1
    local exit_code=$?
    popd > /dev/null

    if [ $exit_code -eq 124 ]; then
        echo "[$name] ⏱ TIMEOUT (2 saat aşıldı) — log: $log"
    elif [ $exit_code -eq 0 ]; then
        echo "[$name] ✓ TAMAM"
    else
        echo "[$name] ✗ HATA (exit: $exit_code) — log: $log"
        tail -5 "$log" | sed 's/^/    /'
    fi
}

# =============================================
# SCRAPERLAR
# =============================================

run_scraper "Avon" \
    "$COSMETICS_DIR/Avon/avon.py" \
    "$COSMETICS_DIR/Avon"

run_scraper "BeymenBeauty" \
    "$COSMETICS_DIR/Beymen Beauty/cosmetic.py" \
    "$COSMETICS_DIR/Beymen Beauty"

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
    "$COSMETICS_DIR/Watsons/scraper.py" \
    "$COSMETICS_DIR/Watsons"

# =============================================
# GIT PUSH
# =============================================
echo ""
echo "--- Git push ---"
cd "$BASE"
git add InflationItems/Datas/Cosmetics/ 2>/dev/null || true

if git diff --cached --quiet; then
    echo "Yeni veri yok, push atlanıyor."
else
    git commit -m "daily cosmetics scrape $DATE"
    git push
    echo "Git push: ✓ TAMAM"
fi

echo ""
echo "========================================"
echo "  Bitti: $DATE"
echo "========================================"
