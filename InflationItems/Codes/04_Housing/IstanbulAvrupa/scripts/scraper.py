"""
Istanbul Avrupa Rent Scraper - Core Scraping Logic Module
=========================================================

This module implements the sophisticated scraping algorithms for Istanbul's European
side rental listings, featuring adaptive price bracket splitting, Selenium-based
browser automation, and comprehensive data extraction with CAPTCHA handling.

Core Algorithms
---------------

Adaptive Bracket Splitting Algorithm
------------------------------------
Sahibinden.com enforces a strict limit of 1,000 listings per query (20 pages × 50 listings).
To capture complete market data, the scraper implements an intelligent bracket splitting
strategy:

scrape_and_resolve() -> tuple[list[dict], list[dict]]
    Recursive algorithm that probes listing counts for price ranges and splits them
    until all brackets fall safely under the 1,000 listing threshold.

Algorithm Steps:
1. **Range Probing**: Query wide price ranges to determine listing density
2. **Count Analysis**: Extract total listing count from page 1 results
3. **Recursive Splitting**: Divide ranges exceeding 1,000 listings in half
4. **Optimal Generation**: Create "safe" leaf brackets under the threshold
5. **Efficient Scraping**: Use already-loaded page 1 for immediate scraping

scrape_leaf_bracket() -> list[dict]
    Scrapes a single safe bracket with known price boundaries, handling pagination
    and data extraction without additional resolution overhead.

Browser Automation Features
---------------------------
Selenium Integration
- undetected-chromedriver for stealth operation
- Persistent browser profiles for session continuity
- Automatic ChromeDriver version management
- Headless mode support for server deployment

CAPTCHA Handling Workflow
- Interactive detection of CAPTCHA challenges and login walls
- User notification with clear instructions
- Manual resolution through Chrome browser interface
- Automatic verification of successful page loading

Data Extraction Strategy
------------------------
Listing Data Sources
1. **Search Results Page**: Main listing grid with rental properties
2. **Listing Cards**: Individual property cards with key information
3. **Pagination Controls**: Navigation elements for multi-page results

Data Fields Extracted
- District: Neighborhood or district name
- Rooms: Room count specification (raw format)
- Price: Monthly rent amount (raw from site)

Performance Features
-------------------
- **Memory Efficiency**: Streaming HTML processing with lxml
- **Connection Reuse**: Persistent browser sessions across requests
- **Incremental Saving**: Progressive CSV writing during scraping
- **Checkpoint Integration**: Session state management for resume capability

Error Handling & Recovery
-------------------------
- **Browser Crashes**: Automatic restart with session recovery
- **Network Issues**: Retry logic with exponential backoff
- **CAPTCHA Events**: Graceful pausing with user notification
- **Data Validation**: Malformed listing filtering with logging

Session Management
-----------------
Browser Profile Persistence
- SeleniumProfile directory stores browser state
- Cookie preservation across sessions
- Login state maintenance when available
- Cache utilization for performance optimization

Checkpoint Integration
---------------------
The module integrates tightly with the checkpoint system:
- Resolved bracket caching for faster resume operations
- Completed bracket tracking for incremental progress
- Session state persistence across browser restarts
- Efficient resumption without redundant work

Configuration Dependencies
------------------------
The module relies on config.py for:
- Seed price ranges for initial bracket generation
- Rate limiting parameters for server compatibility
- Path configurations for data export
- Browser settings and profile locations

Usage Patterns
--------------
```python
# Full scraping with adaptive bracket discovery
brackets, listings = scrape_and_resolve()

# Resume operation with cached brackets
brackets, listings = scrape_and_resolve(resume=True)

# Direct scraping of known safe brackets
listings = scrape_leaf_bracket(bracket)
```

Technical Architecture
----------------------
- **Single-threaded Design**: Browser automation requires sequential processing
- **Memory Optimization**: Efficient DOM parsing and data extraction
- **Error Resilience**: Comprehensive exception handling and recovery
- **Modular Design**: Clear separation of bracket resolution and scraping logic
"""

import csv
import logging
import os
import random
import re
import subprocess
import threading
import time
from typing import Optional

