import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import api from '../api/client'
import './AuthPage.css'


const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? ''

function getRedirectUri(provider: string) {
  return `${window.location.origin}/auth/callback/${provider}`
}

function buildGoogleUrl() {
  const p = new URLSearchParams({
    client_id: GOOGLE_CLIENT_ID,
    redirect_uri: getRedirectUri('google'),
    response_type: 'code',
    scope: 'openid email profile',
    access_type: 'offline',
    prompt: 'select_account',
  })
  return `https://accounts.google.com/o/oauth2/v2/auth?${p}`
}



/* ── Icons ── */
const IconClock = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
  </svg>
)
const IconSparkle = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 3v3m0 12v3M3 12h3m12 0h3m-3.3-7.7-2.1 2.1M8.4 15.6l-2.1 2.1m0-11.4 2.1 2.1m7.2 7.2 2.1 2.1"/>
  </svg>
)
const IconChat = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
  </svg>
)
const IconTrack = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
  </svg>
)
const IconSun = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="16" height="16">
    <circle cx="12" cy="12" r="5"/>
    <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
    <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
  </svg>
)
const IconMoon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="16" height="16">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
  </svg>
)

/* ── OAuth callback handler component ── */
export function OAuthCallback() {
  const navigate  = useNavigate()
  const [params]  = useSearchParams()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const code     = params.get('code')
    const provider = window.location.pathname.split('/').pop() as string // 'google' | 'linkedin'

    if (!code) { setError('No authorization code received.'); return }

    api.post('/auth/oauth/callback', {
      code,
      redirect_uri: getRedirectUri(provider),
      provider,
    }).then(({ data }) => {
      localStorage.setItem('token', data.access_token)
      sessionStorage.setItem('vector_just_logged_in', '1')
      navigate('/jobs')
    }).catch((e) => {
      setError(e.response?.data?.detail ?? 'OAuth login failed')
    })
  }, [])

  if (error) return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'center', minHeight:'100vh',
                  background:'#0b0c12', color:'#f87171', fontFamily:'sans-serif', fontSize:'1rem' }}>
      {error} — <a href="/login" style={{ color:'#30bfb8', marginLeft:8 }}>Return to login</a>
    </div>
  )

  return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'center', minHeight:'100vh',
                  background:'#0b0c12', color:'#9898b4', fontFamily:'sans-serif', fontSize:.9+'rem' }}>
      Completing sign-in…
    </div>
  )
}

/* ── Main auth page ── */
export default function AuthPage() {
  const [mode, setMode]       = useState<'login' | 'signup'>('login')
  const [email, setEmail]     = useState('')
  const [password, setPassword] = useState('')
  const [theme, setTheme]     = useState<'dark' | 'light'>(() =>
    (localStorage.getItem('theme') as 'dark' | 'light') ?? 'dark'
  )
  const { handleLogin, handleSignup, loading, error } = useAuth()

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('theme', theme)
  }, [theme])

  const toggleTheme = () => setTheme(t => t === 'dark' ? 'light' : 'dark')

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    mode === 'login' ? handleLogin(email, password) : handleSignup(email, password)
  }

  return (
    <div className="auth-root">

      {/* ══════════ LEFT HERO ══════════ */}
      <div className="auth-hero">
        <div className="auth-orb auth-orb-1" />
        <div className="auth-orb auth-orb-2" />
        <div className="auth-orb auth-orb-3" />

        <div className="auth-hero-content">
          <div className="auth-logo">
            <img src="/full-logo.png" alt="Vector" />
          </div>

          <p className="auth-eyebrow">Your career trajectory, defined</p>

          <h1 className="auth-headline">
            Every great career<br />
            needs a <em>direction.</em>
          </h1>

          <div className="auth-features">
            <div className="auth-feat">
              <div className="feat-icon pur"><IconClock /></div>
              <div className="feat-body">
                <strong>Current listings, updated daily</strong>
                <span>Every role posted today appears in your feed by morning — no stale listings.</span>
              </div>
            </div>
            <div className="auth-feat">
              <div className="feat-icon teal"><IconSparkle /></div>
              <div className="feat-body">
                <strong>AI-tailored application materials</strong>
                <span>Automatically adapts your CV and cover letter to the requirements of each role.</span>
              </div>
            </div>
            <div className="auth-feat">
              <div className="feat-icon pink"><IconChat /></div>
              <div className="feat-body">
                <strong>Role-specific interview preparation</strong>
                <span>Real questions from your target company, supplemented by AI-generated prompts.</span>
              </div>
            </div>
            <div className="auth-feat">
              <div className="feat-icon gold"><IconTrack /></div>
              <div className="feat-body">
                <strong>End-to-end application tracking</strong>
                <span>Monitor every stage from application to offer. Never lose sight of where you stand.</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ══════════ RIGHT PANEL ══════════ */}
      <div className="auth-panel">

        {/* Theme toggle */}
        <button
          className="auth-theme-toggle"
          onClick={toggleTheme}
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
        >
          {theme === 'dark' ? <IconSun /> : <IconMoon />}
        </button>

        <div className="auth-card">
          <div className="auth-form-header">
            <h2>{mode === 'login' ? 'Welcome back.' : 'Get started.'}</h2>
            <p>{mode === 'login' ? 'Sign in to continue.' : 'Create your account below.'}</p>
          </div>

          {/* Tabs */}
          <div className="auth-tabs">
            <button className={`auth-tab ${mode === 'login' ? 'active' : ''}`} onClick={() => setMode('login')}>
              Sign In
            </button>
            <button className={`auth-tab ${mode === 'signup' ? 'active' : ''}`} onClick={() => setMode('signup')}>
              Create Account
            </button>
          </div>

          {/* Email/password form */}
          <form onSubmit={submit} className="auth-form">
            <div className="field">
              <label htmlFor="email">Email address</label>
              <input
                id="email" type="email" value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@company.com" required autoComplete="email"
              />
            </div>
            <div className="field">
              <label htmlFor="password">Password</label>
              <input
                id="password" type="password" value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••" required minLength={8}
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              />
            </div>

            {error && <div className="auth-error">{error}</div>}

            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? 'Please wait…' : mode === 'login' ? 'Sign In →' : 'Create Account →'}
            </button>
          </form>

          {/* Social login */}
          <div className="auth-divider"><span>or continue with</span></div>
          <div className="auth-socials">
            <a className="btn-social" href={buildGoogleUrl()}>
              <svg viewBox="0 0 24 24">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
              </svg>
              Google
            </a>
            <button className="btn-social" type="button" disabled>
              <svg viewBox="0 0 24 24" fill="none">
                <rect width="24" height="24" rx="4" fill="#0A66C2"/>
                <path d="M7.5 9.5h-3v9h3v-9zM6 8.2A1.7 1.7 0 1 0 6 4.8 1.7 1.7 0 0 0 6 8.2zM19.5 13c0-2.2-1.1-3.7-3-3.7-1 0-1.8.5-2.2 1.2V9.5h-3v9h3v-4.8c0-1.1.5-1.9 1.5-1.9s1.7.7 1.7 2v4.7h3V13z" fill="white"/>
              </svg>
              LinkedIn
            </button>
          </div>

          <p className="auth-legal">
            By continuing you agree to our{' '}
            <a href="/terms-of-service">Terms of Service</a>
            {' '}and{' '}
            <a href="/privacy-policy">Privacy Policy</a>.
          </p>
        </div>
      </div>
    </div>
  )
}