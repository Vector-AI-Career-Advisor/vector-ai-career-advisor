// Saved job-filter presets — persisted in localStorage, surfaced in the Jobs
// filter sidebar.

export interface FilterPreset {
  id: string
  name: string
  keyword?: string
  seniority?: string
  location?: string
  posted_date?: string
  roles?: string[]
  years_experience_min?: number
  years_experience_max?: number
  skills?: string[]
  createdAt: string
}

const PRESETS_KEY = 'vector_saved_filters'

export function loadPresets(): FilterPreset[] {
  try {
    return JSON.parse(localStorage.getItem(PRESETS_KEY) ?? '[]')
  } catch {
    return []
  }
}

export function savePreset(preset: Omit<FilterPreset, 'id' | 'createdAt'>): FilterPreset {
  const presets = loadPresets()
  const next: FilterPreset = {
    ...preset,
    id: crypto.randomUUID(),
    createdAt: new Date().toISOString(),
  }
  localStorage.setItem(PRESETS_KEY, JSON.stringify([next, ...presets]))
  return next
}

export function deletePreset(id: string): void {
  const presets = loadPresets().filter(p => p.id !== id)
  localStorage.setItem(PRESETS_KEY, JSON.stringify(presets))
}