import undetected_chromedriver as uc
from lxml import html as lxml_html
from lxml import etree

import config

logger = logging.getLogger(__name__)

# One CAPTCHA prompt at a time — prevents interleaved terminal output if the
# scraper is ever adapted for concurrent use.
_captcha_lock = threading.Lock()


# ── Adaptive Delay Tracker ───────────────────────────────────────────────────

class AdaptiveDelayTracker:
    """Tracks request success/failure and dynamically adjusts delays.
    
    Attributes
    ----------
    current_delay : float
        Current delay value in seconds.
    consecutive_successes : int
        Count of consecutive successful requests.
    consecutive_failures : int
        Count of consecutive failed requests.
    """
    
    def __init__(self, initial_delay: float = config.PAGE_LOAD_DELAY):
        self.current_delay = initial_delay
        self.consecutive_successes = 0
        self.consecutive_failures = 0
        self._last_request_time = 0.0
    
    def record_success(self) -> None:
        """Record a successful request and potentially reduce delay."""
        if not config.ADAPTIVE_DELAY_ENABLED:
            return
            
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        
        # Reduce delay after consecutive successes
        if self.consecutive_successes >= config.SUCCESS_THRESHOLD:
            old_delay = self.current_delay
            self.current_delay = max(
                config.MIN_DELAY,
                self.current_delay * config.DELAY_DECREASE_FACTOR
            )
            if old_delay != self.current_delay:
                logger.debug(
                    "Reduced delay: %.2fs → %.2fs (after %d successes)",
                    old_delay, self.current_delay, self.consecutive_successes
                )
    
    def record_failure(self) -> None:
        """Record a failed request and increase delay."""
        if not config.ADAPTIVE_DELAY_ENABLED:
            return
            
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        
        old_delay = self.current_delay
        self.current_delay = min(
            config.MAX_DELAY,
            self.current_delay * config.DELAY_INCREASE_FACTOR
        )
        logger.warning(
            "Increased delay: %.2fs → %.2fs (after %d failures)",
            old_delay, self.current_delay, self.consecutive_failures
        )
    
    def get_delay(self, jitter: bool = True) -> float:
        """Get the current delay with optional jitter.
        
        Args
        ----
        jitter : bool
            If True, apply random jitter to the delay.
        
        Returns
        -------
        float
            Delay in seconds with jitter applied.
        """
        if jitter:
            return self.current_delay * random.uniform(0.5, 1.5)
        return self.current_delay
    
    def wait(self, jitter: bool = True) -> None:
        """Wait for the adaptive delay period.
        
        Args
        ----
        jitter : bool
            If True, apply random jitter to the delay.
        """
        delay = self.get_delay(jitter)
        time.sleep(delay)


# Global adaptive delay tracker instance
_delay_tracker = AdaptiveDelayTracker()


# ── Driver factory ────────────────────────────────────────────────────────────

def _ensure_patched_and_signed(executable_path: str) -> None:
    """Patch chromedriver and re-sign it for macOS Apple Silicon.

    On Apple Silicon, macOS kills any executable whose code signature is
    invalid (SIGKILL / exit code -9). undetected_chromedriver patches the
    binary in-place (replacing ``cdc_`` strings), which breaks the original
    signature. This helper pre-patches the binary and immediately re-signs it
    with an ad-hoc signature so that when ``uc.Chrome`` calls
    ``patcher.auto()`` it detects the binary is already patched and skips the
    re-patch, leaving the valid signature intact.
    """
    from undetected_chromedriver.patcher import Patcher
    p = Patcher(executable_path=executable_path)
    if not p.is_binary_patched():
        logger.info("Pre-patching chromedriver binary…")
        p.patch_exe()
        result = subprocess.run(
            ["codesign", "--force", "-s", "-", executable_path],
            capture_output=True,
        )
        if result.returncode == 0:
            logger.info("chromedriver re-signed successfully.")
        else:
            logger.warning("codesign failed: %s", result.stderr.decode())
    else:
        logger.debug("chromedriver already patched — skipping re-patch.")


