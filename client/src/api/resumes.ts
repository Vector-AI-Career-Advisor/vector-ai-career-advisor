import api from './client'

export interface ResumeInfo {
  filename: string
  uploaded_at: string
  updated_at: string
}

export interface ResumeListItem {
  id: number
  title: string | null
  filename: string
  is_active: boolean
  skill_count: number
  uploaded_at: string
  updated_at: string
}

export interface ResumeDetail extends ResumeListItem {
  content: string
  skills: string[]
  soft_skills: string[]
}

export const uploadResume = async (file: File): Promise<void> => {
  const form = new FormData()
  form.append('file', file)
  await api.post('/resumes/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const getMyResume = async (): Promise<ResumeInfo | null> => {
  try {
    const { data } = await api.get<ResumeInfo>('/resumes/me')
    return data
  } catch (e: any) {
    if (e.response?.status === 404) return null
    throw e
  }
}

export const listResumes = async (): Promise<ResumeListItem[]> => {
  const { data } = await api.get<ResumeListItem[]>('/resumes')
  return data
}

export const getResume = async (id: number): Promise<ResumeDetail> => {
  const { data } = await api.get<ResumeDetail>(`/resumes/${id}`)
  return data
}

export const setActiveResume = async (id: number): Promise<ResumeDetail> => {
  const { data } = await api.patch<ResumeDetail>(`/resumes/${id}`, { is_active: true })
  return data
}

export const renameResume = async (id: number, title: string): Promise<ResumeDetail> => {
  const { data } = await api.patch<ResumeDetail>(`/resumes/${id}`, { title })
  return data
}

export const deleteResume = async (id?: number): Promise<void> => {
  await api.delete(id != null ? `/resumes/${id}` : '/resumes/me')
}

export interface CoverLetter {
  cover_letter: string
  job_title: string
  company: string
  skill_gaps?: string
}

export interface TailoredResume {
  tailored_resume: string
  job_title: string
  company: string
  file?: string
}

export const generateCoverLetter = async (jobId: string): Promise<CoverLetter> => {
  const { data } = await api.post<CoverLetter>('/agents/cover-letter', { job_id: jobId })
  return data
}

export const generateTailoredResume = async (jobId: string): Promise<TailoredResume> => {
  const { data } = await api.post<TailoredResume>('/agents/fit-resume', { job_id: jobId })
  return data
}