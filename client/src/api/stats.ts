// src/api/stats.ts
// Add this new file alongside your existing jobs.ts and auth.ts

import api from './client'

export interface DailyCount {
  date: string
  count: number
}

export interface CompanyCount {
  company: string
  count: number
}

export interface RegionCount {
  region: string
  count: number
}

export interface SkillCount {
  skill: string
  count: number
}

export interface SeniorityCount {
  seniority: string
  count: number
}

export interface StatsResponse {
  summary: {
    total_jobs: number
    total_companies: number
    total_locations: number
    total_skills: number
  }
  jobs_per_day: DailyCount[]
  top_companies: CompanyCount[]
  jobs_by_region: RegionCount[]
  top_skills: SkillCount[]
  by_seniority: SeniorityCount[]
  skills_by_role: Record<string, SkillCount[]>
}

export const fetchStats = async (): Promise<StatsResponse> => {
  const { data } = await api.get('/jobs/stats')
  return data
}