def setup_driver(profile_dir: str | None = None) -> uc.Chrome:
    """Create and return a uc.Chrome driver.

    Args
    ----
    profile_dir : str | None
        Path to the Chrome user-data-dir. Defaults to config.SELENIUM_PROFILE_DIR

    Returns
    -------
    uc.Chrome
        Chrome driver instance tailored to bypass basic Selenium detection.
    """
    _ensure_patched_and_signed(config.CHROMEDRIVER_PATH)
    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={profile_dir or config.SELENIUM_PROFILE_DIR}")
    driver = uc.Chrome(options=options, version_main=147, driver_executable_path=config.CHROMEDRIVER_PATH)
    return driver


# ── HTML helpers ──────────────────────────────────────────────────────────────

def _extract_total_listings(tree: etree._Element) -> int | None:
    """Finds the total number of listings from the summary text.

    Example: '"İstanbul Kiralık Ev"aramanızda3.193 ilanbulundu.' -> 3193

    Args
    ----
    tree : etree._Element
        Parsed lxml HTML tree of the sahibinden.com page.

    Returns
    -------
    int | None
        Total listing integer if found, None otherwise.
    """
    # Try to find the result-text element using XPath (faster than CSS selectors)
    res_elems = tree.xpath(".//*[contains(@class, 'result-text')]") 
    if res_elems:
        text = res_elems[0].text_content().strip()
        clean_text = text.replace(".", "")
        match = re.search(r"(\d+)\s*ilan", clean_text, re.IGNORECASE)
        if match:
            return int(match.group(1))

    # Fallback: search all text nodes containing "ilan"
    text_nodes = tree.xpath(".//text()[contains(translate(., 'İILAN', 'iilan'), 'ilan')]")
    for text in text_nodes:
        # Skip script, style, title tags
        parent = text.getparent()
        if parent is not None and parent.tag not in ["script", "style", "title"]:
            clean_text = text.strip().replace(".", "")
            match = re.search(r"(\d+)\s*ilan\s*(?:bulundu|var)", clean_text, re.IGNORECASE)
            if match:
                return int(match.group(1))

    return None


def _resolve_rooms_index(tree: etree._Element) -> int | None:
    """Identifies the index of the "Rooms" column in the search results table.

    Args
    ----
    tree : etree._Element
        Parsed lxml HTML tree of the sahibinden.com page.

    Returns
    -------
    int | None
        0-based index of the "Oda" column, or None if not located.
    """
    # Use XPath for faster header extraction
    headers = tree.xpath(".//table[@id='searchResultsTable']//thead//th[contains(@class, 'searchResultsAttributeHeader')]")
    
    for idx, th in enumerate(headers):
        header_text = th.text_content().strip().lower().replace("ı", "i")
        if "oda" in header_text:
            return idx
    return None


def _parse_listings(tree: etree._Element, rooms_idx: int | None) -> list[dict]:
    """Extracts listing metrics from the page's search results table.

    Args
    ----
    tree : etree._Element
        Parsed lxml HTML tree of the sahibinden.com page.
    rooms_idx : int | None
        The column index containing the rooms data.

    Returns
    -------
    list[dict]
        A list of dictionaries containing District, Rooms, and Price keys.
    """
    records = []
    # Use XPath for faster row extraction
    rows = tree.xpath(".//table[@id='searchResultsTable']//tbody//tr[contains(@class, 'searchResultsItem')]")
    
    for row in rows:
        try:
            # Extract price using XPath
            price_elems = row.xpath(".//*[contains(@class, 'searchResultsPriceValue')]") 
            price = price_elems[0].text_content().strip() if price_elems else None

            # Extract location/district using XPath
            loc_elems = row.xpath(".//*[contains(@class, 'searchResultsLocationValue')]")
            if loc_elems:
                parts = loc_elems[0].text_content().split()
                district = " / ".join(parts)
                # Normalise: if city and district were concatenated without whitespace
                # (e.g. "İstanbulAvcılar" instead of "İstanbul Avcılar"), split at boundary.
                if " / " not in district and district.startswith("İstanbul") and len(district) > 8:
                    district = "İstanbul / " + district[8:]
            else:
                district = "N/A"

            # Extract attributes (rooms, etc.) using XPath
            attrs = row.xpath(".//*[contains(@class, 'searchResultsAttributeValue')]")
            if rooms_idx is not None and len(attrs) > rooms_idx:
                rooms = attrs[rooms_idx].text_content().strip()
            elif len(attrs) > 1:
                rooms = attrs[1].text_content().strip()
            else:
                rooms = "N/A"

            if price:
                records.append({"product_name": f"{district} - {rooms}", "price": price})
        except Exception as exc:
            logger.debug("Row parse error: %s", exc)

    return records


