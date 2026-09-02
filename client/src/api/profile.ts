import api from './client'

export interface BasicInfo {
  first_name: string
  last_name: string
  email: string
  phone?: string
  city?: string
}

export interface CareerStage {
  career_stage: string
  years_experience: number
}

export interface Education {
  degree_type: string
  field_of_study: string
  school: string
  graduation_year: number
  relevant_courses?: string
  academic_highlights?: string
}

export interface EducationRow extends Education {
  id: number
}

export interface WorkExperience {
  position: string
  company: string
  start_date: string           // YYYY-MM-DD
  end_date?: string | null      // YYYY-MM-DD, null = present
  description?: string | null
}

export interface WorkExperienceRow extends WorkExperience {
  id: number
}

export interface Skill {
  skill: string
  category?: string
}

export interface SoftSkill {
  skill: string
}

export interface Language {
  language: string
  proficiency?: string
}

export interface Preferences {
  github_url?: string
  portfolio_url?: string
  work_preferences?: Record<string, boolean>
  interests?: string[]
}

export interface ProfileSummary {
  user: {
    id?: number
    email?: string
    first_name?: string
    last_name?: string
    phone?: string
    city?: string
    years_experience?: number | null
    career_stage?: string | null
    created_at?: string
    updated_at?: string
  }
  education: {
    degree_type?: string | null
    field_of_study?: string | null
    school?: string | null
    graduation_year?: number | null
  }
  skills: string[]
  soft_skills: string[]
  work_experience: Array<{
    position?: string | null
    company?: string | null
    start_date?: string | null
    end_date?: string | null
  }>
  work_preferences?: Record<string, boolean>
  job_filters: {
    keyword?: string
    skills?: string[]
    location?: string | null
    years_experience_min?: number | null
    seniority?: string | null
    work_preferences?: Record<string, boolean>
  }
}

export const updateBasicInfo = async (data: BasicInfo): Promise<any> => {
  const { data: response } = await api.post('/profile/basic-info', data)
  return response
}

export const updateCareerStage = async (data: CareerStage): Promise<any> => {
  const { data: response } = await api.post('/profile/career-stage', data)
  return response
}

export const addEducation = async (data: Education): Promise<any> => {
  const { data: response } = await api.post('/profile/education', data)
  return response
}

export const getEducation = async (): Promise<EducationRow[]> => {
  const { data } = await api.get('/profile/education')
  return data
}

export const updateEducation = async (id: number, data: Education): Promise<EducationRow> => {
  const { data: response } = await api.put(`/profile/education/${id}`, data)
  return response
}

export const deleteEducation = async (id: number): Promise<{ success: boolean }> => {
  const { data } = await api.delete(`/profile/education/${id}`)
  return data
}

export const getWorkExperience = async (): Promise<WorkExperienceRow[]> => {
  const { data } = await api.get('/profile/work-experience')
  return data
}

export const addWorkExperience = async (data: WorkExperience): Promise<WorkExperienceRow> => {
  const { data: response } = await api.post('/profile/work-experience', data)
  return response
}

export const updateWorkExperience = async (id: number, data: WorkExperience): Promise<WorkExperienceRow> => {
  const { data: response } = await api.put(`/profile/work-experience/${id}`, data)
  return response
}

export const deleteWorkExperience = async (id: number): Promise<{ success: boolean }> => {
  const { data } = await api.delete(`/profile/work-experience/${id}`)
  return data
}

export const addSkill = async (data: Skill): Promise<any> => {
  const { data: response } = await api.post('/profile/skills', data)
  return response
}

export const getSkills = async (): Promise<any[]> => {
  const { data } = await api.get('/profile/skills')
  return data
}

export const deleteSkill = async (skillId: number): Promise<any> => {
  const { data } = await api.delete(`/profile/skills/${skillId}`)
  return data
}

export const addSoftSkill = async (data: SoftSkill): Promise<any> => {
  const { data: response } = await api.post('/profile/soft-skills', data)
  return response
}

export const getSoftSkills = async (): Promise<any[]> => {
  const { data } = await api.get('/profile/soft-skills')
  return data
}

export const addLanguage = async (data: Language): Promise<any> => {
  const { data: response } = await api.post('/profile/languages', data)
  return response
}

export const getLanguages = async (): Promise<any[]> => {
  const { data } = await api.get('/profile/languages')
  return data
}

export const updatePreferences = async (data: Preferences): Promise<any> => {
  const { data: response } = await api.post('/profile/preferences', data)
  return response
}

export const getProfile = async (): Promise<any> => {
  const { data } = await api.get('/profile/me')
  return data
}

export const getProfileSummary = async (): Promise<ProfileSummary> => {
  const { data } = await api.get('/profile/summary')
  return data
}

export const checkOnboardingStatus = async (): Promise<any> => {
  const { data } = await api.get('/profile/onboarding-status')
  return data
}

// ── Job-search profile: core (tier 1) & preferences (tier 2) ────────────────

export interface JobCore {
  min_experience: number | null
  max_experience: number | null
  education_level: string | null
}

export interface JobPreferences {
  preferred_roles: string[]
  preferred_locations: string[]
  preferred_seniority: string[]
  remote_only: boolean
}

export const getJobCore = async (): Promise<JobCore> => {
  const { data } = await api.get('/profile/job-core')
  return data
}

export const updateJobCore = async (data: JobCore): Promise<JobCore> => {
  const { data: response } = await api.put('/profile/job-core', data)
  return response
}

export const getJobPreferences = async (): Promise<JobPreferences> => {
  const { data } = await api.get('/profile/job-preferences')
  return data
}

export const updateJobPreferences = async (data: JobPreferences): Promise<JobPreferences> => {
  const { data: response } = await api.put('/profile/job-preferences', data)
  return response
}
