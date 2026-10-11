"""
Samsung sitemap sweep
=====================

Finds priced Samsung Türkiye products that the category pass missed.

1. Read every child sitemap of ``config.SITEMAP_INDEX_URL`` (consumer b2c).
2. Take the model code from each product URL
   (``.../galaxy-a27-5g-blue-128gb-sm-a276bzbbtur/`` -> ``SM-A276BZBBTUR``).
3. Ask the card-detail endpoint about the codes not already scraped, in
   batches, and keep the models that have a price.
"""

import logging
import re
import time

import requests

import config
from product_fetcher import _parse_model

logger = logging.getLogger(__name__)

_LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
_CODE_RE = re.compile(r"[a-z]{2,3}-[a-z0-9]{6,}|[a-z]{2}\d{2}[a-z0-9]{6,}")


def _get(session, url, **kwargs):
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            resp = session.get(url, timeout=30, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            logger.warning("Sweep request failed (%s), attempt %d", exc, attempt)
            time.sleep(config.RETRY_BACKOFF * attempt)
    return None


def _model_codes(session) -> dict:
    """model code -> URL section (e.g. 'lifestyle-tvs')."""
    index = _get(session, config.SITEMAP_INDEX_URL)
    if index is None:
        return {}
    codes = {}
    for child in _LOC_RE.findall(index.text):
        resp = _get(session, child)
        if resp is None:
            continue
        for url in _LOC_RE.findall(resp.text):
            if "/tr/" not in url:
                continue
            last = url.rstrip("/").removesuffix("/buy").rsplit("/", 1)[-1]
            parts = last.split("-")
            for cand in ("-".join(parts[-2:]), parts[-1]):
                if _CODE_RE.fullmatch(cand):
                    codes.setdefault(cand.upper(), url.split("/tr/")[1].split("/")[0])
                    break
    return codes


def sweep(session, known_ids: set) -> list[dict]:
    """Return priced products from the sitemaps whose id is not in ``known_ids``."""
    codes = _model_codes(session)
    missing = [c for c in codes if c not in known_ids]
    logger.info("Sitemap sweep: %d model codes, %d not yet scraped", len(codes), len(missing))

    found = []
    for i in range(0, len(missing), config.SWEEP_BATCH):
        batch = missing[i:i + config.SWEEP_BATCH]
        resp = _get(session, config.CARD_DETAIL_URL, params={
            "siteCode": config.SITE_CODE, "modelList": ",".join(batch), "saleSkuYN": "N",
            "onlyRequestSkuYN": "Y", "keySummaryYN": "N", "specYN": "N", "commonCodeYN": "N",
        })
        if resp is None:
            continue
        try:
            families = ((resp.json().get("response") or {}).get("resultData") or {}).get("productList") or []
        except ValueError:
            continue
        wanted = set(batch)
        for family in families:
            for model in family.get("modelList") or []:
                code = (model.get("modelCode") or "").upper()
                if code not in wanted or code in known_ids:
                    continue
                record = _parse_model(family, model, f"Other ({codes.get(code, 'sitemap')})")
                if record is not None:
                    known_ids.add(code)
                    found.append(record)
        time.sleep(config.REQUEST_DELAY)
    logger.info("Sitemap sweep added %d priced products", len(found))
    return found
