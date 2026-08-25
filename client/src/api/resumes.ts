import api from './client'

export interface ResumeInfo {
  filename: string
  uploaded_at: string
  updated_at: string
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

export const deleteResume = async (): Promise<void> => {
  await api.delete('/resumes/me')
}

export interface CoverLetter {
  cover_letter: string
  job_title: string
  company: string
  skill_gaps?: string
}

export const generateCoverLetter = async (jobId: string): Promise<CoverLetter> => {
  const { data } = await api.post<CoverLetter>('/agents/cover-letter', { job_id: jobId })
  return data
}