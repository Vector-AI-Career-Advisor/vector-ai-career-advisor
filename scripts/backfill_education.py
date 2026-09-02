"""
Backfill jobs.education on rows that predate the field.

The `education` field was added to the LLM extractor after these rows were
scraped, and the raw job descriptions are no longer stored — only the short
`description` summary is. This script runs a focused, education-only extraction
(cheap, one small Claude call per job) over each job's title + stored summary
and writes any degree requirements it finds. Rows where nothing is found get an
empty array, so they are not retried on a re-run.

    docker compose exec scheduler python -m scripts.backfill_education [--dry-run] [--limit N] [--skip-chroma]

Needs ANTHROPIC_API_KEY. Pure API + DB, no browser.
"""
from __future__ import annotations

import argparse
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from server.db.postgres import (
    fetch_jobs_by_ids,
    fetch_jobs_missing_education,
    get_connection,
    update_job_education,
)
from server.etl.extractor import extract_education

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

_WORKERS = 4
_CHROMA_BATCH = 200


def _extract_all(rows: list[dict]) -> list[tuple]:
    """Return (id, education_list) for every row, in input order."""
    results: dict[str, list[str]] = {}

    def work(row: dict) -> tuple[str, list[str]]:
        text = " ".join(filter(None, [row.get("title"), row.get("description")]))
        return row["id"], extract_education(row.get("title") or "", text)

    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        futures = {pool.submit(work, r): r["id"] for r in rows}
        done = 0
        for fut in as_completed(futures):
            jid, edu = fut.result()
            results[jid] = edu
            done += 1
            if done % 25 == 0:
                log.info("  extracted %d/%d", done, len(rows))

    return [(r["id"], results.get(r["id"], [])) for r in rows]


def _reembed(conn, ids: list[str]) -> None:
    from server.db.chroma import init_chroma, upsert_jobs

    collection = init_chroma()
    total = 0
    for start in range(0, len(ids), _CHROMA_BATCH):
        batch = ids[start:start + _CHROMA_BATCH]
        total += upsert_jobs(collection, fetch_jobs_by_ids(conn, batch))
        log.info("  re-embedded %d/%d jobs", min(start + _CHROMA_BATCH, len(ids)), len(ids))
    log.info("ChromaDB: %d vectors upserted across %d jobs", total, len(ids))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="extract and report, write nothing")
    ap.add_argument("--limit", type=int, default=0, help="process at most N jobs (0 = all)")
    ap.add_argument("--skip-chroma", action="store_true", help="update PostgreSQL only")
    args = ap.parse_args()

    start = time.time()
    conn = get_connection()

    rows = fetch_jobs_missing_education(conn)
    if args.limit:
        rows = rows[: args.limit]
    log.info("=== %d jobs need an education backfill ===", len(rows))
    if not rows:
        conn.close()
        return

    updates = _extract_all(rows)
    with_edu = [(jid, edu) for jid, edu in updates if edu]
    log.info("found degree requirements on %d/%d jobs", len(with_edu), len(rows))
    for jid, edu in with_edu[:20]:
        log.info("  %s → %s", jid, edu)
    if len(with_edu) > 20:
        log.info("  … and %d more", len(with_edu) - 20)

    if args.dry_run:
        log.info("dry run — nothing written (%.1fs)", time.time() - start)
        conn.close()
        return

    # Only persist rows where something was found. Rows left NULL stay eligible
    # for the re-scrape backfill (insert_jobs' ON CONFLICT … COALESCE) and for a
    # future re-run of this script if the source text improves.
    if not with_edu:
        log.info("nothing to write (%.1fs)", time.time() - start)
        conn.close()
        return

    update_job_education(conn, with_edu)
    conn.commit()
    log.info("PostgreSQL: %d job rows updated", len(with_edu))

    if not args.skip_chroma:
        _reembed(conn, [jid for jid, _ in with_edu])

    conn.close()
    log.info("=== done in %.1fs ===", time.time() - start)


if __name__ == "__main__":
    main()
