"""Interview Tools — web-search-backed with Anthropic API fallback.

Two-layer strategy (mirrors how ChatGPT works):
  Layer 1: Search public sources (Reddit, LeetCode, GeeksforGeeks, Glassdoor).
           Extract community-reported questions + real links.
  Layer 2: If web search unavailable or returns little, call the Anthropic API
           to synthesise questions from training knowledge — labelled clearly
           as AI-generated, not confirmed past questions.

Always returns:
  - A direct Glassdoor interview page link for the company
  - Honest labels: "community-reported" or "AI-generated practice question"
  - Source links when available

SETUP:
  - SERPER_API_KEY  (optional) — https://serper.dev free tier gives 2500 searches/month
  - ANTHROPIC_API_KEY + ANTHROPIC_MODEL — already in your .env; used as fallback
"""
from __future__ import annotations

import os
import re
import urllib.parse

import anthropic
import requests
from langchain.tools import tool

# ── Config ─────────────────────────────────────────────────────────────────

SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
SERPER_URL     = "https://google.serper.dev/search"

_anthropic = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
_MODEL     = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

def _web_search(query: str, num: int = 8) -> list[dict]:
    """Return [{title, link, snippet}] from Serper (Google Search API). Returns [] on any failure."""
    if not SERPER_API_KEY:
        return []
    try:
        resp = requests.post(
            SERPER_URL,
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": num},
            timeout=10,
        )
        resp.raise_for_status()
        return [
            {"title": r.get("title", ""), "link": r.get("link", ""), "snippet": r.get("snippet", "")}
            for r in resp.json().get("organic", [])
        ]
    except Exception:
        return []


