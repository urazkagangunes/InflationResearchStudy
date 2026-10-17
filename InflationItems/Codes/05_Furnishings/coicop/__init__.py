"""TÜİK 2026 CPI basket codes for scraped products.

codes(name, category, store) returns (category_number, sub_category_number):
the 7-digit basket item code and its 2-digit main group, or ("0", "0") when
the basket has no matching item.

Rules live in rules.py as (code, name regex, category regex, unless regex,
stores, note). Regexes run on normalize()d text and match from the start of a
word. A rule matches when its name and category regexes (those given) match
and its unless regex does not match the name (the category, for a rule that
has no name regex). The first matching rule wins, so specific phrases come
before general ones; rules with code 0 stop the search for product types the
basket has no item for.
"""

import csv
import html
import os
import re
import threading
import unicodedata
from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).resolve().parent
_FOLD = str.maketrans("çğıöşüâîû", "cgiosuaiu")

NO_MATCH = ("0", "0")


def normalize(text):
    text = html.unescape(str(text or ""))
    text = text.replace("İ", "i").replace("I", "ı").lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.translate(_FOLD)
    text = re.sub(r"[^a-z0-9%]+", " ", text)
    return " " + text.strip() + " "


def _load_basket():
    with open(_DIR / "basket_2026.csv", encoding="utf-8", newline="") as fh:
        return {row["code"]: row["name"] for row in csv.DictReader(fh)}


BASKET = _load_basket()


def _compile(pattern):
    # Every alternative starts at a word: "mandal" must not match "kumandalı".
    # Patterns anchored with ^ (lookahead tests on the whole name) are left as they are.
    if not pattern:
        return None
    return re.compile(pattern if pattern.startswith("^") else r"\b(?:" + pattern + ")")


def _load_rules():
    from .rules import RULES as raw

    rules = []
    for number, (code, name_re, cat_re, unless_re, stores, note) in enumerate(raw, 1):
        if code != "0" and code not in BASKET:
            raise ValueError(f"rule {number} ({note}): {code} is not in the 2026 basket")
        if not name_re and not cat_re:
            raise ValueError(f"rule {number} ({note}): needs a name or category regex")
        rules.append((
            code,
            _compile(name_re),
            _compile(cat_re),
            _compile(unless_re),
            frozenset(s.strip() for s in stores.split(",") if s.strip()),
            number,
        ))
    return rules


RULES = _load_rules()


@lru_cache(maxsize=None)
def match(name, category="", store=""):
    """Return (code, rule number) of the first matching rule, or ("0", 0)."""
    n, c = normalize(name), normalize(category)
    for code, name_re, cat_re, unless_re, stores, lineno in RULES:
        if stores and store not in stores:
            continue
        if name_re and not name_re.search(n):
            continue
        if cat_re and not cat_re.search(c):
            continue
        if unless_re and unless_re.search(n if name_re else c):
            continue
        return code, lineno
    return "0", 0


_audit_lock = threading.Lock()


def _audit(store, category, name, code, lineno):
    # Set COICOP_AUDIT to a folder to keep the inputs of every call, so the
    # rules can be re-checked against a fresh scrape.
    folder = os.environ.get("COICOP_AUDIT")
    if not folder:
        return
    safe = re.sub(r"[^A-Za-z0-9]+", "_", store) or "store"
    with _audit_lock, open(Path(folder) / f"audit_{safe}.tsv", "a", encoding="utf-8", newline="") as fh:
        csv.writer(fh, delimiter="\t").writerow([store, category, name, code, lineno])


def codes(name, category="", store=""):
    code, lineno = match(str(name or ""), str(category or ""), str(store or ""))
    _audit(store, category, name, code, lineno)
    return NO_MATCH if code == "0" else (code[:2], code)


FIELDS = ["product_name", "price", "category_number", "sub_category_number"]


def row(name, price, category="", store=""):
    """One CSV row in FIELDS order; category is the site category the product was listed under."""
    return [name, price, *codes(name, category, store)]
