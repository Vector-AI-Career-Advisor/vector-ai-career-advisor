import api from './client'

export interface LoginRecommendation {
  reply: string
  job_ids: string[]
}

export const getLoginRecommendation = async (): Promise<LoginRecommendation> => {
  const { data } = await api.post<LoginRecommendation>('/agents/login-recommendation')
  return data
}