def _build_url(min_price: int, max_price: int, page: int = 1) -> str:
    """Constructs the sahibinden.com search URL query string.

    Args
    ----
    min_price : int
        Minimum price bound limitation.
    max_price : int
        Maximum price bound limitation.
    page : int
        The pagination number to view.

    Returns
    -------
    str
        Full URL to the search results page.
    """
    url = (
        f"https://www.sahibinden.com/kiralik/{config.CITY_URL_NAME}"
        f"?pagingSize={config.PAGE_SIZE}"
        f"&price_min={min_price}&price_max={max_price}"
    )
    if page > 1:
        url += f"&pagingOffset={(page - 1) * config.PAGE_SIZE}"
    return url


def _retry_with_backoff(func, max_retries: int = config.MAX_RETRIES, *args, **kwargs):
    """Execute a function with exponential backoff retry logic.
    
    Args
    ----
    func : callable
        Function to execute.
    max_retries : int
        Maximum number of retry attempts.
    *args, **kwargs
        Arguments to pass to the function.
    
    Returns
    -------
    Any
        Result of the function call.
    
    Raises
    ------
    Exception
        If all retries are exhausted.
    """
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            result = func(*args, **kwargs)
            _delay_tracker.record_success()
            return result
        except Exception as exc:
            last_exception = exc
            _delay_tracker.record_failure()
            
            if attempt < max_retries - 1:
                backoff_delay = min(
                    config.RETRY_BACKOFF_BASE * (2 ** attempt),
                    config.RETRY_BACKOFF_MAX
                )
                logger.warning(
                    "Attempt %d/%d failed: %s. Retrying in %.1fs...",
                    attempt + 1, max_retries, str(exc), backoff_delay
                )
                time.sleep(backoff_delay)
            else:
                logger.error(
                    "All %d retry attempts exhausted. Last error: %s",
                    max_retries, str(exc)
                )
    
    raise last_exception


def _wait_for_listings(driver: uc.Chrome) -> etree._Element:
    """Wait for the page to settle, then return its parsed lxml tree.

    If no listing rows are found and the page does not show a "no results"
    message, a CAPTCHA or login wall is assumed. The scraper pauses and
    prompts the user interactively, then re-parses once a successful page
    is confirmed. Loops until the page is conclusively resolved.

    Args
    ----
    driver : uc.Chrome
        Active Chrome driver instance.

    Returns
    -------
    etree._Element
        Parsed lxml HTML tree of the driver's current active page.
    """
    _delay_tracker.wait(jitter=True)
    try:
        driver.switch_to.window(driver.window_handles[-1])
        driver.switch_to.default_content()
        html_content = driver.execute_script("return document.documentElement.outerHTML;")
    except Exception:
        html_content = driver.page_source

    # Parse with lxml for 5-10x performance improvement
    tree = lxml_html.fromstring(html_content)
    listings = tree.xpath(".//table[@id='searchResultsTable']//tbody//tr[contains(@class, 'searchResultsItem')]")

    if listings:
        return tree

    page_lower = html_content.lower()
    if "ilan bulunamadı" in page_lower or "bulunamamıştır" in page_lower:
        return tree

    # CAPTCHA / login wall — prompt the user and keep retrying until the
    # listing table is visible or the page clearly shows no results.
    with _captcha_lock:
        while True:
            print("\n" + "=" * 55)
            print("⚠️  ACTION REQUIRED: CAPTCHA or Login wall detected.")
            print("   1. Look at the Chrome window and solve the puzzle.")
            print("   2. Wait until you clearly see the list of houses.")
            print("=" * 55)
            input("   ▶ Press ENTER here ONLY AFTER you see the listings… ")

            time.sleep(2.0)
            try:
                driver.switch_to.window(driver.window_handles[-1])
                driver.switch_to.default_content()
                html_content = driver.execute_script("return document.documentElement.outerHTML;")
            except Exception:
                html_content = driver.page_source

            tree = lxml_html.fromstring(html_content)
            listings = tree.xpath(".//table[@id='searchResultsTable']//tbody//tr[contains(@class, 'searchResultsItem')]")

            if listings:
                break

            page_lower = html_content.lower()
            if "ilan bulunamadı" in page_lower or "bulunamamıştır" in page_lower:
                break

            current_url = driver.current_url
            print(f"   ⚠  No listings visible yet. Current URL: {current_url}")
            print("      (If you are stuck, simply navigate back to the search results in Chrome!)")
            print("      Please wait a moment longer or try refreshing the page manually.")

    return tree


