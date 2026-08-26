"""Course Tools — search the web for the best course recommendations."""
from __future__ import annotations

import json
import logging
import os
import requests
from langchain_core.tools import tool

SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
SERPER_URL     = "https://google.serper.dev/search"
ANTHROPIC_URL  = "https://api.anthropic.com/v1/messages"


# ── Web search ─────────────────────────────────────────────────────────────

def _web_search(query: str, num: int = 8) -> list[dict]:
    """Return [{title, link, snippet}] from Serper. Returns [] on any failure."""
    if not SERPER_API_KEY:
        print("[DEBUG] SERPER_API_KEY not set")
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
            {
                "title":   r.get("title", ""),
                "link":    r.get("link", ""),
                "snippet": r.get("snippet", ""),
            }
            for r in resp.json().get("organic", [])
        ]
    except Exception as e:
        print(f"[DEBUG] Serper error: {e}")
        return []


# ── Claude curation ────────────────────────────────────────────────────────

def _ask_claude(topic: str, goal: str, results: list[dict]) -> str:
    """Send search results to Claude and get a curated recommendation."""
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_key or not results:
        return _fallback_format(topic, goal)

    goal_label = "hands-on project building" if goal == "project" else "conceptual understanding"
    results_json = json.dumps(results, ensure_ascii=False, indent=2)

    prompt = f"""You are a career advisor recommending online courses for someone who wants to learn **{topic}**.
Their goal: {goal_label}.

Here are the top search results from Google (title, URL, snippet):
{results_json}

Write a concise, structured recommendation in this EXACT format:

A one-sentence intro recommending the best option.

Then a numbered list of the 3-5 best courses/resources found. For each:
1. [Course Name](URL)
   - Who made it and why it's good (1 sentence).
   - Free or paid.

If there are good free YouTube options in the results, add a short "**Free YouTube Option**" section with 1-2 links.

End with a "**Best Learning Path**" section: 3-5 bullet steps showing how to progress (e.g. start here → build this project → get this cert).

Rules:
- ONLY use URLs from the search results — never invent links.
- Only include results that are actual courses or tutorials.
- Keep the whole response under 300 words.
- Do NOT add a closing offer of further help.
"""

    try:
        print(f"[DEBUG] Sending {len(results)} results to Claude for curation")
        resp = requests.post(
            ANTHROPIC_URL,
            headers={
                "x-api-key":         anthropic_key,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            json={
                "model":      "claude-haiku-4-5",
                "max_tokens": 700,
                "messages":   [{"role": "user", "content": prompt}],
            },
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"].strip()
    except Exception as e:
        print(f"[DEBUG] Claude API error: {e}, using fallback")
        return _fallback_format(topic, goal)


# ── Known good course links per topic (used when Serper is unavailable) ───

_KNOWN_COURSES: dict[str, list[dict]] = {
    "aws": [
        {"title": "AWS Skill Builder (Official)",       "link": "https://skillbuilder.aws",                                          "free": True,  "note": "Official AWS platform. Free beginner paths, hands-on labs, cert prep."},
        {"title": "AWS Cloud Practitioner Essentials",  "link": "https://aws.amazon.com/training/digital/aws-cloud-practitioner-essentials/", "free": True,  "note": "Best first course — covers EC2, S3, RDS, Lambda, IAM, VPC."},
        {"title": "AWS Solutions Architect (Coursera)", "link": "https://www.coursera.org/learn/aws-cloud-solutions-architect",       "free": False, "note": "Structured roadmap with projects. Good for cert prep."},
        {"title": "AWS Full Course 2024 (YouTube)",     "link": "https://www.youtube.com/results?search_query=aws+full+course+2024", "free": True,  "note": "Free long-form walkthrough of AWS fundamentals."},
    ],
    "python": [
        {"title": "Python for Everybody (Coursera)",    "link": "https://www.coursera.org/specializations/python",                   "free": False, "note": "University of Michigan. Best structured beginner course."},
        {"title": "freeCodeCamp Python",                "link": "https://www.freecodecamp.org/learn/scientific-computing-with-python/", "free": True,  "note": "Free, project-based. Covers fundamentals through data."},
        {"title": "Automate the Boring Stuff (free)",   "link": "https://automatetheboringstuff.com",                                "free": True,  "note": "Practical Python book — fully free online."},
    ],
    "react": [
        {"title": "React — The Complete Guide (Udemy)", "link": "https://www.udemy.com/course/react-the-complete-guide-incl-redux/", "free": False, "note": "Maximilian Schwarzmüller. Most comprehensive React course available."},
        {"title": "React Official Docs / Tutorial",     "link": "https://react.dev/learn",                                           "free": True,  "note": "Official React docs with interactive tutorial."},
    ],
    "docker": [
        {"title": "Docker & Kubernetes (Udemy)",        "link": "https://www.udemy.com/course/docker-and-kubernetes-the-complete-guide/", "free": False, "note": "Stephen Grider. Best hands-on Docker + K8s course."},
        {"title": "Play with Docker (free)",            "link": "https://labs.play-with-docker.com",                                 "free": True,  "note": "Browser-based Docker playground — no install needed."},
    ],
    "machine learning": [
        {"title": "Machine Learning Specialization (Coursera)", "link": "https://www.coursera.org/specializations/machine-learning-introduction", "free": False, "note": "Andrew Ng / DeepLearning.AI. The gold standard ML course."},
        {"title": "fast.ai (free)",                     "link": "https://www.fast.ai",                                               "free": True,  "note": "Practical deep learning — top-down, project-first approach."},
    ],
}

def _get_known_courses(topic: str) -> list[dict] | None:
    """Return known courses for a topic if we have them."""
    topic_lower = topic.lower()
    for key, courses in _KNOWN_COURSES.items():
        if key in topic_lower or topic_lower in key:
            return courses
    return None


def _fallback_format(topic: str, goal: str) -> str:
    """Structured fallback using known course links when Serper is unavailable."""
    known = _get_known_courses(topic)

    if known:
        free  = [c for c in known if c["free"]]
        paid  = [c for c in known if not c["free"]]
        lines = [f"Here are the best courses to learn **{topic}**:\n"]

        all_courses = paid + free  # paid first (usually better structured)
        for i, c in enumerate(all_courses, 1):
            tag = "Free" if c["free"] else "Paid"
            lines.append(f"{i}. [{c['title']}]({c['link']})")
            lines.append(f"   - {c['note']} ({tag})")
            lines.append("")

        lines += [
            "**Best Learning Path**",
            f"- Start with a free intro to get comfortable with {topic} basics.",
            "- Follow a structured course (Udemy or Coursera) for depth.",
            "- Build a real project and put it on GitHub.",
            "- Get certified if your target role values it.",
        ]
        return "\n".join(lines)

    # Generic fallback for unknown topics
    return (
        f"Here are the best places to find **{topic}** courses:\n\n"
        f"1. [Udemy](https://www.udemy.com/courses/search/?q={topic.replace(' ', '+')}) — search '{topic}'. Filter by highest rated.\n"
        f"2. [Coursera](https://www.coursera.org/search?query={topic.replace(' ', '+')}) — good for structured, university-backed content.\n"
        f"3. [YouTube](https://www.youtube.com/results?search_query={topic.replace(' ', '+')}+full+course) — free full courses from channels like freeCodeCamp, Traversy Media, Fireship.\n\n"
        f"**Best Learning Path**\n"
        f"- Watch a free YouTube intro first to see if you enjoy the topic.\n"
        f"- Pick one structured course and finish it completely.\n"
        f"- Build a real project and put it on GitHub — that's what employers care about."
    )


# ── Tool ───────────────────────────────────────────────────────────────────

@tool
def recommend_courses(topic: str, goal: str) -> str:
    """Search the web and return AI-curated course recommendations with real links.

    Args:
        topic: The skill or subject (e.g. 'Docker', 'React', 'Data Engineering', 'AWS')
        goal:  Either 'project' (hands-on portfolio building) or 'knowledge' (conceptual understanding)

    Returns:
        AI-curated course recommendations with direct links and reasoning.
    """
    print(f"\n[COURSE TOOL] Searching for best '{topic}' courses (goal: {goal})")

    goal_label = "project tutorial" if goal == "project" else "best course"

    all_results: list[dict] = []
    seen_links: set[str] = set()

    # Run multiple targeted searches to get a broad, high-quality result set
    queries = [
        f"best {topic} course {goal_label} 2025",
        f"{topic} {goal_label} udemy coursera",
        f"free {topic} course tutorial beginners",
    ]

    for query in queries:
        print(f"[COURSE TOOL] Searching: {query}")
        for r in _web_search(query, num=5):
            if r["link"] and r["link"] not in seen_links:
                seen_links.add(r["link"])
                all_results.append(r)

    print(f"[COURSE TOOL] Found {len(all_results)} unique results")

    if not all_results:
        return _fallback_format(topic, goal)

    return _ask_claude(topic, goal, all_results[:12])