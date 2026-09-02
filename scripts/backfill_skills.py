"""
Backfill / repair skill-string casing on existing jobs.

Early rows were stored with whatever casing the LLM returned ("react", "REACT",
"rest apis"). server/etl/skills.normalize_skills() now runs inline in the
extractor for every new job; this script applies the same normalisation to rows
already in the database:

1. Rewrites jobs.skills_must / jobs.skills_nice in PostgreSQL.
2. Re-embeds the changed jobs in ChromaDB (full-text + per-field vectors) so
   vector metadata and search text match the cleaned values. Skip with
   --skip-chroma if you only need PostgreSQL updated.

Pure DB + local embedding model, no browser or network. Set DB_HOST=localhost
in .env when running outside Docker. Inside Docker, run in the `scheduler`
container (it bind-mounts the repo and shares the Chroma volume):

    docker compose exec scheduler python -m scripts.backfill_skills [--dry-run] [--skip-chroma]
"""
from __future__ import annotations

import argparse
import logging
import time

from server.db.postgres import (
    fetch_all_job_skills,
    fetch_jobs_by_ids,
    get_connection,
    update_job_skills,
)
from server.etl.skills import normalize_skills

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

_CHROMA_BATCH = 200   # jobs per embedding batch


def _plan_changes(rows: list[dict]) -> list[tuple]:
    """Return (id, new_must, new_nice) for every row whose skills change."""
    changed = []
    for row in rows:
        new_must = normalize_skills(row["skills_must"])
        new_nice = normalize_skills(row["skills_nice"])
        if new_must != list(row["skills_must"]) or new_nice != list(row["skills_nice"]):
            changed.append((row["id"], new_must, new_nice))
    return changed


def _log_samples(rows_by_id: dict, changed: list[tuple], n: int = 15) -> None:
    for job_id, new_must, new_nice in changed[:n]:
        old = rows_by_id[job_id]
        if list(old["skills_must"]) != new_must:
            log.info("  %s  must: %s → %s", job_id, list(old["skills_must"]), new_must)
        if list(old["skills_nice"]) != new_nice:
            log.info("  %s  nice: %s → %s", job_id, list(old["skills_nice"]), new_nice)
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

    rows = fetch_all_job_skills(conn)
    rows_by_id = {r["id"]: r for r in rows}
    changed = _plan_changes(rows)

    log.info("=== %d/%d jobs have skills to normalise ===", len(changed), len(rows))
    if not changed:
        conn.close()
        return
    _log_samples(rows_by_id, changed)

    if args.dry_run:
        log.info("dry run — nothing written (%.1fs)", time.time() - start)
        conn.close()
        return

    update_job_skills(conn, changed)
    conn.commit()
    log.info("PostgreSQL: %d job rows updated", len(changed))

    if not args.skip_chroma:
        _reembed(conn, [job_id for job_id, _, _ in changed])

    conn.close()
    log.info("=== done in %.1fs ===", time.time() - start)


if __name__ == "__main__":
    main()
