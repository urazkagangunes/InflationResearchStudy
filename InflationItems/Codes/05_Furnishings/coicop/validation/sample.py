"""Draws the stratified validation sample from an audit run.

Strata are the codes the rules assign: every non-zero code is one stratum,
and the products that get 0 form one stratum per store, because missed
products hide there. Each stratum contributes up to --per-code or
--per-store-zero products; the stratum size is kept so validate.py can weight
the results back to the whole catalogue.

    python sample.py <audit dir> <out.csv> [--seed 20261017]

The audit dir holds the audit_*.tsv files written by a scrape run with
COICOP_AUDIT set. The sample carries no codes, so it can be labelled blind.
With --scale, large strata get one product per --scale products, up to --cap;
--exclude leaves out the products of an earlier sample, so a second round is
measured on products the rules were not corrected against.
"""

import argparse
import csv
import glob
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import coicop  # noqa: E402


def load_products(audit_dir):
    seen, products = set(), []
    for path in sorted(glob.glob(str(Path(audit_dir) / "audit_*.tsv"))):
        with open(path, encoding="utf-8", newline="") as fh:
            for store, category, name, *_ in csv.reader(fh, delimiter="\t"):
                if (store, category, name) not in seen:
                    seen.add((store, category, name))
                    products.append((store, category, name))
    return products


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("audit_dir")
    parser.add_argument("out")
    parser.add_argument("--seed", type=int, default=20261017)
    parser.add_argument("--per-code", type=int, default=10)
    parser.add_argument("--per-store-zero", type=int, default=15)
    parser.add_argument("--scale", type=int, default=0)
    parser.add_argument("--cap", type=int, default=40)
    parser.add_argument("--exclude")
    args = parser.parse_args()

    excluded = set()
    if args.exclude:
        with open(args.exclude, encoding="utf-8", newline="") as fh:
            excluded = {(r["store"], r["site_category"], r["product_name"]) for r in csv.DictReader(fh)}

    strata = defaultdict(list)
    for store, category, name in load_products(args.audit_dir):
        code, _ = coicop.match(name, category, store)
        strata[f"zero:{store}" if code == "0" else f"code:{code}"].append((store, category, name))

    rng = random.Random(args.seed)
    rows = []
    for stratum in sorted(strata):
        members = sorted(strata[stratum])
        size = args.per_store_zero if stratum.startswith("zero:") else args.per_code
        if args.scale:
            size = min(max(size, math.ceil(len(members) / args.scale)), max(size, args.cap))
        # The stratum size stays the full count: excluded products still stand for the catalogue.
        pool = [m for m in members if m not in excluded]
        for store, category, name in rng.sample(pool, min(size, len(pool))):
            rows.append([stratum, len(members), store, category, name])
    rng.shuffle(rows)

    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["id", "stratum", "stratum_size", "store", "site_category", "product_name"])
        writer.writerows([i, *row] for i, row in enumerate(rows, 1))
    print(f"{len(rows)} products from {len(strata)} strata -> {args.out}")


if __name__ == "__main__":
    main()
