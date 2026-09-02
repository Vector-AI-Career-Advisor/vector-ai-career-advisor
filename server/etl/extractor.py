"""LLM-based job description extraction using Claude."""
from __future__ import annotations

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import anthropic

from server.web.core.config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
    EXTRACTION_PROMPT,
    VALID_ROLES,
    VALID_SENIORITY,
)
from .skills import normalize_skills
from .utils import company_slug

log = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ── Description pre-processing ────────────────────────────────────────────────
#
# LinkedIn descriptions arrive with boilerplate, bullet-point noise, and
# occasional HTML artefacts. Stripping these reduces inference time without
# losing any structured information the model needs.

_MAX_CHARS = 10_000

_BOILERPLATE_PATTERNS = [
    r"(equal\s+opportunity|eeo|affirmative\s+action).{0,300}",
    r"linkedin is committed.{0,200}",
    r"(we offer|our benefits include|what we offer)[:\s].{0,400}",
]
_BOILERPLATE_RE = re.compile("|".join(_BOILERPLATE_PATTERNS), re.DOTALL | re.IGNORECASE)


def _preprocess_description(raw: str) -> str:
    """
    Clean and intelligently truncate a raw LinkedIn description.

    Strips HTML artefacts, collapses whitespace, removes boilerplate, then
    keeps the first 70 % and last 30 % if still over _MAX_CHARS so that both
    the intro and the requirements section (usually at the end) are preserved.
    """
    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = _BOILERPLATE_RE.sub("", text)
    text = re.sub(r" {2,}", " ", text).strip()

    if len(text) <= _MAX_CHARS:
        return text

    head = int(_MAX_CHARS * 0.70)
    tail = _MAX_CHARS - head
    return text[:head] + "\n\n[...]\n\n" + text[-tail:]


# ── Public extraction API ─────────────────────────────────────────────────────

def extract_with_claude(title: str, description: str) -> dict:
    """Send a job title + description to Claude and return a structured dict."""
    if not description or description == "N/A":
        return _empty_extraction()

    processed = _preprocess_description(description)

    for attempt in range(3):
        try:
            resp = _client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=1024,
                temperature=0,
                system=EXTRACTION_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Job Title: {title}\n\n"
                            f"Job Description:\n{processed}\n\n"
                            "JSON:"
                        ),
                    }
                ],
            )
            raw = resp.content[0].text.strip()
            return _parse_and_validate(raw, title)

        except json.JSONDecodeError as e:
            log.warning("Claude JSON parse error (attempt %d/3): %s", attempt + 1, e)
            if attempt == 2:
                return _empty_extraction()
            time.sleep(2)

        except anthropic.APIError as e:
            log.warning("Claude API error (attempt %d/3): %s", attempt + 1, e)
            if attempt == 2:
                return _empty_extraction()
            time.sleep(5)

    return _empty_extraction()


def extract_all_parallel(stubs: list[dict]) -> list[dict]:
    """
    Run LLM-based extraction with a small thread pool.
    """
    if not stubs:
        return []

    valid_stubs, skipped_count = _filter_valid_stubs(stubs)
    if not valid_stubs:
        return []

    results: list[Optional[dict]] = [None] * len(valid_stubs)

    def _worker(idx: int, stub: dict) -> tuple[int, dict]:
        log.info(
            "[%d/%d] Extracting: %s | %s",
            idx + 1, len(valid_stubs), stub["title"], stub["company"],
        )
        return idx, extract_with_claude(stub["title"], stub["raw_description"])

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_worker, i, stub): i for i, stub in enumerate(valid_stubs)}
        for future in as_completed(futures):
            i = futures[future]
            try:
                idx, extracted = future.result()
                results[idx] = extracted
            except Exception as e:
                log.error("Extraction worker failed for stub %d: %s", i, e)
                results[i] = _empty_extraction()

    jobs = []
    for stub, extracted in zip(valid_stubs, results):
        if extracted is None:
            extracted = _empty_extraction()
        job = {
            "id":              stub["id"],
            "title":           stub["title"],
            "company":         stub["company"],
            "location":        stub["location"],
            "url":             stub["url"],
            "role":            extracted["role"],
            "seniority":       extracted["seniority"],
            "description":     extracted["description"],
            "skills_must":     extracted["skills_must"],
            "skills_nice":     extracted["skills_nice"],
            "yearsexperience": extracted["yearsexperience"],
            "past_experience": extracted["past_experience"],
            "posted_at":       stub.get("posted_at"),
            "keyword":         stub["keyword"],
            "source":          "linkedin",
            "logo_source_url": stub.get("logo_source_url"),
            "company_slug":    company_slug(stub["company"]),
        }
        log.info(
            "  ✓ %s | %s | exp: %s",
            job["role"], job["seniority"],
            f"{job['yearsexperience']}yr" if job["yearsexperience"] else "?",
        )
        jobs.append(job)

    log.info(
        "Extraction complete — %d/%d jobs processed (%d skipped).",
        len(jobs), len(stubs), skipped_count,
    )
    return jobs


