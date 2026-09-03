import type { SavedFilterBody } from '../api/savedFilters'
import { POSTED_DATE_OPTIONS, EXP_MIN, EXP_MAX, JOB_EDUCATION_LABELS } from '../constants'

export interface FilterFacet {
  label: string
  value: string
}

const postedLabel = (v?: string) =>
  POSTED_DATE_OPTIONS.find(o => o.value === v)?.label ?? v ?? ''

/**
 * Turn a saved filter into a readable list of "what's in it", for the
 * expandable rows in the profile and the sidebar.
 */
export function summarizeFilter(f: SavedFilterBody): FilterFacet[] {
  const facets: FilterFacet[] = []

  if (f.keyword) facets.push({ label: 'Keyword', value: `"${f.keyword}"` })
  if (f.seniority) {
    facets.push({ label: 'Seniority', value: f.seniority.split(',').join(', ') })
  }
  if (f.roles?.length) facets.push({ label: 'Roles', value: f.roles.join(', ') })
  if (f.location) facets.push({ label: 'Location', value: f.location })

  const lo = f.years_experience_min
  const hi = f.years_experience_max
  if (lo != null || hi != null) {
    const from = lo ?? EXP_MIN
    const to = hi == null ? `${EXP_MAX}+` : hi
    facets.push({ label: 'Experience', value: `${from}–${to} yrs` })
  }

  if (f.skills?.length) facets.push({ label: 'Skills', value: f.skills.join(', ') })
  if (f.education?.length) {
    facets.push({
      label: 'Education',
      value: f.education.map(c => JOB_EDUCATION_LABELS[c] ?? c).join(', '),
    })
  }
  if (f.posted_date) facets.push({ label: 'Posted', value: postedLabel(f.posted_date) })

  return facets
}

/** One-line version, e.g. for a title attribute. */
export function summarizeFilterInline(f: SavedFilterBody): string {
  const facets = summarizeFilter(f)
  return facets.length
    ? facets.map(x => `${x.label}: ${x.value}`).join('  ·  ')
    : 'No criteria — matches everything'
}
