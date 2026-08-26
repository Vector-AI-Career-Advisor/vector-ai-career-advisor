import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login as apiLogin, signup as apiSignup } from '../api/auth'

export function useAuth() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  const handleLogin = async (email: string, password: string) => {
    setLoading(true)
    setError(null)
    try {
      const token = await apiLogin(email, password)
      localStorage.setItem('token', token)
      sessionStorage.setItem('vector_just_logged_in', '1')
      navigate('/jobs')
    } catch (e: any) {
      setError(e.response?.data?.detail ?? 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  const handleSignup = async (email: string, password: string) => {
    setLoading(true)
    setError(null)
    try {
      await apiSignup(email, password)
      // Auto-login after signup
      const token = await apiLogin(email, password)
      localStorage.setItem('token', token)
      sessionStorage.setItem('vector_just_logged_in', '1')
      navigate('/jobs')
    } catch (e: any) {
      setError(e.response?.data?.detail ?? 'Signup failed')
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    navigate('/login')
  }

  const isAuthenticated = () => !!localStorage.getItem('token')

  return { handleLogin, handleSignup, handleLogout, isAuthenticated, loading, error }
}
