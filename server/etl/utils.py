from __future__ import annotations
import re
import unicodedata
from datetime import datetime, timedelta, timezone


# ── Company identity ──────────────────────────────────────────────────────────

_BLANK_COMPANY = {"", "n/a", "na", "none", "unknown"}


def company_slug(name: str | None) -> str | None:
    """
    Normalise a company name into a stable slug used as the key for a company's
    stored logo (see `company_logos` table). Returns None for blank / placeholder
    names so the caller can skip them.

    Known limitation: "Google" and "Google LLC" produce different slugs.
    """
    if not name or name.strip().lower() in _BLANK_COMPANY:
        return None
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug or None


# ── Formatting ────────────────────────────────────────────────────────────────

def fmt(seconds: float) -> str:
    """Format a duration in seconds to a readable string."""
    if seconds >= 60:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    return f"{seconds:.1f}s"


# ── Date parsing ──────────────────────────────────────────────────────────────

def parse_posted_date(text: str):
    """
    Parse a human-readable posted-date string (English or Hebrew) into a date.
    Returns None if the string cannot be parsed.
    """
    if not text:
        return None

    text = text.strip()
    now  = datetime.now(timezone.utc).replace(tzinfo=None)

    # Try ISO format first
    iso = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if iso:
        try:
            return datetime.strptime(iso.group(1), "%Y-%m-%d").date()
        except ValueError:
            pass

    num_match = re.search(r"(\d+)", text)
    n = int(num_match.group(1)) if num_match else 1
    t = text.lower()

    if any(k in t for k in ("שעה", "שעות", "hour")):
        return (now - timedelta(hours=n)).date()
    if any(k in t for k in ("יום", "ימים", "day")):
        return (now - timedelta(days=n)).date()
    if any(k in t for k in ("שבוע", "שבועות", "week")):
        return (now - timedelta(weeks=n)).date()
    if any(k in t for k in ("חודש", "חודשים", "month")):
        return (now - timedelta(days=n * 30)).date()
    if any(k in t for k in ("עכשיו", "just", "moments")):
        return now.date()

    return None


# ── ChromaDB metadata ─────────────────────────────────────────────────────────

def build_chroma_metadata(job: dict) -> dict:
    """
    Build a ChromaDB-compatible metadata dict (scalar values only).
    Lists are joined as comma-separated strings.
    """
    scalar_fields = ("id", "title", "role", "seniority", "company",
                     "location", "url", "yearsexperience", "keyword", "source",
                     "company_slug")
    list_fields   = ("skills_must", "skills_nice", "past_experience")

    meta = {}

    for f in scalar_fields:
        val = job.get(f)
        if val is not None:
            meta[f] = int(val) if f == "yearsexperience" else str(val)
        else:
            meta[f] = ""

    for f in list_fields:
        val = job.get(f)
        meta[f] = ", ".join(str(v) for v in val) if isinstance(val, list) and val else ""

    meta["posted_at"] = str(job["posted_at"]) if job.get("posted_at") else ""

    return meta
