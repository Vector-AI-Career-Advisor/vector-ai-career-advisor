"""
Company logo images.

`download_logo` fetches one company's logo (from the media.licdn.com URL that the
scraper captured) and stores it as a file under config.LOGO_DIR.
`sync_company_logos` is the ETL entry point: given the companies seen in a load
batch, it fetches logos for the ones not already stored and records the outcome
in the `company_logos` table.

Pure HTTP — no browser. The content-type / size checks are what reject LinkedIn's
auth-wall HTML page when a logo URL is served to a logged-in context.
"""
from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor

import httpx

from server.web.core.config import LOGO_DIR
from server.db.postgres import fetch_logo_status, upsert_company_logo

log = logging.getLogger(__name__)

_EXT_BY_TYPE = {
    "image/png":     "png",
    "image/jpeg":    "jpg",
    "image/jpg":     "jpg",
    "image/webp":    "webp",
    "image/gif":     "gif",
    "image/svg+xml": "svg",
}
_MIN_BYTES = 256
_MAX_BYTES = 2 * 1024 * 1024
_TIMEOUT = 5
_MAX_WORKERS = 8
_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0 Safari/537.36"


def download_logo(slug: str, url: str, *, client: httpx.Client | None = None) -> str | None:
    """
    Fetch `url` and save it as ``<slug>.<ext>`` inside LOGO_DIR.
    Returns the file's basename on success, or None (not an image / too small /
    too large / network error).
    """
    own_client = client is None
    client = client or httpx.Client(timeout=_TIMEOUT, follow_redirects=True)
    try:
        resp = client.get(url, headers={"User-Agent": _UA})
        resp.raise_for_status()
        ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
        ext = _EXT_BY_TYPE.get(ctype)
        if ext is None or not (_MIN_BYTES <= len(resp.content) <= _MAX_BYTES):
            log.warning("logo %s rejected — type=%r, %d bytes", slug, ctype, len(resp.content))
            return None

        os.makedirs(LOGO_DIR, exist_ok=True)
        # one canonical file per slug — drop any stale extension from a prior fetch
        for old_ext in set(_EXT_BY_TYPE.values()):
            stale = os.path.join(LOGO_DIR, f"{slug}.{old_ext}")
            if old_ext != ext and os.path.exists(stale):
                os.remove(stale)

        fname = f"{slug}.{ext}"
        with open(os.path.join(LOGO_DIR, fname), "wb") as fh:
            fh.write(resp.content)
        return fname
    except Exception as exc:  # noqa: BLE001 — any failure just means "no logo"
        log.warning("logo %s fetch failed — %s", slug, exc)
        return None
    finally:
        if own_client:
            client.close()


def sync_company_logos(conn, companies: dict[str, tuple[str | None, str]]) -> int:
    """
    `companies` maps company_slug -> (display_name, source_url).
    Fetches a logo for every slug not already status='ok' in company_logos.
    Returns the number of logos newly stored.
    """
    if not companies:
        return 0

    already = fetch_logo_status(conn)
    todo = [
        (slug, name, url)
        for slug, (name, url) in companies.items()
        if url and already.get(slug) != "ok"
    ]
    if not todo:
        return 0

    # Downloads run concurrently (pure network + per-slug file writes); the DB
    # upserts stay on this thread — the psycopg connection isn't thread-safe.
    stored = 0
    with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
            results = pool.map(
                lambda t: (t[0], t[1], t[2], download_logo(t[0], t[2], client=client)),
                todo,
            )
            for slug, name, url, fname in results:
                upsert_company_logo(conn, slug, name, fname, url,
                                    status="ok" if fname else "missing")
                stored += bool(fname)
    return stored