# ── Internal helpers ──────────────────────────────────────────────────────────

def _filter_valid_stubs(stubs: list[dict]) -> tuple[list[dict], int]:
    valid, skipped = [], 0
    for stub in stubs:
        desc = stub.get("raw_description", "")
        if not desc or desc == "N/A":
            log.warning(
                "Skipping '%s' @ '%s' — no description.", stub["title"], stub["company"]
            )
            skipped += 1
        else:
            valid.append(stub)
    if skipped:
        log.info("Skipped %d stub(s) with missing descriptions.", skipped)
    return valid, skipped


def _parse_and_validate(raw: str, title: str) -> dict:
    """Strip markdown fences, extract JSON, validate and return."""
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        raw = match.group(0)

    data = json.loads(raw)
    return _validate(data, title)


def _empty_extraction() -> dict:
    return {
        "role":            "Other",
        "seniority":       "Not specified",
        "description":     None,
        "yearsexperience": None,
        "skills_must":     [],
        "skills_nice":     [],
        "past_experience": [],
    }


def _validate(data: dict, title: str) -> dict:
    """Validate and normalise a raw extraction dict."""
    empty  = _empty_extraction()
    result = {}

    for key, default in empty.items():
        # LLM sometimes returns "experience" instead of "yearsexperience"
        llm_key = "experience" if key == "yearsexperience" else key
        val     = data.get(llm_key, data.get(key, default))

        if key in {"skills_must", "skills_nice"}:
            result[key] = normalize_skills(val)

        elif key == "past_experience":
            result[key] = [str(v) for v in val if v] if isinstance(val, list) else []

        elif key == "yearsexperience":
            try:
                result[key] = int(val) if val is not None else None
            except (ValueError, TypeError):
                result[key] = None

        elif key == "role":
            result[key] = str(val).strip() if val in VALID_ROLES else _infer_role(title)

        elif key == "seniority":
            result[key] = str(val).strip() if val in VALID_SENIORITY else "Not specified"

        else:
            result[key] = str(val).strip() if val else None

    _apply_seniority_heuristic(result)
    return result


def _apply_seniority_heuristic(result: dict) -> None:
    """
    Override seniority based on years of experience ONLY when the LLM
    returned 'Not specified'. Explicit LLM values are always preserved.
    """
    if result.get("seniority") != "Not specified":
        return

    yrs = result.get("yearsexperience")
    if yrs is None:
        return

    if yrs <= 3:
        new = "Junior"
    elif yrs <= 5:
        new = "Mid"
    else:
        new = "Senior"

    log.debug(
        "Seniority heuristic: 'Not specified' → '%s' (yearsexperience=%d)", new, yrs
    )
    result["seniority"] = new


def _infer_role(title: str) -> str:
    """Keyword-based role fallback when the LLM returns an unrecognised value."""
    t = title.lower()
    checks = [
        (["client", "front-end", "front end", "ui developer", "react developer",
          "angular developer", "vue developer", "web developer"],        "Frontend"),
        (["server", "back-end", "back end", "server-side", "node developer"],   "Backend"),
        (["fullstack", "full-stack", "full stack"],                               "Fullstack"),
        (["machine learning", "deep learning", "nlp", "computer vision",
          "llm", "ai engineer", "ml engineer", "artificial intelligence"],        "AI / ML"),
        (["data scientist"],                                                       "Data Scientist"),
        (["data engineer", "etl", "pipeline engineer"],                           "Data Engineer"),
        (["data analyst", "bi developer", "business intelligence"],               "Data Analyst"),
        (["devops", "cloud engineer", "sre", "site reliability",
          "platform engineer", "infrastructure engineer"],                        "DevOps / Cloud"),
        (["mobile", "android", "ios", "flutter", "react native"],                 "Mobile"),
        (["qa ", "quality engineer", "automation engineer",
          "test engineer", "sdet"],                                               "QA / Automation"),
        (["security", "cyber", "infosec", "penetration", "appsec"],              "Security"),
        (["embedded", "firmware"],                                                 "Embedded / Firmware"),
        (["solutions architect", "solution architect", "system architect"],       "Solutions Architect"),
        (["team lead", "tech lead", "engineering manager"],                       "Team Lead"),
        (["software engineer", "software developer", "programmer",
          "developer", "engineer"],                                               "Software Development"),
    ]

    for keywords, role in checks:
        if any(k in t for k in keywords):
            return role

    if ("product" in t and "manager" in t) or any(
        k in t for k in ["product lead", "vp product", "head of product", "product owner"]
    ):
        return "Product Manager"

    return "Other"
