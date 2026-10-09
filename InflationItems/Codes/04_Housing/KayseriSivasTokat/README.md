# Sahibinden Kira Scraper

A stealth browser scraper that collects rental listing data (district, room count, price) from [sahibinden.com](https://www.sahibinden.com) for the cities of Kayseri, Sivas, and Tokat. Built on top of [rayobrowse](https://github.com/rayobyte-data/rayobrowse) (a stealth Chromium container) and Playwright. Designed to survive bot detection, Cloudflare Turnstile, managed challenges, and unexpected redirects — and to do so while looking like a real human using a browser.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Project Structure](#project-structure)
4. [Output Structure](#output-structure)
5. [How to Run](#how-to-run)
6. [Live CLI Commands](#live-cli-commands)
7. [How It Works — Full Flow](#how-it-works--full-flow)
   - [Startup](#1-startup)
   - [Browser Session Lifecycle](#2-browser-session-lifecycle)
   - [Warmup and Trust Building](#3-warmup-and-trust-building)
   - [Bot Detection Handling](#4-bot-detection-handling)
   - [Adaptive Bracket Scraping](#5-adaptive-bracket-scraping)
   - [Data Parsing and Saving](#6-data-parsing-and-saving)
   - [Checkpointing and Resume](#7-checkpointing-and-resume)
8. [Scenario Reference](#scenario-reference)
9. [Function Reference](#function-reference)
10. [Configuration Reference](#configuration-reference)
11. [Timing Reference](#timing-reference)
12. [Troubleshooting](#troubleshooting)

---

## Prerequisites

| Requirement | Version | Purpose |
|---|---|---|
| Python | 3.10 – 3.12 | Runtime |
| Docker Desktop | Any current | Runs the rayobrowse stealth browser daemon |
| uv or pip | Any | Package management |

> **Python 3.14 is not recommended.** Rayobrowse and Playwright are tested on 3.10–3.12.

---

## Installation

**Step 1 — Install Python dependencies**

```bash
pip install playwright beautifulsoup4 rayobrowse
playwright install chromium
```

**Step 2 — Start the rayobrowse Docker container**

Navigate to the folder containing `docker-compose.yml` (the rayobrowse repo) and run:

```bash
docker compose up -d
```

**Step 3 — Verify the daemon is healthy**

```bash
curl http://localhost:9222/health
# Expected: {"success": true, "data": {"status": "healthy", ...}}
```

**Step 4 — (Optional) Increase Docker memory**

Each browser instance needs ~300 MB RAM minimum. Go to **Docker Desktop → Settings → Resources → Memory** and set it to at least **4 GB**. Also add `shm_size: '512mb'` to the `docker-compose.yml` service block to prevent Chromium from dying due to shared memory limits:

```yaml
services:
  rayobrowse:
    image: rayobyte/rayobrowse:latest
    shm_size: '512mb'
    ports:
      - "9222:9222"
      - "6080:6080"
    env_file:
      - .env
```

---

## Project Structure

```
KayseriSivasTokat/
├── run_scraper.py        ← Entry point. Checks daemon, then calls main()
├── main.py               ← Argument parsing, console listener, city loop
├── scraper.py            ← All scraping logic
├── config.py             ← All tuneable settings
└── checkpoints/
    ├── checkpoint_YYYY-MM-DD.json   ← Resume state (created at runtime)
    └── cookies/
        ├── kayseri_cookies.json     ← Persistent session cookies per city
        ├── sivas_cookies.json
        └── tokat_cookies.json
```

Output data is written three levels up from the script directory:

```
[Project Root]/
└── Datas/
    └── HousesRent/
        ├── Kayseri/
        │   └── YYYY-MM-DD.csv
        ├── Sivas/
        │   └── YYYY-MM-DD.csv
        └── Tokat/
            └── YYYY-MM-DD.csv
```

---

## Output Structure

Each CSV file has three columns:

| Column | Example | Description |
|---|---|---|
| `District` | `Kayseri / Melikgazi / Bahçelievler` | Full location path from the listing |
| `Rooms` | `3+1` | Room count as shown on the site |
| `Price` | `8500.0` | Monthly rent in Turkish Lira (float) |

A new CSV is created each day (`YYYY-MM-DD.csv`). Running the scraper twice on the same day **appends** to the same file — it does not overwrite.

### Output flow diagram

```
sahibinden.com
      │
      │  HTML response
      ▼
 parse_page()
      │
      │  [{District, Rooms, Price}, ...]
      ▼
save_incremental()
      │
      ├─── file does not exist yet ──► creates file + writes header + rows
      │
      └─── file exists ─────────────► appends rows (no header)
      │
      ▼
[Project Root]/Datas/HousesRent/{CityName}/YYYY-MM-DD.csv
```

---

## How to Run

### Normal run (all cities, fresh start)

```bash
python run_scraper.py
```

Deletes any existing CSV for today and starts from scratch for all three cities.

### Resume an interrupted run

```bash
python run_scraper.py --resume
```

Reads `checkpoints/checkpoint_YYYY-MM-DD.json` and continues from the last completed top-level price bracket. The interrupted bracket is skipped to avoid duplicate rows in the CSV.

### Scrape a single city only

```bash
python run_scraper.py --city kayseri
python run_scraper.py --city sivas
python run_scraper.py --city tokat
```

### Verbose/debug logging

```bash
python run_scraper.py -v
```

Prints DEBUG-level logs including every exception that is normally silenced, every page content failure, and every cookie operation detail.

### Combining flags

```bash
python run_scraper.py --resume --city kayseri -v
```

---

## Live CLI Commands

While the scraper is running, type any of these commands and press Enter. The console listener thread reads them and passes them to the scraper through a thread-safe queue.

| Command | Effect |
|---|---|
| `ok` or `devam` | Confirm a manual captcha/challenge you solved in the browser. Resumes immediately. |
| `next` | Skip the current price bracket. Moves to the next bracket in the same city. |
| `skip` | Skip the current city entirely. Moves to the next city. |
| `stop` | Gracefully stop the scraper after the current page finishes. |
| `status` | Print the current city, bracket, and page number. |
| `help` | Print the command list. |

> **Important:** `ok` / `devam` is only useful when a `🔒` prompt appears on the console asking you to solve something manually. After you solve it in the browser window, type `ok` and press Enter. If you don't respond within 90 seconds, the scraper automatically continues anyway.

---

## How It Works — Full Flow

### 1. Startup

```
python run_scraper.py
        │
        ▼
check_daemon()
        │
        ├── GET http://localhost:9222/health
        │
        ├── {"status": "healthy"} ──► ✅ continue
        │
        └── any error ──────────────► ❌ print instructions and exit
        │
        ▼
main() in main.py
        │
        ▼
Start console_listener thread (owns stdin for the entire run)
        │
        ▼
For each city in CITIES:
    call scrape_city()
```

`run_scraper.py` exists purely to guard against the case where Docker is not running. It does a plain HTTP health check against the rayobrowse daemon on `localhost:9222`. If the daemon isn't up, it prints clear instructions and exits before any browser is created.

---

### 2. Browser Session Lifecycle

A new browser session is created for each city (and again on each retry). The browser is never reused across cities.

```
scrape_city()
      │
      ▼
rayobrowse.create_browser(
    headless=False,
    target_os="windows",
    browser_language="tr-TR,tr;q=0.9",
    ui_language="tr-TR"
)  ──► returns WebSocket URL string
      │
      ▼
async_playwright().start()
      │
      ▼
pw.chromium.connect_over_cdp(ws_url)
      │
      ▼
browser.contexts[0].pages[0]   ← use pre-created stealth context, not new_page()
      │
      ▼
  [scraping happens here]
      │
      ▼
browser.close()   ← sufficient, no close_browser() needed
pw.stop()
```

**Why `contexts[0].pages[0]` instead of `new_page()`?**
rayobrowse pre-creates a browser context with its stealth fingerprint patches applied. Calling `browser.new_page()` creates a fresh context that may not have the patches. Using the pre-created page ensures the fingerprint is consistent.

**Why `target_os="windows"`?**
The rayobrowse documentation states that Windows and Android fingerprints are the most thoroughly tested. A Linux fingerprint is more likely to be flagged as a server/bot by detection systems.

---

### 3. Warmup and Trust Building

Before scraping any listings, the browser visits the sahibinden.com homepage and performs human-like behaviour to build a trust score with the site's analytics.

```
warmup_with_human_surf()
      │
      ▼
Check saved cookies from previous session
      │
      ├── cookies exist and are not expired ──► load into browser
      │         │
      │         ▼
      │    Navigate to homepage
      │         │
      │         ├── page loads cleanly ──► skip warmup, go straight to scraping
      │         │
      │         └── protection/login detected ──► delete cookies, do full warmup
      │
      └── no cookies ──► full warmup:
                │
                ▼
         Navigate to sahibinden.com homepage
                │
                ▼
         Wait 3–5 seconds (HOMEPAGE_WAIT)
                │
                ▼
         Check for protection page
                │
                ├── Turnstile/Cloudflare ──► auto_solve_turnstile()
                ├── other captcha ──────────► wait_for_manual_solve()
                └── clean ──────────────────► continue
                │
                ▼
         Scroll page 2–4 times randomly
                │
                ▼
         Move mouse to a random nav link
                │
                ▼
         1 random browsing click
                │
                ▼
         Save cookies for next session
```

**`human_jittery_move(page, tx, ty, steps=15)`**
Moves the mouse from a random starting position to the target coordinates in 15 micro-steps with ±8px random jitter per step and a 10–50ms delay between steps. This produces a curved, imprecise path that matches real human mouse movement patterns.

**`human_browsing_clicks(page, count)`**
Clicks random coordinates across the page body. Uses actual viewport dimensions to calculate safe click zones proportionally (10%–90% of width, 20%–90% of height).

**`bracket_safe_clicks(page, count)`**
Called between price brackets to simulate a user interacting with the page between search queries. Picks from 6 varied zones (top-left, top-right, bottom-left, bottom-right, center, left-middle) rather than always clicking screen edges, which would be detectable as robotic after a few brackets.

---

### 4. Bot Detection Handling

Every page navigation goes through `safe_goto()`, which classifies the response before returning it to the scraper.

```
safe_goto(page, url)
      │
      ▼
goto_with_retry()   ← up to 3 attempts on timeout, fails immediately on other errors
      │
      ▼
Wait 8–12 seconds (PAGE_LOAD_AFTER_GOTO) — human reading time simulation
      │
      ▼
get_page_content()
      │
      ▼
is_login_page(html, page)?
      │
      ├── YES ──► raise BrowserBlockedError("Login yönlendirmesi: <url>")
      │
      └── NO ──► is_protection_page(html, page)?
                      │
                      ├── Turnstile or Cloudflare ──► auto_solve_turnstile()
                      │         │
                      │         ├── solved ──► re-check, continue
                      │         └── failed ──► wait_for_manual_solve()
                      │
                      ├── Other captcha ──────────────► wait_for_manual_solve()
                      │
                      └── Clean page ─────────────────► return HTML to caller
```

#### Page classification

**`is_login_page(html, page)`** uses a three-tier approach:

1. **URL check (strongest):** If the URL contains `/giris`, it is definitively the login page.
2. **Safe URL allowlist:** If the URL is the homepage, `/kiralik/`, `/satilik/`, `/ilan/`, or `/cs/checkloading`, it is definitively not the login page. This prevents false positives because sahibinden embeds a hidden login modal (with `type="password"` and `type="email"` fields) into every page for the header login button — the old approach of checking for those fields in HTML would fire on every page.
3. **Last-resort HTML check:** Requires `type="password"` + `type="email"` + `"google ile giriş yap"` all present together. The Google login button only appears on the actual `/giris` page, not in the hidden modal.

**`is_protection_page(html, page)`** scans for known markers: `px-captcha` (PerimeterX), `cf-turnstile` (Cloudflare Turnstile), `datadome`, `g-recaptcha`, `h-captcha`, `olağan dışı erişim` (PerimeterX Turkish), `/cs/checkloading` in URL (Managed Challenge), `güvenlik doğrulaması` or `tarayıcınızı kontrol ediyoruz` (Cloudflare), `bir dakika lütfen` or `doğrulanıyor` (Cloudflare Wait). Always calls `is_login_page` first — the real login page embeds hCaptcha, and without this guard the login page would be misreported as an hCaptcha challenge.

#### Turnstile handling

```
auto_solve_turnstile()
      │
      ├── "managed" or "checkloading" in reason?
      │         │
      │         └── YES ──► _wait_for_managed_redirect()
      │                           Poll every 2s for up to 40s.
      │                           Return True when URL leaves /cs/checkloading
      │
      └── NO (interactive Turnstile) ──► _auto_solve_interactive_turnstile()
                    │
                    ▼
             Check: is challenge still present?
                    │
                    ├── NO (user already solved it) ──► return True immediately
                    │                                    (no stray clicks on results page)
                    │
                    └── YES ──► find Cloudflare iframe (up to 15s)
                                      │
                                      ├── not found ──► wait 25s, check again
                                      │
                                      └── found ──► move mouse near checkbox
                                                    hover 4–6 times with small jitter
                                                    check again (user may solve during hover)
                                                    click checkbox
                                                    click #btn-continue if visible
                                                    poll every 2s for up to 20s
```

#### Manual solve flow

When auto-solve fails or detects a captcha type it cannot handle (PerimeterX, DataDome, reCAPTCHA, hCaptcha), `wait_for_manual_solve()` is called:

```
🔒 [reason] | URL: [current url]
   Konsola 'ok' yazın devam etmek için.
   Veya: skip / next / stop
   90s içinde yanıt gelmezse otomatik devam edilir.
```

The function polls `cmd_queue` every 0.5 seconds for 90 seconds. It never calls `input()` — the `console_listener` thread is the only thing that reads from stdin, eliminating the deadlock that previously caused CLI commands to stop working.

---

### 5. Adaptive Bracket Scraping

The core scraping strategy uses price brackets to work around sahibinden's 1,000-listing result cap per query.

#### Price brackets (from `config.py`)

| Bracket | Range |
|---|---|
| 0 | 0 – 19,999 TL |
| 1 | 20,000 – 39,999 TL |
| 2 | 40,000 – 59,999 TL |
| 3 | 60,000 – 99,999 TL |
| 4 | 100,000 – 9,999,999 TL |

#### Adaptive split logic

For each bracket, the scraper performs an "early peek" — it loads page 1, reads the total listing count from the page, and decides whether the range is too dense to scrape completely.

```
scrape_adaptive_bracket(min_price, max_price, depth)
      │
      ▼
Navigate to page 1 of this price range
      │
      ▼
extract_total_listings()
      │
      ├── total > MAX_LISTINGS_PER_QUERY (1000)?
      │   AND width > MIN_BRACKET_WIDTH (500 TL)?
      │   AND depth < MAX_ADAPTIVE_DEPTH (6)?
      │         │
      │         └── YES ──► SPLIT
      │                       mid = (min + max) // 2
      │                       ┌─────────────────────────────────────┐
      │                       │  recurse(min, mid,   depth+1)       │
      │                       │  wait 4–6s                          │
      │                       │  recurse(mid+1, max, depth+1)       │
      │                       └─────────────────────────────────────┘
      │
      └── NO (safe range, or min width reached) ──► SCRAPE
                  │
                  ▼
           Parse page 1 → save_incremental()
                  │
                  ▼
           Find "Sonraki" (next) button
                  │
                  ├── not found ──► done, return count
                  │
                  └── found ──► wait 8–12s, navigate, parse, save
                                repeat up to MAX_PAGES_PER_BRACKET (20) times
```

#### Split example

If the 20,000–39,999 TL bracket has 2,400 listings:

```
20,000–39,999 TL  (2400 listings → split)
    │
    ├── 20,000–29,999 TL  (check)
    │       ├── 20,000–24,999 TL  (check, safe → scrape all pages)
    │       └── 25,000–29,999 TL  (check, safe → scrape all pages)
    │
    └── 30,000–39,999 TL  (check, safe → scrape all pages)
```

The maximum recursion depth is 6, which limits splitting to at most 64 sub-ranges per bracket. The minimum bracket width of 500 TL prevents infinite recursion in extremely dense price points.

`extract_total_listings()` tries three strategies in order:
1. Looks for a `.result-text` element (most reliable)
2. Scans all text nodes for patterns like `"3.193 ilan bulundu"`
3. Runs regex patterns across the full page text as a fallback

If the count cannot be determined, the scraper proceeds to scrape anyway and treats the range as safe.

---

### 6. Data Parsing and Saving

**`parse_page(html)`** receives the raw HTML of a search results page and extracts all listings from the `#searchResultsTable tbody tr.searchResultsItem` rows.

For each row it extracts:
- **Price** from `.searchResultsPriceValue` → passed through `normalize_price()`
- **District** from `.searchResultsLocationValue` → joined with ` / ` separator
- **Rooms** from the column whose header contains `"oda"` (normalised for Turkish characters: ı→i, ö→o etc.) or falls back to the second attribute column

A row is only included if both price and district are valid. Rows with missing price or `"N/A"` district are silently dropped.

**`normalize_price(t)`** handles three Turkish number formats:
- `"8.500,00 TL"` → dot is thousands separator, comma is decimal → `8500.0`
- `"8500,00"` → comma is decimal → `8500.0`
- `"8500.00"` → dot is decimal (checks that non-final parts are 3 digits to distinguish from thousands) → `8500.0`

**`save_incremental(city_name, batch)`** appends a batch of records to the day's CSV file. It checks `os.path.isfile()` at each call to decide whether to write the header row — this is how it correctly handles the first write of the day. The CSV columns are always `District, Rooms, Price`.

If `parse_page` returns no records, the console prints a warning with the current URL, detected protection status, and HTML length — so you know whether it was a genuine end-of-results or a silent failure.

---

### 7. Checkpointing and Resume

The checkpoint system allows a run interrupted by a crash, block, or manual `stop` command to continue from where it left off rather than starting over.

```
Checkpoint file: checkpoints/checkpoint_YYYY-MM-DD.json

{
  "city":          "kayseri",
  "bracket_index": 2,          ← enumeration index (0–4), NOT a price
  "page_num":      1,
  "saved_at":      "2025-01-15T14:23:11"
}
```

**Saving:** `save_checkpoint()` is called by `scrape_city_brackets()` after each top-level bracket completes, using the bracket's enumeration index (`bi = 0, 1, 2, 3, 4`). It uses an atomic write — it writes to a `.tmp` file first and then calls `os.replace()`, so a crash during the write never corrupts the checkpoint.

**Loading:** On `--resume`, `get_resume_point()` reads `bracket_index` from the file and `scrape_city_brackets()` skips brackets where `bi < start_bracket`.

**Duplicate prevention on resume:** When resuming, the bracket that was interrupted when the crash happened is **skipped entirely** (jumped to `start_bracket + 1`). This prevents duplicate rows in the CSV at the cost of potentially missing some listings from that one bracket. A console warning is printed to tell you this happened.

```
Resume flow:

checkpoint says bracket_index=2 (40,000–59,999 TL)
      │
      ▼
scrape_city_brackets():
  bi=0 (0–19,999)      → skip (bi < start_bracket)
  bi=1 (20,000–39,999) → skip (bi < start_bracket)
  bi=2 (40,000–59,999) → SKIP (interrupted bracket, warn user)
  bi=3 (60,000–99,999) → scrape ✓
  bi=4 (100,000+)      → scrape ✓
```

**Cookie persistence:** After each successful city, cookies are saved to `checkpoints/cookies/{city_slug}_cookies.json`. On the next run, the scraper loads these cookies and navigates to the homepage. If the page loads cleanly (no protection page, no login, results table present), the warmup phase is skipped entirely, saving ~30 seconds per city. Session cookies (no expiry) are filtered out before saving — only cookies with a future expiry date are kept.

---

## Scenario Reference

### Scenario A — Clean run, no bot detection

```
Startup ──► Daemon healthy
Browser created ──► Load cookies
Cookie check ──► Valid ──► Skip warmup
Navigate to bracket ──► Results page loads cleanly
Extract listing count ──► Safe range
Scrape all pages ──► save to CSV
Next bracket ──► ...
City complete ──► Save cookies ──► Next city
```

### Scenario B — Turnstile appears on a listing page

```
Navigate to bracket ──► Turnstile detected
auto_solve_turnstile():
    Check if already solved ──► not yet
    Find iframe ──► hover ──► click checkbox
    Wait up to 20s
    ──► Solved: continue scraping normally
    ──► Not solved: wait_for_manual_solve() ──► print 🔒 prompt
        User types 'ok' ──► continue
        OR 90s timeout ──► auto-continue
```

### Scenario C — Turnstile user solved before console prompt appears

```
Navigate to bracket ──► Turnstile detected
auto_solve_turnstile():
    Check if already solved ──► YES (user solved in browser)
    ──► return True immediately, no clicks
Continue scraping normally (no stray click on results)
```

### Scenario D — Browser gets hard-blocked (login redirect)

```
Navigate to bracket ──► Login page detected
raise BrowserBlockedError
scrape_city() catches it:
    delete cookies
    if attempt < MAX_RESTARTS_PER_CITY (3):
        wait 30–60s
        create new browser session
        full warmup again
        retry from checkpoint
    else:
        log error, skip city
```

### Scenario E — Run interrupted mid-bracket (crash / Ctrl+C)

```
Checkpoint saved at last completed bracket
User runs: python run_scraper.py --resume
scrape_city_brackets():
    Reads checkpoint: bracket_index=2
    Warns: "yarım kalan bracket atlanıyor (40,000–59,999 TL)"
    Starts from bracket_index=3
Continues without duplicating already-saved data
```

### Scenario F — Dense price range triggers splitting

```
Navigate to 20,000–39,999 TL
extract_total_listings() = 2,400
2400 > MAX_LISTINGS_PER_QUERY (1000) AND width > MIN_BRACKET_WIDTH (500)
    → Split into 20,000–29,999 and 30,000–39,999
        20,000–29,999: 850 listings → safe → scrape all pages
        30,000–39,999: 1,100 listings → split again
            30,000–34,999: 450 → safe → scrape
            35,000–39,999: 650 → safe → scrape
```

### Scenario G — Unexpected redirect (error page, different domain)

```
Navigate to bracket URL
final URL does not contain "sahibinden.com"
    → Console: ⚠️ Beklenmeyen yönlendirme! İstenen: <url> → Gelen: <final_url>
parse_page() finds no rows
    → Console: ⚠️ Sayfa 1'de hiç kayıt yok! URL: ... | Koruma: yok | HTML uzunluğu: ...
break out of pagination loop
move to next bracket
```

---

## Function Reference

### `run_scraper.py`

**`check_daemon()`**
Sends a GET request to `http://localhost:9222/health`. If the response is not `{"status": "healthy"}`, prints a human-readable error message telling the user to run `docker compose up -d` and exits. Prevents all downstream errors from appearing before the user knows Docker isn't running.

---

### `main.py`

**`console_listener(cmd_queue, stop_event)`**
Runs in a background daemon thread and is the **sole owner of stdin** for the entire lifetime of the program. Blocks on `input()`, strips and lowercases each line, and puts recognised commands (`skip`, `next`, `stop`, `ok`, `devam`) into `cmd_queue`. `scraper.py` functions read from this queue. No scraper function ever calls `input()` — this design prevents the stdin deadlock that previously caused CLI commands to stop working mid-run.

**`update_status(city, bracket, page)`** / **`print_status()`**
Maintains a thread-safe `_current_status` dict. `print_status()` is triggered by the `status` command and prints the current city, bracket, and page number.

**`run(args)`**
The main async coroutine. Loads or ignores the checkpoint based on `--resume`. Clears today's CSV files if not resuming. Iterates over cities, calling `scrape_city()` for each, and handles `SkipCitySignal` and `StopSignal` at this level.

---

### `scraper.py`

#### Signals (exceptions used as control flow)

| Signal | Raised by | Caught by | Effect |
|---|---|---|---|
| `SkipCitySignal` | `check_commands`, `wait_for_manual_solve` | `run()` in main.py | Abandon current city, move to next |
| `SkipBracketSignal` | `check_commands`, `wait_for_manual_solve` | `scrape_city()` | Increment `start_bracket`, retry city |
| `StopSignal` | `check_commands`, `wait_for_manual_solve` | `run()` in main.py | Stop the entire scraper |
| `BrowserBlockedError` | `safe_goto`, warmup functions | `scrape_city()` | Trigger retry with new browser session |

#### Command helpers

**`check_commands(cmd_queue)`**
Drains the entire command queue in a loop using `get_nowait()` (non-blocking). Raises the appropriate signal for `skip`/`next`/`stop`. Logs acknowledgement for `ok`/`devam`. Called at every decision point: top of each bracket loop, top of each page loop, and inside `interruptible_sleep`.

**`interruptible_sleep(seconds, cmd_queue)`**
Sleeps for the specified duration but wakes up every 0.5 seconds to call `check_commands`. This means a `stop` command during a 12-second page-load wait responds within 0.5 seconds rather than after the full delay.

#### Alert and manual solve

**`beep_alert()`**
On Windows, plays `SystemExclamation` then `SystemHand` using `winsound`. On other systems, writes `\a` (ASCII bell) to stdout. Logs at DEBUG level if a sound fails so you know why it is silent.

**`wait_for_manual_solve(loop, reason, cmd_queue, timeout=90)`**
Prints the `🔒` prompt with the reason and current URL. Polls `cmd_queue` every 0.5 seconds for up to 90 seconds. Interprets `ok`/`devam` as confirmation to continue, and `skip`/`next`/`stop` as their respective signals. If no command arrives within 90 seconds, logs a timeout warning and returns (auto-continues). Never calls `input()`.

#### Mouse helpers

**`_get_viewport(page)`**
Reads `page.viewport_size` and returns `(width, height)`. Falls back to `(1280, 800)` if the page is disconnected or the viewport is unavailable.

**`human_jittery_move(page, tx, ty, steps=15)`**
Moves the mouse from a random start position proportional to the viewport to the target `(tx, ty)` in 15 micro-steps. Each step adds ±8px of random noise and pauses 10–50ms. The result is a curved, imprecise path.

**`human_browsing_clicks(page, count)`**
Picks random `(x, y)` coordinates within the safe portion of the viewport and clicks them after a jittery mouse move. Used during warmup to simulate a user reading the homepage.

**`bracket_safe_clicks(page, count)`**
Similar to above but picks from 6 predefined zones (corners, center, left-middle) rather than the full page. Used between brackets to simulate the user repositioning their mouse between searches without accidentally clicking a listing.

#### Page classification

**`is_login_page(html, page)`**
See [Bot Detection Handling](#4-bot-detection-handling) for full detail. Returns `True` only for the actual `/giris` login page.

**`is_protection_page(html, page)`**
Returns `(True, name)` if a known bot-detection marker is found, `(False, "")` otherwise. Always calls `is_login_page` first to avoid misclassifying the login page as an hCaptcha challenge.

#### Navigation

**`goto_with_retry(page, url, retries=3)`**
Calls `page.goto()`. On timeout, waits 13–18 seconds and retries up to 3 times. On any non-timeout error (connection reset, browser closed), raises `BrowserBlockedError` immediately without retrying — pointless retries on fatal errors were a previous bug.

**`safe_goto(page, url, loop, cmd_queue)`**
The main navigation function used by all scraping code. Calls `goto_with_retry`, waits 8–12 seconds, reads the page, checks for login or protection, handles Turnstile automatically, calls `wait_for_manual_solve` for other protections, logs the final URL after navigation, warns on unexpected redirects, and waits for the results table selector before returning the final HTML.

#### Data extraction

**`extract_total_listings(soup)`**
Tries three strategies to read the total listing count from a search results page. Returns an integer or `None`.

**`get_room_col_index(soup)`**
Reads the `<thead>` of the results table and finds which column index corresponds to the room count. Normalises all Turkish characters before comparing so `"Oda Sayısı"`, `"Oda/Salon"`, and plain `"Oda"` all match.

**`parse_page(html)`**
Parses the full HTML with BeautifulSoup. Selects all `tr.searchResultsItem` rows. For each row extracts price (via `normalize_price`), district (joined location path), and room count. Returns `(list_of_records, soup)`.

**`normalize_price(t)`**
Strips currency symbols, handles Turkish number formatting (dot as thousands separator, comma as decimal), and converts to a Python float. Returns `None` for unparseable input.

#### Persistence

**`save_incremental(city_name, batch)`**
Appends a list of record dicts to today's CSV. Creates the output directory and file if needed. Writes the header only on first creation.

**`save_checkpoint(city_slug, bracket_index, page_num)`**
Atomically writes the checkpoint JSON using a temp file + `os.replace()`. The `bracket_index` field is always the enumeration index of the top-level bracket (0–4), never a price value.

**`load_checkpoint()`**
Reads and returns the checkpoint dict. Logs a warning if the file is corrupt and returns `{}`.

**`clear_checkpoint()`**
Removes the checkpoint file after a full successful run.

**`get_resume_point(checkpoint, city_slug)`**
Returns `(bracket_index, page_num)` from the checkpoint if the city matches, otherwise `(0, 1)`.

#### Cookie management

**`get_cookie_path(city_slug)`**
Returns the path for a city's cookie file. Creates the cookies directory only once per process run (cached with `_COOKIE_DIR_CREATED`).

**`save_cookies(page, city_slug)`**
Reads all cookies from the browser context, filters out session cookies (those with no `expires` field or an `expires` in the past), and saves the rest to JSON.

**`load_cookies(page, city_slug)`**
Reads cookies from the JSON file, filters out expired ones, adds the valid ones to the browser context, and returns `True` if any were loaded.

**`delete_cookies(city_slug)`**
Removes the cookie file. Only logs confirmation if the file actually existed.

#### Core scraping

**`scrape_adaptive_bracket(...)`**
The recursive scraping engine. Navigates to a price range URL, reads the listing count, and either splits the range in half (if too dense) or paginates through all pages. Does not call `save_checkpoint` — that is the responsibility of the caller.

**`scrape_city_brackets(...)`**
Iterates the five top-level brackets. Calls `scrape_adaptive_bracket` for each. Calls `save_checkpoint` with the correct bracket index after each bracket completes. On resume, skips the interrupted bracket to prevent duplicate rows.

**`scrape_city(city, checkpoint, cmd_queue)`**
Creates the browser, manages the warmup, calls `scrape_city_brackets`, and handles all retry logic. Retries up to `MAX_RESTARTS_PER_CITY` (3) times on `BrowserBlockedError`. Raises `SkipCitySignal` and `StopSignal` up the stack immediately. Always closes the browser in the `finally` block.

---

## Configuration Reference

All settings are in `config.py`.

| Setting | Default | Description |
|---|---|---|
| `CITIES` | Kayseri, Sivas, Tokat | List of cities to scrape |
| `DEFAULT_BRACKETS` | 5 price ranges | Price ranges per city |
| `OUTPUT_BASE_DIR` | `[root]/Datas/HousesRent` | Where CSVs are written |
| `CHECKPOINT_DIR` | `./checkpoints` | Where checkpoint and cookie files are stored |
| `MAX_RESTARTS_PER_CITY` | `3` | Browser restart attempts before giving up on a city |
| `MAX_PAGES_PER_BRACKET` | `20` | Maximum pages per price range (1000 listings cap) |
| `PAGE_SIZE` | `50` | Listings per page |
| `MAX_LISTINGS_PER_QUERY` | `1000` | Threshold above which a price range is split |
| `MIN_BRACKET_WIDTH` | `500` | Minimum TL range — splitting stops below this |
| `MAX_ADAPTIVE_DEPTH` | `6` | Maximum recursion depth for bracket splitting |
| `RAYOBROWSE_HEADLESS` | `False` | Show browser window (True = invisible) |
| `RAYOBROWSE_TARGET_OS` | `"windows"` | Fingerprint OS (windows has best coverage) |
| `RAYOBROWSE_BROWSER_LANGUAGE` | `"tr-TR,tr;q=0.9"` | Accept-Language header |
| `RAYOBROWSE_UI_LANGUAGE` | `"tr-TR"` | Browser UI locale |
| `BASE_URL` | `"https://www.sahibinden.com"` | Target site |

---

## Timing Reference

All delays are randomised within a range to avoid predictable intervals.

| Setting | Range | When it fires |
|---|---|---|
| `HOMEPAGE_WAIT` | 3–5 s | After loading the homepage during warmup |
| `PAGE_LOAD_AFTER_GOTO` | 8–12 s | After every page navigation (simulates reading time) |
| `BETWEEN_PAGES` | 8–12 s | Between pagination pages within a bracket |
| `BETWEEN_BRACKETS` | 4–6 s | Between top-level price brackets |
| `GOTO_RETRY_WAIT` | 13–18 s | Between timeout retries in `goto_with_retry` |
| `POST_CHECK_WAIT` | 4–6 s | After manual captcha solve before re-checking |
| `CITY_CLOSE_WAIT` | 30 s (fixed) | Delay after closing a city browser before retrying |

---

## Troubleshooting

### `BrowserCreateError: BROWSER_CREATE_FAILED`
The Chromium process inside Docker died during startup. Causes and fixes:
1. **Not enough RAM** → Docker Desktop → Settings → Resources → Memory → set to 4 GB+
2. **Not enough shared memory** → Add `shm_size: '512mb'` to `docker-compose.yml`
3. Check logs: `docker compose logs --tail=50`

### Everything is flagged as a login page
This was a historical bug (now fixed). If you see this with the current code, the URL-first logic in `is_login_page` should prevent it. Check that you are running the latest version of `scraper.py`.

### CLI commands (`stop`, `skip`, etc.) are not responding
This was a historical bug caused by `wait_for_manual_solve` calling `input()` and competing with `console_listener` for stdin. The fix ensures `console_listener` is the sole stdin reader. If commands are not responding, check that you are on the latest `scraper.py` and `main.py`.

### Scraper resumes but scrapes nothing
This was caused by `save_checkpoint` being called with a price value instead of a bracket index. The fix in `scrape_city_brackets` ensures only the bracket enumeration index (0–4) is ever written. If you have an old checkpoint file from before this fix, delete it: `del checkpoints/checkpoint_YYYY-MM-DD.json`.

### Turnstile click lands on the results page
This was caused by `_auto_solve_interactive_turnstile` not checking whether the challenge was already solved before clicking. The fix checks for the challenge string in the HTML before any mouse movement and returns early if it is gone.

### `docker compose` command not found
On older Docker versions the command is `docker-compose` (with hyphen). Try `docker-compose up -d`.

### Data looks duplicated in the CSV
Most likely caused by running without `--resume` after an interrupted run that had already written some data. The scraper without `--resume` deletes the day's CSV before starting — but only at the start of the run, not before each city. If you interrupted after city 1 was already complete and then re-ran without `--resume`, city 1 will be doubled. Solution: delete the CSV file and re-run from scratch, or use `--resume` consistently.
