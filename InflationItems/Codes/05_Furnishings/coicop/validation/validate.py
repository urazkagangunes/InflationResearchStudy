"""Measures the rules against the hand-checked validation sample.

    python validate.py gold.csv [--boot 2000]

gold.csv is sample.py's output with a gold_code column (7-digit code or 0).
Each product is weighted by stratum size / products drawn from the stratum,
so the figures estimate the whole catalogue of the audit run, not the
sample. 95% intervals come from a bootstrap within strata.

Reported:
  accuracy      products whose code equals the gold code
  false match   products given a code that is not their gold code
                (wrong item, or a code where the gold is 0), among coded products
  missed        products with a gold code that were given 0, among products
                with a gold code
  group         first two digits right (0 counts as its own group)
"""

import argparse
import csv
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import coicop  # noqa: E402

CONSTRUCTION = set(
    "AfeksYapiMarket Bauhaus Ereyon FiltasYapi HanCivata Hausmart Koctas LoyaMakina "
    "Nalburadam Nalburcuk Nalburtek SanatYapiOnline TasciYapiMarket Yapıyoz yapimaks".split()
)


def group(code):
    return "0" if code == "0" else code[:2]


def metrics(items):
    tot = coded = coded_ok = gold_coded = missed = ok = group_ok = 0.0
    for it in items:
        w, pred, gold = it["w"], it["pred"], it["gold"]
        tot += w
        ok += w * (pred == gold)
        group_ok += w * (group(pred) == group(gold))
        if pred != "0":
            coded += w
            coded_ok += w * (pred == gold)
        if gold != "0":
            gold_coded += w
            missed += w * (pred == "0")
    return {
        "accuracy": ok / tot if tot else float("nan"),
        "false match": 1 - coded_ok / coded if coded else float("nan"),
        "missed": missed / gold_coded if gold_coded else float("nan"),
        "group": group_ok / tot if tot else float("nan"),
        "zero share (rules)": 1 - coded / tot if tot else float("nan"),
        "zero share (gold)": 1 - gold_coded / tot if tot else float("nan"),
    }


def bootstrap(items, reps, seed=1):
    by_stratum = defaultdict(list)
    for it in items:
        by_stratum[it["stratum"]].append(it)
    rng = random.Random(seed)
    draws = defaultdict(list)
    for _ in range(reps):
        sample = []
        for members in by_stratum.values():
            sample.extend(rng.choice(members) for _ in members)
        for key, value in metrics(sample).items():
            draws[key].append(value)
    return {k: (sorted(v)[int(0.025 * reps)], sorted(v)[int(0.975 * reps) - 1]) for k, v in draws.items()}


def report(title, items, reps):
    point, ci = metrics(items), bootstrap(items, reps)
    weight = sum(it["w"] for it in items)
    print(f"\n{title}: {len(items)} checked, standing for {weight:,.0f} products")
    for key, value in point.items():
        low, high = ci[key]
        print(f"  {key:20s} {value:6.1%}   (95%: {low:.1%} - {high:.1%})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("gold")
    parser.add_argument("--boot", type=int, default=2000)
    args = parser.parse_args()

    items = []
    with open(args.gold, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            pred, _ = coicop.match(row["product_name"], row["site_category"], row["store"])
            items.append({
                **row,
                "pred": pred,
                "gold": row["gold_code"].strip().zfill(7) if row["gold_code"].strip() != "0" else "0",
            })
    drawn = defaultdict(int)
    for it in items:
        drawn[it["stratum"]] += 1
    for it in items:
        it["w"] = int(it["stratum_size"]) / drawn[it["stratum"]]
    unknown = sorted({it["gold"] for it in items} - set(coicop.BASKET) - {"0"})
    if unknown:
        sys.exit(f"gold codes not in the basket: {unknown}")

    report("All stores", items, args.boot)
    report("HomeGoods", [it for it in items if it["store"] not in CONSTRUCTION], args.boot)
    report("ConstructionSuppliesMarkets", [it for it in items if it["store"] in CONSTRUCTION], args.boot)

    wrong = [it for it in items if it["pred"] != it["gold"]]
    print(f"\n{len(wrong)} of {len(items)} checked products disagree with the gold code:")
    for it in sorted(wrong, key=lambda it: (it["gold"], it["pred"])):
        print(f"  gold {it['gold']:7s} rules {it['pred']:7s} {it['store']:15s} {it['product_name'][:80]}")


if __name__ == "__main__":
    main()
