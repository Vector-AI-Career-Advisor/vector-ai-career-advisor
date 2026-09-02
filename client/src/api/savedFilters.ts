import api from './client'
import type { JobFilters } from './jobs'

// The persisted part of a job search — no pagination.
export type SavedFilterBody = Omit<JobFilters, 'limit' | 'offset'>

export interface SavedFilter {
  id: number
  name: string
  filters: SavedFilterBody
  created_at: string
  updated_at: string
}

export const listSavedFilters = async (): Promise<SavedFilter[]> => {
  const { data } = await api.get('/saved-filters/')
  return data
}

export const createSavedFilter = async (
  name: string,
  filters: SavedFilterBody,
): Promise<SavedFilter> => {
  const { data } = await api.post('/saved-filters/', { name, filters })
  return data
}

export const deleteSavedFilter = async (id: number): Promise<void> => {
  await api.delete(`/saved-filters/${id}`)
}
