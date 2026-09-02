"""
Backfill / repair normalised locations on existing jobs.

Scraped locations are a mix of cities, districts and transliteration variants
("Yoqneam Illit" vs "Yokneam Ilit"). server/etl/locations.normalize_location()
now runs inline in the extractor for every new job; this script applies the
same normalisation to rows already in the database:

1. Rewrites jobs.location (canonical city, or NULL for district-only rows) and
   sets jobs.region (Tel Aviv / Center / Sharon / Haifa / North / South /
   Jerusalem) in PostgreSQL.
2. Re-embeds the changed jobs in ChromaDB so vector metadata and search text
   match. Skip with --skip-chroma if you only need PostgreSQL updated.

Pure DB + local embedding model, no browser or network. Set DB_HOST=localhost
in .env when running outside Docker. Inside Docker, run in the `scheduler`
container:

    docker compose exec scheduler python -m scripts.backfill_locations [--dry-run] [--skip-chroma]
"""
from __future__ import annotations

import argparse
import logging
import time

from server.db.postgres import (
    fetch_all_job_locations,
    fetch_jobs_by_ids,
    get_connection,
    update_job_locations,
)
from server.etl.locations import normalize_location

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

_CHROMA_BATCH = 200   # jobs per embedding batch


def _plan_changes(rows: list[dict]) -> list[tuple]:
    """Return (id, new_location, new_region) for every row that changes.

    Normalisation reads jobs.location, which this script also overwrites — a
    district row ("Center District") becomes location=NULL, region="Center".
    Once location is NULL the original string is gone, so such rows are left
    alone on re-runs (skip when location is falsy). New jobs are normalised at
    ingest by the extractor, so the backfill only needs the legacy non-NULL rows.
    """
    changed = []
    for row in rows:
        if not row["location"]:
            continue
        city, region = normalize_location(row["location"])
        if city != row["location"] or region != row["region"]:
            changed.append((row["id"], city, region))
    return changed


def _log_samples(rows_by_id: dict, changed: list[tuple], n: int = 25) -> None:
    for job_id, city, region in changed[:n]:
        old = rows_by_id[job_id]
        log.info("  %s  %r → city=%r region=%r", job_id, old["location"], city, region)
    if len(changed) > n:
        log.info("  … and %d more", len(changed) - n)


def _reembed(conn, ids: list[str]) -> None:
    from server.db.chroma import init_chroma, upsert_jobs

    collection = init_chroma()
    total = 0
    for start in range(0, len(ids), _CHROMA_BATCH):
        batch = ids[start:start + _CHROMA_BATCH]
        jobs = fetch_jobs_by_ids(conn, batch)   # reads the freshly-updated rows
        total += upsert_jobs(collection, jobs)
        log.info("  re-embedded %d/%d jobs", min(start + _CHROMA_BATCH, len(ids)), len(ids))
    log.info("ChromaDB: %d vectors upserted across %d jobs", total, len(ids))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would change, write nothing")
    ap.add_argument("--skip-chroma", action="store_true",
                    help="update PostgreSQL only, leave ChromaDB untouched")
    args = ap.parse_args()

    start = time.time()
    conn = get_connection()

    rows = fetch_all_job_locations(conn)
    rows_by_id = {r["id"]: r for r in rows}
    changed = _plan_changes(rows)

    log.info("=== %d/%d jobs have a location to normalise ===", len(changed), len(rows))
    if not changed:
        conn.close()
        return
    _log_samples(rows_by_id, changed)

    if args.dry_run:
        log.info("dry run — nothing written (%.1fs)", time.time() - start)
        conn.close()
        return

    update_job_locations(conn, changed)
    conn.commit()
    log.info("PostgreSQL: %d job rows updated", len(changed))

    if not args.skip_chroma:
        _reembed(conn, [job_id for job_id, _, _ in changed])

    conn.close()
    log.info("=== done in %.1fs ===", time.time() - start)


if __name__ == "__main__":
    main()