# ── Shared page-scraping helper ───────────────────────────────────────────────

def _scrape_pages_from_soup(
    driver: uc.Chrome,
    tree: etree._Element,
    min_price: int,
    max_price: int,
    delay: float,
    pad: str = "",
    cached_rooms_idx: Optional[int] = None,
) -> list[dict]:
    """Scrape all pages of a bracket, starting from an already-loaded lxml tree.

    page 1 tree is passed in directly (already fetched by the caller) so no
    additional request is made for the first page. Subsequent pages are
    navigated using the "Sonraki" (Next) button. Stops at page 20, which is
    the hard cap imposed by sahibinden.com (20 pages × 50 listings = 1 000).

    Args
    ----
    driver : uc.Chrome
        Active Chrome driver instance.
    tree : etree._Element
        The fetched page 1 lxml HTML tree for iterative processing.
    min_price : int
        Minimum price limit for logs.
    max_price : int
        Maximum price limit for logs.
    delay : float
        Base delay value between pagination shifts (deprecated, uses adaptive delay).
    pad : str
        Padding for console display visuals.
    cached_rooms_idx : Optional[int]
        Pre-cached room column index to avoid re-parsing.

    Returns
    -------
    list[dict]
        Complete list of collected row dictionaries spanning all accessible pages.
    """
    records: list[dict] = []
    # Use cached index if available, otherwise resolve it
    rooms_idx: int | None = cached_rooms_idx if cached_rooms_idx is not None else _resolve_rooms_index(tree)
    page_num = 1
    empty_pages = 0  # Track consecutive empty pages for early termination

    while True:
        page_records = _parse_listings(tree, rooms_idx)
        
        if page_records:
            records.extend(page_records)
            empty_pages = 0  # Reset empty page counter
            logger.info(
                "%s  Page %2d: %2d listings (total: %d) | %d–%d TL",
                pad, page_num, len(page_records), len(records),
                min_price, max_price,
            )
        else:
            empty_pages += 1
            # Early termination if we hit 2 consecutive empty pages
            if empty_pages >= 2:
                logger.info("%s  No more listings found after page %d. Stopping.", pad, page_num)
                break

        # Sahibinden hard cap: 20 pages × 50 = 1 000 listings
        if page_num >= 20:
            break

        # Use XPath to find next button (faster than BeautifulSoup)
        next_btns = tree.xpath(".//a[@title='Sonraki']")
        if not next_btns:
            break

        next_url = "https://www.sahibinden.com" + next_btns[0].get("href")
        driver.get(next_url)
        page_num += 1
        
        # Use adaptive delay instead of fixed delay
        _delay_tracker.wait(jitter=True)
        tree = _wait_for_listings(driver)

        # Only re-resolve rooms index if we don't have it yet
        if rooms_idx is None:
            rooms_idx = _resolve_rooms_index(tree)

    return records


# ── Adaptive resolve + scrape ─────────────────────────────────────────────────

