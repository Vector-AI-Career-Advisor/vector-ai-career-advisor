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

export const getEducation = async (): Promise<any[]> => {
  const { data } = await api.get('/profile/education')
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

export const checkOnboardingStatus = async (): Promise<any> => {
  const { data } = await api.get('/profile/onboarding-status')
  return data
}
