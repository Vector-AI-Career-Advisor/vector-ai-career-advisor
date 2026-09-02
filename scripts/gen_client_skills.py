"""
Generate client/src/lib/skills.ts from server/etl/skills.py.

The client needs the same skill normalisation as the ETL so that rows written
before the last backfill still render consistently. The rule tables are far too
big to keep in sync by hand, so the TypeScript mirror is generated: the tables
are dumped straight from the Python module and the rules are the port below.

Run after editing server/etl/skills.py (no DB, no network):

    python -m scripts.gen_client_skills
"""
from __future__ import annotations

import json
from pathlib import Path

from server.etl import skills as py

OUT = Path(__file__).resolve().parents[1] / "client" / "src" / "lib" / "skills.ts"

_HEADER = """// GENERATED FILE — do not edit by hand.
// Mirrors server/etl/skills.py; regenerate with `python -m scripts.gen_client_skills`
// after changing the Python rules.
//
// The ETL normalises every skill on ingest and scripts/backfill_skills.py fixes
// older rows, so this is a display-time fallback: it folds casing, filler words
// ("C programming" → "C"), versions, plurals and synonyms onto one spelling.
"""

_BODY = """
const TECH_NAMES = new Set([...Object.keys(CANONICAL), ...Object.keys(ACRONYMS)])

const WS = /\\s+/g
const PARENS = /\\s*\\([^)]*\\)/g
const VERSION = /\\s+v?\\d+(?:\\.\\d+)*\\+?$/
const UPPER = /[A-Z]/
const INNER_UPPER = /.[A-Z]/

function clean(raw: string): string {
  let skill = String(raw).replace(/\\u00a0/g, ' ').replace(WS, ' ').trim()
  skill = skill.replace(/^["'`\\u201c\\u201d\\u2018\\u2019]+|["'`\\u201c\\u201d\\u2018\\u2019]+$/g, '').trim()
  const stripped = skill.replace(PARENS, '').trim()
  if (stripped) skill = stripped
  skill = skill.replace(/ & /g, ' and ').replace(/[.,;:]+$/, '').trim()
  return skill.replace(WS, ' ')
}

function stripPrefix(skill: string): string {
  for (;;) {
    const low = skill.toLowerCase()
    if (low in ALIASES || low in CANONICAL) return skill
    const trimmed = skill.replace(PREFIX, '').trim()
    if (trimmed === skill || !trimmed) return skill
    skill = trimmed
  }
}

function stripSuffix(skill: string): string {
  for (;;) {
    const low = skill.toLowerCase()
    let head: string | null = null
    for (const suffix of NOISE_SUFFIXES) {
      if (low.endsWith(' ' + suffix)) {
        head = skill.slice(0, -(suffix.length + 1)).trim()
        break
      }
    }
    if (head === null) {
      const versioned = skill.replace(VERSION, '').trim()
      if (versioned !== skill) head = versioned
    }
    if (!head) return skill
    const headLow = head.toLowerCase()
    if (headLow in ALIASES) return ALIASES[headLow]
    if (!TECH_NAMES.has(headLow)) return skill
    skill = head
  }
}

function recaseToken(token: string, isFirst: boolean, casingOnly = false): string {
  const low = token.toLowerCase()
  const canonical = CANONICAL[low]
  if (canonical && !canonical.includes(' ') && !(casingOnly && canonical.toLowerCase() !== low)) {
    return canonical
  }
  if (token.includes('-') && token.length > 1) {
    return token
      .split('-')
      .map((part, i) => recaseToken(part, isFirst && i === 0, true))
      .join('-')
  }
  if (token !== token.toUpperCase() && INNER_UPPER.test(token)) return token
  if (ACRONYMS[low]) return ACRONYMS[low]
  if (!token) return token
  if (isFirst) return UPPER.test(token) ? token : low.charAt(0).toUpperCase() + low.slice(1)
  if (COMMON_WORDS.has(low)) return low
  if (UPPER.test(token)) return token
  return low
}

function recase(skill: string): string {
  let words = skill.split(' ')
  if (words.length > 1 && skill === skill.toUpperCase() && words.some(w => w.length >= 5)) {
    words = skill.toLowerCase().split(' ')
  }
  return words.map((w, i) => recaseToken(w, i === 0)).join(' ')
}

function fixLastWord(skill: string): string {
  const words = skill.split(' ')
  if (words.length < 2) return skill
  const last = words[words.length - 1]
  if (last === last.toLowerCase() && PREFERRED_NUMBER[last]) {
    words[words.length - 1] = PREFERRED_NUMBER[last]
  }
  return words.join(' ')
}

function resolve(skill: string): string {
  skill = ALIASES[skill.toLowerCase()] ?? skill
  const canonical = CANONICAL[skill.toLowerCase()]
  if (canonical) return canonical
  skill = stripSuffix(skill)
  skill = ALIASES[skill.toLowerCase()] ?? skill
  const canonical2 = CANONICAL[skill.toLowerCase()]
  if (canonical2) return canonical2
  skill = fixLastWord(recase(skill))
  return ALIASES[skill.toLowerCase()] ?? skill
}

/** Canonical display spelling of one skill string. */
export function formatSkill(raw: string): string {
  let skill = stripPrefix(clean(raw))
  if (!skill) return ''
  for (let i = 0; i < 3; i++) {
    const next = resolve(skill)
    if (next === skill) break
    skill = next
  }
  return skill
}

/**
 * Normalise one skill string into the skills it actually names — compounds
 * whose sides are technologies in their own right are split ("C/C++" → C, C++),
 * names that merely contain a slash ("CI/CD") are left whole.
 */
export function expandSkill(raw: string): string[] {
  const skill = stripPrefix(clean(raw))
  if (!skill) return []
  const low = skill.toLowerCase()
  if (skill.includes('/') && !skill.includes(' ') && !NO_SPLIT.has(low) && !(low in CANONICAL)) {
    const parts = skill.split('/').map(p => p.trim()).filter(Boolean)
    if (
      parts.length > 1 &&
      parts.every(p => TECH_NAMES.has(p.toLowerCase()) || p.toLowerCase() in ALIASES)
    ) {
      const out: string[] = []
      for (const part of parts) {
        const norm = formatSkill(part)
        if (norm && !out.includes(norm)) out.push(norm)
      }
      return out
    }
  }
  const norm = formatSkill(skill)
  return norm ? [norm] : []
}
"""


