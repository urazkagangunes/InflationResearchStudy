"""
run_all_group13_scrapers.py — Unified Runner for TÜİK Group 13 (Personal Care, Social Protection & Services)

Executes all scrapers that comprise TÜİK COICOP Group 13:
  1. Cosmetics & Personal Care (14 retailers: Dermomarket, Watsons, Rossmann, etc.)
  2. Gold & Jewellery (Harem Altın / Live Gold Market) [1321101]
  3. Watches (Saat & Saat) [1321105]
  4. Hairdresser & Barber Services (Kolay Randevu + Chamber Tariffs) [1313]
  5. Notary Fees (Resmi Gazete TNB Statutory Tariffs) [1390901]
  6. Legal Services (TBB Official Minimum Attorney Tariff) [1390903]
  7. Vehicle Inspection & Expertise (Pilot Garage) [1390902]
  8. Daycare & Childcare Services (Daycare & Nursery Tuition) [1330101]

Usage:
  python run_all_group13_scrapers.py                   # Run all scrapers
  python run_all_group13_scrapers.py --services-only  # Run only services & jewelry (skip cosmetics)
  python run_all_group13_scrapers.py --date YYYY-MM-DD
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("Group13Runner")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = next((p for p in BASE_DIR.parents if (p / ".git").exists()), BASE_DIR.parents[3])

# Paths to service and jewelry scrapers
SERVICES_SCRAPERS = [
    # 1. Jewellery & Watches (1321)
    ("Gold & Jewellery Market (1321101)", PROJECT_ROOT / "InflationItems/Codes/13_Personal_Care/Jewelry/Gold/gold_scraper.py"),
    ("Altınbaş Retail Jewellery (1321101)", PROJECT_ROOT / "InflationItems/Codes/13_Personal_Care/Jewelry/Altinbas/altinbas_scraper.py"),
    ("Watches - Saat & Saat (1321105)", PROJECT_ROOT / "InflationItems/Codes/13_Personal_Care/Jewelry/SaatVeSaat/saatvesaat_scraper.py"),

    # 2. Hairdresser & Barber Services (1313)
    ("Hairdresser - Kolay Randevu (1313)", PROJECT_ROOT / "InflationItems/Codes/13_Personal_Care/Hairdresser/KolayRandevu/kolayrandevu_scraper.py"),
    ("Barber Chambers Official Tariff (1313)", PROJECT_ROOT / "InflationItems/Codes/13_Personal_Care/Hairdresser/BerberlerOdasi/berberler_odasi_scraper.py"),
    ("Hairdresser Chambers Official Tariff (1313)", PROJECT_ROOT / "InflationItems/Codes/13_Personal_Care/Hairdresser/KuaforlerOdasi/kuaforler_odasi_scraper.py"),

    # 3. Notary Services (1390901)
    ("Notary Fee Tariff (1390901)", PROJECT_ROOT / "InflationItems/Codes/13_Personal_Care/Services/Notary/notary_tariff_scraper.py"),
    ("Notary Vehicle Transfer Fees (1390901)", PROJECT_ROOT / "InflationItems/Codes/13_Personal_Care/Services/NotaryVehicle/notary_vehicle_transfer_scraper.py"),
    ("Notary Real Estate Tariffs (1390901)", PROJECT_ROOT / "InflationItems/Codes/13_Personal_Care/Services/NotaryRealEstate/notary_realestate_scraper.py"),

    # 4. Legal Services (1390903)
    ("Legal - TBB Official Tariff (1390903)", PROJECT_ROOT / "InflationItems/Codes/13_Personal_Care/Services/Legal/legal_tariff_scraper.py"),
    ("Legal - Istanbul Bar Advisory (1390903)", PROJECT_ROOT / "InflationItems/Codes/13_Personal_Care/Services/IstanbulBarosu/istanbul_barosu_scraper.py"),
    ("Legal - Mediation Official Tariff (1390903)", PROJECT_ROOT / "InflationItems/Codes/13_Personal_Care/Services/Mediation/mediation_tariff_scraper.py"),

    # 5. Vehicle Inspection & Appraisal (1390902)
    ("Appraisal - Pilot Garage (1390902)", PROJECT_ROOT / "InflationItems/Codes/13_Personal_Care/Services/AutoExpertise/pilotgarage_scraper.py"),
    ("Inspection - TÜVTÜRK Official (1390902)", PROJECT_ROOT / "InflationItems/Codes/13_Personal_Care/Services/Tuvturk/tuvturk_scraper.py"),
    ("Appraisal - Dynobil Network (1390902)", PROJECT_ROOT / "InflationItems/Codes/13_Personal_Care/Services/Dynobil/dynobil_scraper.py"),

    # 6. Childcare & Daycare Services (1330101)
    ("Daycare - Metropolitan Index (1330101)", PROJECT_ROOT / "InflationItems/Codes/13_Personal_Care/Daycare/Daycare/daycare_scraper.py"),
    ("Daycare - Regional Preschools (1330101)", PROJECT_ROOT / "InflationItems/Codes/13_Personal_Care/Daycare/KreslerCom/kresler_com_scraper.py"),
    ("Daycare - Infant & Toddler Care (1330101)", PROJECT_ROOT / "InflationItems/Codes/13_Personal_Care/Daycare/ChildcareServices/childcare_services_scraper.py"),
]

# Cosmetics scrapers runner
COSMETICS_RUNNER = PROJECT_ROOT / "InflationItems/Codes/13_Personal_Care/Cosmetics/run_all_cosmetics.py"


def run_script(name: str, script_path: Path, extra_args: list[str] | None = None) -> bool:
    """Executes a single scraper script via subprocess and logs output."""
    if not script_path.exists():
        logger.error("[%s] Script not found: %s", name, script_path)
        return False

    cmd = [sys.executable, str(script_path)]
    if extra_args:
        cmd.extend(extra_args)

    logger.info("==================================================")
    logger.info("STARTING: %s", name)
    start_time = time.time()

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=True
        )
        elapsed = time.time() - start_time
        logger.info("[%s] Completed successfully in %.1f seconds.", name, elapsed)
        # Print last few lines of output
        lines = proc.stdout.strip().splitlines()
        for line in lines[-5:]:
            logger.info("   | %s", line)
        return True
    except subprocess.CalledProcessError as err:
        elapsed = time.time() - start_time
        logger.error("[%s] Failed with exit code %d after %.1f seconds.", name, err.returncode, elapsed)
        if err.stdout:
            for line in err.stdout.strip().splitlines()[-10:]:
                logger.error("   | %s", line)
        return False


def main():
    parser = argparse.ArgumentParser(description="Unified Group 13 Scrapers Runner")
    parser.add_argument("--services-only", action="store_true", help="Run only services, gold and watches (skip cosmetics)")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    args = parser.parse_args()

    date_str = args.date or datetime.today().strftime("%Y-%m-%d")
    logger.info("==================================================")
    logger.info("GROUP 13 UNIFIED SCRAPER RUNNER — DATE: %s", date_str)
    logger.info("==================================================")

    total_start = time.time()
    results = {}

    # 1. Run Cosmetics if not excluded
    if not args.services_only and COSMETICS_RUNNER.exists():
        ok = run_script("Cosmetics (14 Retailers)", COSMETICS_RUNNER)
        results["Cosmetics"] = ok

    # 2. Run All Group 13 Services, Gold & Watches
    for label, script_path in SERVICES_SCRAPERS:
        extra = []
        if args.date:
            extra = ["--date", args.date]
        ok = run_script(label, script_path, extra)
        results[label] = ok

    # Summary
    logger.info("==================================================")
    logger.info("EXECUTION SUMMARY:")
    all_passed = True
    for name, success in results.items():
        status = "SUCCESS" if success else "FAILED"
        if not success:
            all_passed = False
        logger.info("  %-35s : %s", name, status)

    total_elapsed = time.time() - total_start
    logger.info("Total elapsed time: %.1f seconds.", total_elapsed)
    logger.info("==================================================")

    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
