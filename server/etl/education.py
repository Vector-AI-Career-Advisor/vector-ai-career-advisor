"""
Education-level normalisation.

`jobs.education` is a `TEXT[]` of free-text degree requirements the LLM extractor
pulls from each posting — "BSc in Computer Science", "Master's degree in CS or
related field — preferred", "MSc — advantage", "Minimum GPA of 85", "Degree or
equivalent relevant experience". That free text is unusable for an exact filter,
so `normalize_education_level()` folds each list onto ONE canonical minimum
degree level:

  "none"     — no degree strictly required (posting is silent, waives the degree,
               or only lists degrees as an advantage/preference)
  "bachelor" — a bachelor's (BSc / BA / "degree in X") is required
  "master"   — a master's (MSc / MA / MBA / "graduate degree") is required
  "phd"      — a doctorate is required

The ETL stores this as jobs.education_level (derived at ingest, never extracted);
the sidebar's Education filter matches against it. Kept in sync with the
client-side copy in client/src/lib/educationLevel.ts.

`normalize_education_level` is a pure function of the `education` list, so the
backfill (scripts/backfill_education_level.py) can be re-run safely and
re-scraped jobs never drift.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

EDUCATION_LEVELS = ("none", "bachelor", "master", "phd")
_RANK = {level: i for i, level in enumerate(EDUCATION_LEVELS)}

# An entry that only *prefers* a degree rather than requiring it. "or equivalent
# … experience" means a degree OR experience is accepted, so the degree is not
# mandatory either.
_OPTIONAL_RE = re.compile(
    r"\b(?:advantage|preferred|preferable|nice[ -]to[ -]have|bonus|"
    r"a\s+plus|plus\b|ideally|an?\s+asset|desirable|would\s+be\s+a\s+plus)\b"
    r"|or\s+equivalent\b[^.]*\bexperience\b",
    re.IGNORECASE,
)

_PHD_RE = re.compile(r"\b(?:ph\.?\s?d|doctora(?:te|l))\b", re.IGNORECASE)
_MASTER_RE = re.compile(
    r"\b(?:master'?s?|m\.?\s?sc|m\.?\s?a\b|mba|graduate\s+degree)\b",
    re.IGNORECASE,
)
# Bachelor-*specific* tokens only.
_BACHELOR_RE = re.compile(
    r"\b(?:bachelor'?s?|b\.?\s?sc|b\.?\s?a\b|b\.?\s?eng|undergraduate)\b",
    re.IGNORECASE,
)
# A generic "has a degree" signal with no level word — implies at least a
# bachelor's, but only when no higher level is also named ("Master's degree in
# X" must not read as bachelor).
_DEGREE_RE = re.compile(
    r"\b(?:degree\s+in|academic\s+degree|(?:college|university)\s+degree|"
    r"'s\s+degree|\bdegree\b)\b",
    re.IGNORECASE,
)


def classify_requirement(entry: str) -> tuple[Optional[str], bool]:
    """Return (level, is_required) for a single free-text degree string.

    `level` is the *lowest* degree named in the entry — "Master's degree or PhD"
    means a master's is the floor — or None when the entry names no recognisable
    degree ("Minimum GPA of 85", "Strong academic background").
    """
    text = str(entry or "").strip()
    if not text:
        return (None, True)

    required = not _OPTIONAL_RE.search(text)

    levels = []
    if _BACHELOR_RE.search(text):
        levels.append("bachelor")
    if _MASTER_RE.search(text):
        levels.append("master")
    if _PHD_RE.search(text):
        levels.append("phd")
    if not levels and _DEGREE_RE.search(text):
        levels.append("bachelor")

    level = min(levels, key=lambda lvl: _RANK[lvl]) if levels else None
    return (level, required)


def normalize_education_level(entries: Optional[Iterable[str]]) -> str:
    """Fold a jobs.education list onto one minimum degree level (see module doc).

    None / empty / all-optional / all-unrecognised → "none".
    """
    if not entries:
        return "none"

    required_levels = [
        level
        for level, required in (classify_requirement(e) for e in entries)
        if required and level is not None
    ]
    if not required_levels:
        return "none"
    return min(required_levels, key=lambda lvl: _RANK[lvl])
