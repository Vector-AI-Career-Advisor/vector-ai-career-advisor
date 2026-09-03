"""
Shared pipeline steps used by both the Airflow DAG and the local runner.
"""
from __future__ import annotations

import logging
import time
from typing import List
from selenium.common.exceptions import InvalidSessionIdException, WebDriverException
from server.web.core.config import DAILY_TARGET, KEYWORDS, MAX_EMPTY_KEYWORD_STREAK
from server.db.chroma import get_existing_ids, init_chroma, upsert_jobs
from server.db.postgres import (
    count_jobs_today,
    fetch_all_ids,
    fetch_jobs_missing_from_chroma,
    get_connection,
    init_db,
    insert_jobs,
    refresh_job_count_stat,
)
from .extractor import extract_all_parallel
from .logos import sync_company_logos
from .scraper import build_driver, scrape_keyword
from .utils import company_slug

log = logging.getLogger(__name__)


# ── Step 1: Scrape ────────────────────────────────────────────────────────────

def run_scrape(
    daily_target: int = DAILY_TARGET,
    max_empty_streak: int = MAX_EMPTY_KEYWORD_STREAK,
) -> List[dict]:
    """
    Scrape LinkedIn for new jobs up to `daily_target` per day.
    Returns a list of raw stub dicts (with raw_description + posted_at).
    Stubs where no description was fetched are filtered out here so that
    downstream steps never waste an API call on empty content.

    If `max_empty_streak` keywords in a row yield no new jobs the scrape gives
    up early — LinkedIn is likely auth-walling or the browser session is dead,
    so grinding through the rest of KEYWORDS just wastes time. Pass 0 to disable.
    """
    conn          = get_connection()
    init_db(conn)
    scraped_today = count_jobs_today(conn)
    remaining     = daily_target - scraped_today

    log.info("Today's progress: %d/%d jobs scraped.", scraped_today, daily_target)

    if remaining <= 0:
        log.info("Daily target already reached — nothing to scrape.")
        conn.close()
        return []

    seen_ids = fetch_all_ids(conn)
    conn.close()

    driver = build_driver()
    stubs  = []
    empty_streak = 0

    for keyword in KEYWORDS:
        if len(stubs) >= remaining:
            break

        count_before = len(stubs)
        try:
            for stub in scrape_keyword(driver, keyword, seen_ids, remaining - len(stubs)):
                raw_desc = stub.get("raw_description", "")
                if not raw_desc or raw_desc == "N/A":
                    log.warning(
                        "Dropping stub '%s' @ '%s' — no description fetched.",
                        stub["title"], stub["company"],
                    )
                    continue

                if stub.get("posted_at"):
                    stub["posted_at"] = stub["posted_at"]  # keep as date object; str() in insert

                stubs.append(stub)
                log.info(
                    "Scraped [%d/%d]: %s | %s",
                    len(stubs), remaining, stub["title"], stub["company"],
                )

        except (InvalidSessionIdException, WebDriverException) as e:
            log.warning("Browser crashed (%s) — rebuilding driver...", e)
            try:
                driver.quit()
            except Exception:
                pass
            time.sleep(3)
            driver = build_driver()

        except Exception as e:
            log.error("Error scraping keyword '%s': %s", keyword, e)

        if len(stubs) > count_before:
            empty_streak = 0
        else:
            empty_streak += 1
            if max_empty_streak and empty_streak >= max_empty_streak:
                log.warning(
                    "No new jobs after %d keywords in a row — ending scrape early.",
                    empty_streak,
                )
                break

    try:
        driver.quit()
    except Exception:
        pass

    log.info("Scrape complete — %d stubs collected (descriptions present).", len(stubs))
    return stubs


# ── Step 2: Extract ───────────────────────────────────────────────────────────

def run_extract(stubs: List[dict]) -> List[dict]:
    """
    Run extraction on all stubs in parallel.
    Returns a list of fully structured job dicts ready for storage.
    """
    if not stubs:
        log.info("No stubs to extract.")
        return []

    return extract_all_parallel(stubs)


# ── Step 3a: Load PostgreSQL ──────────────────────────────────────────────────

def run_load_postgres(jobs: List[dict]) -> int:
    """Insert jobs into PostgreSQL. Returns number of rows inserted."""
    if not jobs:
        log.info("No jobs to insert into PostgreSQL.")
        return 0

    seen: set = set()
    unique_jobs: List[dict] = []
    for job in jobs:
        job_id = job.get("id")
        if job_id and job_id in seen:
            log.warning("Duplicate job ID in batch, skipping: %s", job_id)
            continue
        if job_id:
            seen.add(job_id)
        unique_jobs.append(job)

    conn     = get_connection()
    init_db(conn)
    inserted = insert_jobs(conn, unique_jobs)
    refresh_job_count_stat(conn)

    # One logo per company, fetched once. Build {slug: (name, source_url)} from
    # this batch and let sync_company_logos skip the companies already stored.
    companies: dict[str, tuple[str, str]] = {}
    for job in unique_jobs:
        slug = company_slug(job.get("company"))
        if slug and job.get("logo_source_url"):
            companies.setdefault(slug, (job["company"], job["logo_source_url"]))
    try:
        stored = sync_company_logos(conn, companies)
        log.info("Company logos: %d new.", stored)
    except Exception:
        log.exception("Company-logo sync failed (continuing).")

    conn.close()
    return inserted


# ── Step 3b: Load ChromaDB ────────────────────────────────────────────────────

def run_load_chroma() -> int:
    """
    Backfill ChromaDB with any jobs that exist in PostgreSQL but are missing
    from the vector store. Returns number of vectors upserted.
    """
    collection     = init_chroma()
    conn           = get_connection()
    raw_ids        = get_existing_ids(collection)
    chroma_job_ids = {vid.rsplit("_", 1)[0] for vid in raw_ids}
    missing        = fetch_jobs_missing_from_chroma(conn, chroma_job_ids)
    conn.close()

    if not missing:
        log.info("ChromaDB is up to date — nothing to backfill.")
        return 0

    upserted = upsert_jobs(collection, missing)
    return upserted