def _record(name: str, table: dict[str, str]) -> str:
    body = "".join(f"  {json.dumps(k)}: {json.dumps(v)},\n" for k, v in table.items())
    return f"const {name}: Record<string, string> = {{\n{body}}}\n"


def _set(name: str, values) -> str:
    body = "".join(f"  {json.dumps(v)},\n" for v in sorted(values))
    return f"const {name} = new Set([\n{body}])\n"


def _list(name: str, values) -> str:
    body = "".join(f"  {json.dumps(v)},\n" for v in values)
    return f"const {name} = [\n{body}]\n"


def build() -> str:
    parts = [
        _HEADER,
        _record("CANONICAL", py._CANONICAL),
        _record("ACRONYMS", py._ACRONYMS),
        _record("ALIASES", py._ALIASES),
        _record("PREFERRED_NUMBER", py._PREFERRED_NUMBER),
        _set("COMMON_WORDS", py._COMMON_WORDS),
        _set("NO_SPLIT", py._NO_SPLIT),
        _list("NOISE_SUFFIXES", py._NOISE_SUFFIXES),
        f"const PREFIX = new RegExp({json.dumps(py._PREFIX_RE.pattern)}, 'i')\n",
        _BODY,
    ]
    return "\n".join(parts)


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT} ({len(build().splitlines())} lines)")
