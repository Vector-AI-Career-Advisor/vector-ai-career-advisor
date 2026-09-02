"""
Backfill / repair per-company logo images.

1. Sets jobs.company_slug on every row where it is NULL, using the same
   utils.company_slug() the ETL insert path uses.
2. (Re)downloads company logos from company_logos.source_url into
   server/web/static/logos/, recording the outcome in company_logos.

Steady-state logo population happens inline in the ETL (run_load_postgres →
sync_company_logos); this script only backfills company_slug and retries
companies stuck at status='missing' (or, with --force, re-fetches every company
that has a source_url on file).

Pure HTTP + DB, no browser. Set DB_HOST=localhost in .env when running outside
Docker. Run in the `scheduler` container — it bind-mounts the repo (so
`scripts/` is present) and shares server/web/static/logos with `server`:

    docker compose exec scheduler python -m scripts.backfill_logos [--force]
"""
from __future__ import annotations

import argparse
import logging
import time

import httpx

from server.db.postgres import (
    backfill_company_slugs,
    fetch_companies_needing_logo,
    get_connection,
    upsert_company_logo,
)
from server.etl.logos import download_logo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true",
                    help="re-download every company that has a source_url, not just status='missing'")
    args = ap.parse_args()

    start = time.time()
    conn = get_connection()

    updated = backfill_company_slugs(conn)
    log.info("company_slug set on %d job rows", updated)

    companies = fetch_companies_needing_logo(conn, force=args.force)
    log.info("=== %d companies need a logo ===", len(companies))
    if not companies:
        conn.close()
        return

    stored = missing = 0
    with httpx.Client(timeout=10, follow_redirects=True) as client:
        for i, (slug, name, url) in enumerate(companies, 1):
            fname = download_logo(slug, url, client=client)
            upsert_company_logo(
                conn, slug, name, fname, url,
                status="ok" if fname else "missing",
            )
            if fname:
                stored += 1
            else:
                missing += 1
            log.info("[%d/%d] %s → %s", i, len(companies), slug, fname or "missing")
            if i % 25 == 0:
                conn.commit()
            time.sleep(0.2)   # be gentle with the CDN

    conn.commit()
    conn.close()
    log.info("=== done in %.1fs — %d stored, %d missing ===",
             time.time() - start, stored, missing)


if __name__ == "__main__":
    main()
