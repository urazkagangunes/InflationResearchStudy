import csv
import os
import queue
import random
import re
import threading
import time
from datetime import datetime
from typing import List, Set, Tuple

import requests
from bs4 import BeautifulSoup, Tag

BASE_URL = "https://www.afyonsoz.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}

NUM_WORKERS   = 4    # paralel thread sayısı
PAGE_DELAY    = 0.3  # aynı path içinde sayfalar arası bekleme (sn)
MAX_RETRIES   = 4
TIMEOUT       = 45

PATH_RE        = re.compile(r"/hesabim\?path=(\d+)")
PRICE_RE       = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2})\s*TL", re.IGNORECASE)
TOTAL_PAGES_RE = re.compile(r"\((\d+)\s*Sayfa\)", re.IGNORECASE)
NON_PRODUCT_TITLES = {"alt kategoriler", "kategoriler"}


# ── helpers ──────────────────────────────────────────────────────────────────

def repo_root() -> str:
    return os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def category_url(path_id: int, page: int = 1) -> str:
    if page == 1:
        return f"{BASE_URL}/hesabim?path={path_id}"
    return f"{BASE_URL}/hesabim?page={page}&path={path_id}"


def fetch(session: requests.Session, url: str) -> BeautifulSoup:
    """GET url with exponential-backoff retry. Raises on permanent failure."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = session.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            return BeautifulSoup(r.text, "html.parser")
        except Exception as exc:
            if attempt == MAX_RETRIES:
                raise
            wait = (2 ** attempt) * 3 + random.uniform(0, 2)  # 6s, 14s, 30s
            print(f"  !! Attempt {attempt} failed ({exc}) — retry in {wait:.0f}s")
            time.sleep(wait)


def extract_total_pages(soup: BeautifulSoup) -> int:
    m = TOTAL_PAGES_RE.search(" ".join(soup.stripped_strings))
    if m:
        try:
            return max(1, int(m.group(1)))
        except ValueError:
            pass
    return 1


def discover_paths(soup: BeautifulSoup) -> Set[int]:
    paths: Set[int] = set()
    for a in soup.find_all("a", href=True):
        m = PATH_RE.search(a["href"])
        if m:
            try:
                paths.add(int(m.group(1)))
            except ValueError:
                pass
    return paths


def parse_products(soup: BeautifulSoup) -> List[Tuple[str, str]]:
    results: List[Tuple[str, str]] = []
    seen: Set[Tuple[str, str]] = set()
    for h in soup.find_all(["h4", "h3"]):
        if not isinstance(h, Tag):
            continue
        name = h.get_text(strip=True)
        if not name or len(name) < 2 or name.strip().lower() in NON_PRODUCT_TITLES:
            continue
        container = h.find_parent()
        if not isinstance(container, Tag):
            continue
        pm = PRICE_RE.search(" ".join(container.stripped_strings))
        if not pm:
            continue
        price = pm.group(1).replace(".", "").strip()
        key = (name, price)
        if key not in seen:
            seen.add(key)
            results.append(key)
    return results


def scrape_path(session: requests.Session, path_id: int) -> Tuple[List[Tuple[str, str]], Set[int]]:
    first = fetch(session, category_url(path_id, 1))
    pages = extract_total_pages(first)
    found_paths = discover_paths(first)
    products = parse_products(first)

    for page in range(2, pages + 1):
        time.sleep(PAGE_DELAY + random.uniform(0, 0.2))
        soup = fetch(session, category_url(path_id, page))
        found_paths |= discover_paths(soup)
        products.extend(parse_products(soup))

    return products, found_paths


# ── threading ────────────────────────────────────────────────────────────────

def worker(
    path_queue: "queue.Queue[int]",
    visited: Set[int],
    visited_lock: threading.Lock,
    results: List[Tuple[str, str]],
    results_lock: threading.Lock,
    global_seen: Set[Tuple[str, str]],
) -> None:
    session = make_session()
    while True:
        try:
            path_id = path_queue.get(timeout=8)
        except queue.Empty:
            break

        with visited_lock:
            if path_id in visited:
                path_queue.task_done()
                continue
            visited.add(path_id)

        print(f"Scraping path={path_id} ...")
        try:
            products, discovered = scrape_path(session, path_id)
        except Exception as exc:
            print(f"  !! Permanently failed path={path_id}: {exc}")
            path_queue.task_done()
            continue

        print(f"  -> {len(products)} items  (path={path_id})")

        # yeni path'leri kuyruğa ekle
        with visited_lock:
            for p in discovered:
                if p not in visited:
                    path_queue.put(p)

        # sonuçları kaydet
        with results_lock:
            for name, price in products:
                key = (name, price)
                if key not in global_seen:
                    global_seen.add(key)
                    results.append(key)

        path_queue.task_done()


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    # seed paths
    print("Ana sayfa taranıyor...")
    seed_session = make_session()
    home_soup = fetch(seed_session, BASE_URL + "/")
    seeds = discover_paths(home_soup)
    print(f"Seed paths from homepage: {len(seeds)}")

    path_queue: "queue.Queue[int]" = queue.Queue()
    for p in sorted(seeds):
        path_queue.put(p)

    visited: Set[int] = set()
    visited_lock = threading.Lock()
    results: List[Tuple[str, str]] = []
    results_lock = threading.Lock()
    global_seen: Set[Tuple[str, str]] = set()

    threads = [
        threading.Thread(
            target=worker,
            args=(path_queue, visited, visited_lock, results, results_lock, global_seen),
            daemon=True,
        )
        for _ in range(NUM_WORKERS)
    ]
    for t in threads:
        t.start()

    try:
        path_queue.join()  # tüm task_done() çağrılana kadar bekle
    except KeyboardInterrupt:
        print("\nDurduruldu — o ana kadar toplanan veriler kaydediliyor...")

    # CSV kaydet
    out_dir = os.path.join(repo_root(), "Datas", "Markets", "SozSanal")
    os.makedirs(out_dir, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    out_path = os.path.join(out_dir, f"soz_{today}.csv")

    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["ID", "Product Name", "Price"])
        for i, (name, price) in enumerate(results, 1):
            w.writerow([i, name, price])

    print(f"\nDone. Visited paths: {len(visited)}")
    print(f"Done. Unique products written: {len(results)} -> {out_path}")

    # zero-price check
    zero_like = {"0", "0,0", "0,00"}
    zeros = sum(1 for _, price in results if price in zero_like)
    ratio = zeros / len(results) if results else 0.0
    print(f"Zero-price rows: {zeros}")
    print(f"Zero-price ratio: {ratio:.6f} ({zeros}/{len(results)})")


if __name__ == "__main__":
    main()
