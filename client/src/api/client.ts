import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000',
  // Repeat array params as `key=a&key=b` (no `[]`), which is what FastAPI's
  // `List[str] = Query(...)` reads — the axios default `key[]=a` is ignored.
  paramsSerializer: { indexes: null },
})

// Attach JWT to every request automatically
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Auto-logout on 401
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api
