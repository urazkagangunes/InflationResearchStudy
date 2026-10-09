from pathlib import Path
import os
import sys
import subprocess
import pandas as pd
import time
from datetime import datetime

# ── CONFIGURATION ────────────────────────────────────────────────────────────
SCRIPTS_TO_RUN = [
    "boyner_scraper1.py",
    "boyner_scraper2.py",
    "boyner_scraper3.py",
    "boyner_scraper4.py"
]

PART_IDENTIFIERS = ["part1", "part2", "part3", "part4"]


# ─────────────────────────────────────────────────────────────────────────────

def run_sequential_scrapers():
    current_dir = os.path.dirname(os.path.abspath(__file__))

    print("\n🚀 STARTING SEQUENTIAL EXECUTION...")
    print("=" * 50)

    for index, script_name in enumerate(SCRIPTS_TO_RUN):
        script_path = os.path.join(current_dir, script_name)

        if not os.path.exists(script_path):
            print(f"  ❌ ERROR: Could not find {script_name} in {current_dir}")
            continue

        print(f"\n  ▶️ [{index + 1}/{len(SCRIPTS_TO_RUN)}] Running {script_name}...")
        start_time = time.time()

        # Sıralı çalıştır — bitene kadar bekle
        result = subprocess.run([sys.executable, script_path])

        elapsed = time.time() - start_time
        if result.returncode == 0:
            print(f"  ✅ {script_name} tamamlandı ({elapsed:.0f}s)")
        else:
            print(f"  ❌ {script_name} HATA ile bitti (exit: {result.returncode}, {elapsed:.0f}s)")

    print("\n✅ Tüm scraperlar sırayla tamamlandı!")


def merge_csv_files():
    print("\n🧩 INITIATING DATA MERGE...")
    print("=" * 50)

    current_dir = Path(__file__).resolve()
    root_dir = next((p for p in current_dir.parents if (p / ".git").exists()), current_dir.parents[5])
    data_dir = os.path.join(root_dir, "InflationItems", "Datas", "13_Personal_Care", "Cosmetics", "Boyner")

    date_str = datetime.now().strftime("%Y-%m-%d")
    all_dataframes = []

    # 1. Gather all the part files
    for part in PART_IDENTIFIERS:
        part_filename = f"boyner_{part}_{date_str}.csv"
        part_filepath = os.path.join(data_dir, part_filename)

        if os.path.exists(part_filepath):
            print(f"  📄 Found {part_filename}...")
            df = pd.read_csv(part_filepath)
            all_dataframes.append(df)

            # Clean up temporary file
            os.remove(part_filepath)
            print(f"     🗑️ Deleted temporary file {part_filename}")
        else:
            print(f"  ⚠️ Warning: Could not find {part_filename}.")

    # 2. Merge and Save
    if all_dataframes:
        print("\n  ⚙️ Merging all data together...")

        master_df = pd.concat(all_dataframes, ignore_index=True)

        initial_count = len(master_df)
        master_df.drop_duplicates(subset=["Product Name", "Category"], inplace=True)
        duplicates_removed = initial_count - len(master_df)

        if duplicates_removed > 0:
            print(f"  ✂️ Removed {duplicates_removed} overlapping duplicate products.")

        final_filename = f"boyner_{date_str}.csv"
        final_filepath = os.path.join(data_dir, final_filename)

        master_df.to_csv(final_filepath, index=False, encoding="utf-8-sig")

        print(f"\n🏆 SUCCESS! Master file created.")
        print(f"📊 Total Unique Products: {len(master_df)}")
        print(f"📁 Location: {final_filepath}")

    else:
        print("\n❌ MERGE FAILED: No partial CSV files were found to merge.")


if __name__ == "__main__":
    run_sequential_scrapers()
    merge_csv_files()