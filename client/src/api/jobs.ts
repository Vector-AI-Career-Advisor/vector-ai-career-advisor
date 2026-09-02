import api from './client'

export interface Job {
  id: string
  title?: string
  role?: string
  seniority?: string
  company?: string
  location?: string
  region?: string
  url?: string
  description?: string
  skills_must?: string[]
  skills_nice?: string[]
  yearsexperience?: number
  past_experience?: string[]
  education?: string[]
  keyword?: string
  source?: string
  posted_at?: string
  scraped_at?: string
  logo_url?: string
}

export interface JobFilters {
  keyword?: string
  seniority?: string
  location?: string
  posted_date?: string
  roles?: string[]
  years_experience_min?: number
  years_experience_max?: number
  skills?: string[]
  limit?: number
  offset?: number
}

export interface JobsResponse {
  items: Job[]
  total: number
}

export const fetchJobs = async (filters: JobFilters = {}): Promise<JobsResponse> => {
  const { data } = await api.get('/jobs/', { params: filters })
  return data
}

export const fetchJob = async (id: string): Promise<Job> => {
  const { data } = await api.get(`/jobs/${id}`)
  return data
}