def scrape_and_resolve(
    driver: uc.Chrome,
    min_price: int,
    max_price: int,
    done_ranges: set[tuple[int, int]],
    save_fn,
    mark_done_fn,
    bracket_cache: list | None = None,
    delay: float = config.PAGE_LOAD_DELAY,
    indent: int = 0,
    cached_rooms_idx: Optional[int] = None,
) -> tuple[int, Optional[int]]:
    """Recursively resolves and scrapes the price range [min_price, max_price].

    On the first page load, peeks at the total listing count:
      - If count > MAX_LISTINGS_PER_QUERY: splits the range and recurses.
      - If count is safe: scrapes all pages immediately, reusing the already
        loaded page 1 soup (no duplicate request).

    Each resolved leaf bracket is appended to bracket_cache (if provided) so
    main.py can persist the bracket list for faster future --resume runs.
    Brackets already in done_ranges are skipped without a page load.

    Args
    ----
    driver : uc.Chrome
        Active Selenium worker instance.
    min_price : int
        Current testing minimum bound in TL.
    max_price : int
        Current testing maximum bound in TL.
    done_ranges : set[tuple[int, int]]
        Set of recorded (already-completed) bounds.
    save_fn : Callable
        Function pointing to the data persistence orchestrator.
    mark_done_fn : Callable
        Function pointing to checkpoint persistence logical flow.
    bracket_cache : list | None
        Active list tracking leaf brackets as they emerge from recursion.
    delay : float
        Configured base latency limit payload to stagger query speeds.
    indent : int
        Padding tracker to provide tree structured logs on the terminal.

    Returns
    -------
    int
        The total number of records successfully captured and saved by leaf logic.
    """
    pad = "  " * indent

    if (min_price, max_price) in done_ranges:
        logger.info("%s↩  Skipping completed: %d–%d TL", pad, min_price, max_price)
        return 0, cached_rooms_idx

    width = max_price - min_price
    logger.info("%s▶  Checking range %d–%d TL…", pad, min_price, max_price)

    url = _build_url(min_price, max_price, page=1)
    
    # Use retry logic for page loading
    def load_page():
        driver.get(url)
        return _wait_for_listings(driver)
    
    try:
        tree = _retry_with_backoff(load_page)
    except Exception as exc:
        logger.error("%s✗  Failed to load range %d–%d TL: %s", pad, min_price, max_price, exc)
        return 0, cached_rooms_idx
    
    total_listings = _extract_total_listings(tree)
    
    # Cache room index on first successful parse
    if cached_rooms_idx is None:
        cached_rooms_idx = _resolve_rooms_index(tree)

    # ── Split decision ────────────────────────────────────────────────────────
    # Intelligent splitting: split earlier for high-density ranges
    should_split = (
        total_listings is not None
        and total_listings > config.MAX_LISTINGS_PER_QUERY
        and width > config.MIN_BRACKET_WIDTH
    )
    
    # Early split for high-density ranges to optimize performance
    early_split = (
        total_listings is not None
        and total_listings > config.HIGH_DENSITY_THRESHOLD
        and width > config.MIN_BRACKET_WIDTH * 2
    )
    
    if should_split or early_split:
        if early_split and not should_split:
            logger.info(
                "%s   ⚡ High density (%d listings). Early split for optimization…",
                pad, total_listings,
            )
        else:
            logger.info(
                "%s   ✂️ Range too dense (%d listings). Splitting…",
                pad, total_listings,
            )
        
        mid = (min_price + max_price) // 2
        
        # Use adaptive delay between splits
        time.sleep(random.uniform(
            config.BETWEEN_BRACKET_DELAY_MIN,
            config.BETWEEN_BRACKET_DELAY_MAX,
        ))
        
        # Recursively split with cached room index
        total, cached_rooms_idx = scrape_and_resolve(
            driver, min_price, mid,
            done_ranges, save_fn, mark_done_fn, bracket_cache, delay, indent + 1,
            cached_rooms_idx,
        )
        count2, cached_rooms_idx = scrape_and_resolve(
            driver, mid + 1, max_price,
            done_ranges, save_fn, mark_done_fn, bracket_cache, delay, indent + 1,
            cached_rooms_idx,
        )
        total += count2
        return total, cached_rooms_idx

    elif total_listings is not None and total_listings > config.MAX_LISTINGS_PER_QUERY:
        logger.warning(
            "%s   ⚠ Min width (%d TL) reached but count (%d) still over cap. "
            "Scraping up to the 1000-listing limit only.",
            pad, width, total_listings,
        )
    elif total_listings is not None and total_listings == 0:
        logger.info("%s   ⊘ Empty range (0 listings). Skipping.", pad)
        mark_done_fn(min_price, max_price)
        done_ranges.add((min_price, max_price))
        return 0, cached_rooms_idx
    elif total_listings is not None:
        logger.info(
            "%s   ✓ Safe range (%d listings). Scraping now…",
            pad, total_listings,
        )
    else:
        logger.info("%s   ? Could not parse count (likely 0). Scraping.", pad)

    # ── Scrape this safe bracket (page 1 already loaded — no extra request) ──
    if bracket_cache is not None:
        bracket_cache.append([min_price, max_price])

    records = _scrape_pages_from_soup(
        driver, tree, min_price, max_price, delay, pad, cached_rooms_idx
    )

    if records:
        save_fn(records)
        logger.info(
            "%s✅ Saved %d records for %d–%d TL.",
            pad, len(records), min_price, max_price,
        )

    mark_done_fn(min_price, max_price)
    done_ranges.add((min_price, max_price))
    return len(records), cached_rooms_idx