def _ask_claude(prompt: str, max_tokens: int = 800) -> str:
    """Call Claude and return the text response. Used as web-search fallback."""
    try:
        resp = _anthropic.messages.create(
            model=_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception:
        return ""


# Hand-curated Glassdoor company IDs.
# Format is always: https://www.glassdoor.com/Interview/{Slug}-Interview-Questions-{ID}.htm
# To find a missing ID: open glassdoor.com/Interview, search the company, copy the E-number from the URL.
_GLASSDOOR_IDS: dict[str, str] = {
    "fullpath":   "E2257168",
    "global-e":   "E3E4015786",
    "google":     "E9079",
    "meta":       "E40772",
    "amazon":     "E6036",
    "microsoft":  "E1651",
    "apple":      "E1138",
    "netflix":    "E11891",
    "monday":     "E2529809",
    "wix":        "E338054",
    "ironsource": "E778142",
}


def _glassdoor_interview_url(company: str) -> tuple[str, str]:
    """
    Return (direct_url, search_fallback_url) for a company's Glassdoor interview page.
    direct_url uses the known company ID when available; falls back to the search form otherwise.
    search_fallback_url always uses the search form so the user always has a working link.
    """
    key = company.lower().replace(" ", "-")
    search = (
        f"https://www.glassdoor.com/Interview/index.htm"
        f"?typedKeyword={urllib.parse.quote_plus(company)}&locT=N&locId=3"
    )
    gd_id = _GLASSDOOR_IDS.get(key)
    if gd_id:
        slug   = company.replace(" ", "-").title()
        direct = f"https://www.glassdoor.com/Interview/{slug}-Interview-Questions-{gd_id}.htm"
        return direct, search
    return search, search

def _format_sources(results: list[dict]) -> str:
    lines = [f"- [{r['title']}]({r['link']})" for r in results if r["link"]]
    return "\n".join(lines)


def _extract_questions_from_snippets(snippets: list[str]) -> list[str]:
    """
    Pull sentence-level question candidates out of search snippets.
    Very lightweight heuristic — the LLM does the real synthesis.
    """
    questions = []
    for s in snippets:
        for sentence in re.split(r"[.?!]\s+", s):
            sentence = sentence.strip()
            if len(sentence) > 20 and ("?" in sentence or sentence.lower().startswith(
                ("tell me", "how", "what", "why", "describe", "explain",
                 "design", "implement", "write", "given", "find", "solve",
                 "you are", "assume", "suppose", "walk me")
            )):
                questions.append(sentence.rstrip("?") + "?")
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique = []
    for q in questions:
        key = q.lower()
        if key not in seen:
            seen.add(key)
            unique.append(q)
    return unique[:20]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def search_interview_questions(company: str, role: str) -> str:
    """Search public sources for past interview questions at a specific company and role.

    Layer 1 — web search (Reddit, LeetCode Discuss, GeeksforGeeks, Glassdoor).
    Layer 2 — Anthropic API fallback when web search is unavailable or thin.
    Always returns a correct Glassdoor interview link. All questions are honestly labelled.

    Args:
        company: Company name, e.g. "Fullpath", "Meta", "Google".
        role:    Job role, e.g. "Junior Software Engineer", "Data Analyst".
    """
    glassdoor_direct, glassdoor_search = _glassdoor_interview_url(company)
    # ── Layer 1: web search ────────────────────────────────────────────────
    all_results: list[dict] = []
    seen_links: set[str] = set()
    for q in [
        f'"{company}" "{role}" interview questions experience',
        f'{company} {role} interview questions site:reddit.com',
        f'{company} {role} interview site:leetcode.com/discuss',
        f'site:geeksforgeeks.org "{company}" interview experience',
    ][:3]:
        for r in _web_search(q, num=5):
            if r["link"] and r["link"] not in seen_links:
                seen_links.add(r["link"])
                all_results.append(r)

    snippets      = [r["snippet"] for r in all_results if r["snippet"]]
    web_questions = _extract_questions_from_snippets(snippets)
    sources_text  = _format_sources(all_results[:8])

    # ── Layer 2: Anthropic API fallback (always fills gaps) ────────────────
    ai_questions: list[str] = []
    raw = _ask_claude(
        f"""You are an interview prep expert.

List 12 realistic interview questions for a {role} at {company}.
Draw from publicly known interview reports, community discussions, and industry patterns.

Format — one question per line with its type label, exactly like:
[Technical] Explain the difference between SQL joins.
[Behavioral] Tell me about a time you resolved a conflict on your team.
[System Design] How would you design a notifications service?

No preamble. No numbering. No explanations after the question.""",
        max_tokens=700,
    )
    if raw:
        ai_questions = [line.strip() for line in raw.splitlines() if line.strip()]

    # ── Assemble output ────────────────────────────────────────────────────
    lines = [
        f"## {company} — {role} Interview Prep",
        "",
        f"Glassdoor: {glassdoor_direct}",
        f"(Search fallback: {glassdoor_search})",
        "",
    ]

    if web_questions:
        lines += ["### Community-Reported Questions",
                  "*(sourced from Reddit, LeetCode Discuss, GeeksforGeeks, public blogs)*", ""]
        for q in web_questions:
            lines.append(f"- {q}")
        lines.append("")

    if ai_questions:
        header = "### Additional Practice Questions" if web_questions else "### Practice Questions"
        note   = (
            "*(AI-generated, based on publicly available interview reports and industry patterns)*"
            if web_questions
            else "*(AI-generated — no community reports found for this specific company/role. "
                 "Questions reflect typical patterns for this type of role.)*"
        )
        lines += [header, note, ""]
        for q in ai_questions:
            lines.append(f"- {q}")
        lines.append("")

    if sources_text:
        lines += ["### Sources", sources_text, ""]

    lines += [
        "---",
        "Community-reported questions come from public forums and are not verified by the company.",
        "AI-generated questions are practice material based on training data and industry patterns.",
    ]

    return "\n".join(lines)


@tool
def generate_interview_questions(company: str, role: str, num_questions: int = 12) -> str:
    """Generate AI practice interview questions for a company and role.

    Searches for the company's public tech stack first, then generates grounded questions.
    Clearly labelled as AI-generated practice material, not confirmed past questions.

    Args:
        company:       Target company, e.g. "Fullpath".
        role:          Target role, e.g. "Junior Software Engineer".
        num_questions: How many questions to generate (default 12).
    """
    glassdoor_direct, _ = _glassdoor_interview_url(company)

    context_results = _web_search(f"{company} tech stack engineering blog technologies used", num=5)
    context_text    = " ".join(r["snippet"] for r in context_results if r["snippet"])[:1200]

    raw = _ask_claude(
        f"""You are an interview prep coach.
Generate {num_questions} realistic interview questions for a {role} at {company}.

{'Company context from public sources: ' + context_text if context_text else ''}

Include a mix of:
- Technical / coding questions relevant to the role and the company stack
- System design questions (adjust depth for {role})
- Behavioral questions (STAR triggers)
- 1-2 company-specific questions about {company} product or engineering culture

Format — one per line with label:
[Technical] <question>
[System Design] <question>
[Behavioral] <question>
[Company] <question>

No preamble. No numbering. No explanations.""",
        max_tokens=700,
    )
    ai_questions = [line.strip() for line in (raw or "").splitlines() if line.strip()]

    lines = [
        f"## Practice Questions — {company} ({role})",
        "",
        f"Glassdoor: {glassdoor_direct}",
        "",
        "### Generated Questions",
        "*(AI-generated based on publicly available information about this company's tech stack",
        "and typical interview patterns for this role — not confirmed past questions)*",
        "",
    ]
    if ai_questions:
        for q in ai_questions:
            lines.append(f"- {q}")
    else:
        lines.append("*(Generation failed — please try again.)*")

    lines += ["", "---",
              f"For verified candidate experiences: {glassdoor_direct}"]
    return "\n".join(lines)


@tool
def get_interview_prep_guide(company: str, role: str) -> str:
    """Return a full interview preparation guide for a company and role.

    Covers: typical process, key topics to study, public resources, Glassdoor link.
    Uses web search for context and Anthropic API for synthesis.

    Args:
        company: Target company, e.g. "Fullpath".
        role:    Target role, e.g. "Junior Software Engineer".
    """
    glassdoor_direct, glassdoor_search = _glassdoor_interview_url(company)

    all_results: list[dict] = []
    seen: set[str] = set()
    for r in (
        _web_search(f"{company} interview process stages rounds {role}", num=5)
        + _web_search(f"{company} {role} interview topics technical skills", num=4)
    ):
        if r["link"] and r["link"] not in seen:
            seen.add(r["link"])
            all_results.append(r)

    sources_text     = _format_sources(all_results[:8])
    context_snippets = " ".join(r["snippet"] for r in all_results if r["snippet"])[:1200]

    raw = _ask_claude(
        f"""You are an interview prep expert.
Write a concise prep guide for a {role} at {company}.

{'Context from public sources: ' + context_snippets if context_snippets else ''}

Use these exact section headers and be specific:

### Typical Interview Process
(bullet list of stages)

### Key Topics to Study
(bullet list specific to {role} and {company} tech stack)

### Tips for {company}
(2-3 concrete tips based on {company} culture and engineering style)

No preamble. No filler.""",
        max_tokens=800,
    )

    lines = [
        f"## Interview Prep Guide — {company} ({role})",
        "",
        f"Glassdoor: {glassdoor_direct}",
        f"(Search fallback: {glassdoor_search})",
        "",
    ]

    if raw:
        lines.append(raw)
    else:
        lines += [
            "### Typical Interview Process",
            "- Recruiter / HR screen",
            "- Technical phone/video screen (30–60 min)",
            "- Take-home or timed coding challenge",
            "- On-site / virtual loop — coding, system design, behavioural",
            "- Offer / debrief call",
        ]

    lines += [
        "",
        "### Key Resources",
        "",
        f"- [Glassdoor — {company} Interviews]({glassdoor_direct})",
        "- [LeetCode Interview Discussions](https://leetcode.com/discuss/interview-question)",
        "- [GeeksforGeeks Interview Experiences](https://www.geeksforgeeks.org/company-interview-corner/)",
        "- [Blind — Tech Interviews](https://www.teamblind.com/topics/Interview)",
        "- [Reddit r/cscareerquestions](https://www.reddit.com/r/cscareerquestions/)",
    ]

    if sources_text:
        lines += ["", "### Sources Found", sources_text]

    return "\n".join(lines)


INTERVIEW_TOOLS = [
    search_interview_questions,
    generate_interview_questions,
    get_interview_prep_guide,
]