#!/bin/bash
# run_all.sh — Eren'in 4 scraper'ını çalıştırır, sonra git push yapar.
# Cron: 0 3 * * * /home/eren/eren/run_all.sh >> /home/eren/eren/logs/cron.log 2>&1

BASE=/home/eren/eren
DATE=$(date +%Y-%m-%d)
LOG_DIR=$BASE/logs
mkdir -p "$LOG_DIR"

echo ""
echo "========================================"
echo " Daily scrape: $DATE"
echo "========================================"

# En son kodu çek
cd "$BASE" || exit 1
git pull

# Xvfb başlat (sahibinden headless engeline karşı sanal ekran)
if ! pgrep -x "Xvfb" > /dev/null; then
    echo "[Xvfb] Başlatılıyor..."
    Xvfb :99 -screen 0 1400x900x24 &
    sleep 3
else
    echo "[Xvfb] Zaten çalışıyor."
fi
export DISPLAY=:99

# Scraper çalıştırma fonksiyonu
run_scraper() {
    local name=$1
    local script=$2
    local log="$LOG_DIR/${name}_${DATE}.log"
    echo ""
    echo "--- $name başlıyor ---"
    python3 "$script" > "$log" 2>&1
    if [ $? -eq 0 ]; then
        echo "[$name] TAMAM"
    else
        echo "[$name] HATA — log: $log"
    fi
}

# 4 scraper
run_scraper "loft"        "$BASE/InflationItems/Codes/ClothingStores/Loft/loftscraper.py"
run_scraper "sahibinden"  "$BASE/InflationItems/Codes/HousesRent/Duzce_Kocaeli_Sakarya/scrape_duzce_kocaeli_sakarya.py"
run_scraper "soz"         "$BASE/InflationItems/Codes/Markets/SozSanal/soz_scraper.py"
run_scraper "nalburcuk"   "$BASE/InflationItems/Codes/ConstructionSuppliesMarkets/Nalburcuk/nalburcuk_scraper.py"

# Yeni CSV'leri git'e ekle ve push et
echo ""
echo "--- Git push ---"
cd "$BASE"
git add InflationItems/Datas/ 2>/dev/null || true
git add Datas/ 2>/dev/null || true

if git diff --cached --quiet; then
    echo "Yeni veri yok, push atlanıyor."
else
    git commit -m "daily scrape $DATE"
    git push
    echo "Git push: TAMAM"
fi

echo ""
echo "========================================"
echo " Bitti: $DATE"
echo "========================================"