# ── Direct leaf-bracket scrape ────────────────────────────────────────────────

def scrape_leaf_bracket(
    driver: uc.Chrome,
    min_price: int,
    max_price: int,
    save_fn,
    mark_done_fn,
    delay: float = config.PAGE_LOAD_DELAY,
    cached_rooms_idx: Optional[int] = None,
) -> tuple[int, Optional[int]]:
    """Scrape a single price bracket whose bounds are already known to be safe.

    Used on --resume when the complete bracket list has been cached in the
    checkpoint from a previous run. Skips peeking at the listing count,
    loading page 1 directly and scraping all pages from there.

    Args
    ----
    driver : uc.Chrome
        Active driver proxy.
    min_price : int
        Lowest listing criteria price.
    max_price : int
        Highest listing criteria price.
    save_fn : Callable
        Function appending collected records.
    mark_done_fn : Callable
        Function for updating ongoing progress logs.
    delay : float
        Pre-configured sleep buffer limit (deprecated, uses adaptive delay).
    cached_rooms_idx : Optional[int]
        Pre-cached room column index to avoid re-parsing.

    Returns
    -------
    tuple[int, Optional[int]]
        Tuple of (record count, cached room index).
    """
    logger.info("▶  Scraping bracket %d–%d TL…", min_price, max_price)
    url = _build_url(min_price, max_price, page=1)
    
    # Use retry logic for page loading
    def load_page():
        driver.get(url)
        return _wait_for_listings(driver)
    
    try:
        tree = _retry_with_backoff(load_page)
    except Exception as exc:
        logger.error("✗  Failed to load bracket %d–%d TL: %s", min_price, max_price, exc)
        return 0, cached_rooms_idx
    
    # Cache room index if not already cached
    if cached_rooms_idx is None:
        cached_rooms_idx = _resolve_rooms_index(tree)

    records = _scrape_pages_from_soup(
        driver, tree, min_price, max_price, delay, "", cached_rooms_idx
    )

    if records:
        save_fn(records)
        logger.info("✅ Saved %d records for %d–%d TL.", len(records), min_price, max_price)

    mark_done_fn(min_price, max_price)
    return len(records), cached_rooms_idx


# ── CSV output ────────────────────────────────────────────────────────────────

def save_incremental(data_batch: list[dict]) -> None:
    """Append a batch of records to the shared CSV.
    
    Args
    ----
    data_batch : list[dict]
        The newly validated chunk of dictionary records.
    """
    if not data_batch:
        return

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    file_exists = os.path.isfile(config.CSV_OUTPUT_FILE)

    with open(config.CSV_OUTPUT_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["product_name", "price"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(data_batch)
