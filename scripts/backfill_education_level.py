"""
Backfill / repair the derived jobs.education_level on existing jobs.

server/etl/education.normalize_education_level() folds a job's free-text
`education` list ("BSc in Computer Science", "MSc — advantage", …) onto one
minimum degree level (none | bachelor | master | phd). It now runs inline in the
extractor for every new job; this script applies the same derivation to rows
already in the database:

1. Rewrites jobs.education_level in PostgreSQL for every row where the derived
   value differs from what's stored (NULL / empty `education` → "none").
2. Re-embeds the changed jobs in ChromaDB so vector metadata matches. Skip with
   --skip-chroma if you only need PostgreSQL updated.

Pure DB derivation — no LLM / network / browser. Idempotent: a second --dry-run
reports 0 changes. Set DB_HOST=localhost in .env when running outside Docker.
Inside Docker, run in the `scheduler` container:

    docker compose exec scheduler python -m scripts.backfill_education_level [--dry-run] [--skip-chroma] [--limit N]
"""
from __future__ import annotations

import argparse
import logging
import time

from server.db.postgres import (
    fetch_all_job_education,
    fetch_jobs_by_ids,
    get_connection,
    update_job_education_level,
)
from server.etl.education import normalize_education_level

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

_CHROMA_BATCH = 200   # jobs per embedding batch


def _plan_changes(rows: list[dict]) -> list[tuple]:
    """Return (id, new_level) for every row whose derived level differs."""
    changed = []
    for row in rows:
        new_level = normalize_education_level(row["education"])
        if new_level != row["education_level"]:
            changed.append((row["id"], new_level))
    return changed


def _log_samples(rows_by_id: dict, changed: list[tuple], n: int = 25) -> None:
    for job_id, level in changed[:n]:
        old = rows_by_id[job_id]
        log.info("  %s  %r  %s → %s", job_id, old["education"], old["education_level"], level)
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
    ap.add_argument("--limit", type=int, default=0,
                    help="process at most N changed rows (0 = all)")
    args = ap.parse_args()

    start = time.time()
    conn = get_connection()

    rows = fetch_all_job_education(conn)
    rows_by_id = {r["id"]: r for r in rows}
    changed = _plan_changes(rows)
    if args.limit:
        changed = changed[: args.limit]

    log.info("=== %d/%d jobs need an education_level update ===", len(changed), len(rows))
    if not changed:
        conn.close()
        return
    _log_samples(rows_by_id, changed)

    if args.dry_run:
        log.info("dry run — nothing written (%.1fs)", time.time() - start)
        conn.close()
        return

    update_job_education_level(conn, changed)
    conn.commit()
    log.info("PostgreSQL: %d job rows updated", len(changed))

    if not args.skip_chroma:
        _reembed(conn, [job_id for job_id, _ in changed])

    conn.close()
    log.info("=== done in %.1fs ===", time.time() - start)


if __name__ == "__main__":
    main()
