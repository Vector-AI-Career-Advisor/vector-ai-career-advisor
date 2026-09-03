
import { useEffect, useState } from 'react'
import {
  AreaChart, Area,
  BarChart, Bar,
  PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
  Legend,
} from 'recharts'
import { fetchStats, StatsResponse } from '../api/stats'

import './StatsPage.css'

const ACCENT   = '#7c6af7'
const ACCENT2  = '#9b8ff9'
const GREEN    = '#34d399'
const BLUE     = '#60a5fa'
const ORANGE   = '#fb923c'
const RED      = '#f87171'
const PINK     = '#f472b6'
const TEAL     = '#2dd4bf'
const PIE_COLORS = [ACCENT, GREEN, BLUE, ORANGE, RED, PINK, TEAL, '#facc15', '#a78bfa', '#38bdf8']

// ── Theme-aware hook ──────────────────────────────────────────────────────────
function useChartTheme() {
  const [theme, setTheme] = useState(
    document.documentElement.getAttribute('data-theme') ?? 'dark'
  )

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setTheme(document.documentElement.getAttribute('data-theme') ?? 'dark')
    })
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    })
    return () => observer.disconnect()
  }, [])

  const isLight = theme === 'light'
  return {
    gridColor:  isLight ? 'rgba(0,0,0,0.06)'  : 'rgba(255,255,255,0.05)',
    axisColor:  isLight ? 'rgba(0,0,0,0.15)'  : 'rgba(255,255,255,0.2)',
    axisStyle:  {
      fontSize: 11,
      fill:     isLight ? 'rgba(0,0,0,0.45)'  : 'rgba(255,255,255,0.4)',
      fontFamily: 'var(--font-mono)',
    },
    legendColor: isLight ? 'rgba(0,0,0,0.5)'  : 'rgba(255,255,255,0.55)',
  }
}

// ── Custom tooltip ─────────────────────────────────────────────────────────────
function ChartTooltip({ active, payload, label, valueLabel = 'Jobs' }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-label">{label}</div>
      {payload.map((p: any, i: number) => (
        <div key={i} className="chart-tooltip-value">
          {p.name ?? valueLabel}: <strong style={{ color: p.color ?? ACCENT2 }}>{p.value}</strong>
        </div>
      ))}
    </div>
  )
}

function fmtDate(d: string) {
  return new Date(d + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function trunc(s: string, n = 18) {
  return s.length > n ? s.slice(0, n) + '…' : s
}

export default function StatsPage() {
  const [stats, setStats]           = useState<StatsResponse | null>(null)
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState<string | null>(null)
  const [activeRole, setActiveRole] = useState<string>('')

  // ← use the hook here
  const { gridColor, axisColor, axisStyle, legendColor } = useChartTheme()

  useEffect(() => {
    fetchStats()
      .then(data => {
        setStats(data)
        const roles = Object.keys(data.skills_by_role)
        if (roles.length) setActiveRole(roles[0])
      })
      .catch(() => setError('Failed to load insights.'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="stats-loading">
      <div className="spinner" />
      <p>Crunching numbers…</p>
    </div>
  )

  if (error || !stats) return (
    <div className="stats-error">
      <p>{error ?? 'No data available.'}</p>
    </div>
  )

  const { summary, jobs_per_day, top_companies, jobs_by_location, top_skills, by_seniority, skills_by_role } = stats
  const roles = Object.keys(skills_by_role)
  const roleSkills = skills_by_role[activeRole] ?? []

  return (
    <div className="stats-root">
     


      {/* graph of job post per day
      <div className="stats-section">
        <div className="stats-section-header">
          <span className="stats-section-title">Listings Over Time</span>
          <span className="stats-section-badge">last 60 days</span>
        </div>
        <div className="chart-card">
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={jobs_per_day} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={ACCENT} stopOpacity={0.35} />
                  <stop offset="95%" stopColor={ACCENT} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
              <XAxis dataKey="date" tickFormatter={fmtDate} tick={axisStyle} stroke={axisColor} tickLine={false} interval="preserveStartEnd" />
              <YAxis tick={axisStyle} stroke={axisColor} tickLine={false} axisLine={false} />
              <Tooltip content={<ChartTooltip valueLabel="Jobs added" />} labelFormatter={fmtDate} />
              <Area type="monotone" dataKey="count" stroke={ACCENT} strokeWidth={2} fill="url(#areaGrad)" dot={false} activeDot={{ r: 4, fill: ACCENT2, strokeWidth: 0 }} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>*/}

      {/* ── Two-column: companies + locations ── */}
      <div className="stats-grid-2">

        <div className="stats-section">
          <div className="stats-section-header">
            <span className="stats-section-title">Top Hiring Companies</span>
            <span className="stats-section-badge">top 15</span>
          </div>
          <div className="chart-card">
            <ResponsiveContainer width="100%" height={340}>
              <BarChart data={top_companies.map(c => ({ ...c, company: trunc(c.company) }))} layout="vertical" margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} horizontal={false} />
                <XAxis type="number" tick={axisStyle} stroke={axisColor} tickLine={false} axisLine={false} />
                <YAxis dataKey="company" type="category" tick={{ ...axisStyle, fontSize: 10 }} stroke={axisColor} tickLine={false} width={110} />
                <Tooltip content={<ChartTooltip valueLabel="Listings" />} cursor={{ fill: 'rgba(124,106,247,0.06)' }} />
                <Bar dataKey="count" name="Listings" radius={[0, 4, 4, 0]} maxBarSize={16}>
                  {top_companies.map((_, i) => <Cell key={i} fill={`rgba(124,106,247,${1 - i * 0.055})`} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="stats-section">
          <div className="stats-section-header">
            <span className="stats-section-title">Jobs by Location</span>
            <span className="stats-section-badge">top 15</span>
          </div>
          <div className="chart-card">
            <ResponsiveContainer width="100%" height={340}>
              <BarChart data={jobs_by_location.map(l => ({ ...l, location: trunc(l.location) }))} layout="vertical" margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} horizontal={false} />
                <XAxis type="number" tick={axisStyle} stroke={axisColor} tickLine={false} axisLine={false} />
                <YAxis dataKey="location" type="category" tick={{ ...axisStyle, fontSize: 10 }} stroke={axisColor} tickLine={false} width={110} />
                <Tooltip content={<ChartTooltip valueLabel="Jobs" />} cursor={{ fill: 'rgba(96,165,250,0.06)' }} />
                <Bar dataKey="count" name="Jobs" radius={[0, 4, 4, 0]} maxBarSize={16}>
                  {jobs_by_location.map((_, i) => <Cell key={i} fill={`rgba(96,165,250,${1 - i * 0.055})`} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* ── Two-column: top skills + seniority ── */}
      <div className="stats-grid-2">

        <div className="stats-section">
          <div className="stats-section-header">
            <span className="stats-section-title">Most In-Demand Technologies</span>
            <span className="stats-section-badge">top 20</span>
          </div>
          <div className="chart-card">
            <ResponsiveContainer width="100%" height={340}>
              <BarChart data={top_skills} margin={{ top: 10, right: 10, left: -10, bottom: 60 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
                <XAxis dataKey="skill" tick={{ ...axisStyle, fontSize: 10 }} stroke={axisColor} tickLine={false} angle={-40} textAnchor="end" interval={0} />
                <YAxis tick={axisStyle} stroke={axisColor} tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTooltip valueLabel="Occurrences" />} cursor={{ fill: 'rgba(52,211,153,0.06)' }} />
                <Bar dataKey="count" name="Occurrences" radius={[4, 4, 0, 0]} maxBarSize={28}>
                  {top_skills.map((_, i) => <Cell key={i} fill={`rgba(52,211,153,${1 - i * 0.042})`} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="stats-section">
          <div className="stats-section-header">
            <span className="stats-section-title">Jobs by Seniority</span>
          </div>
          <div className="chart-card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <ResponsiveContainer width="100%" height={340}>
              <PieChart>
                <Pie data={by_seniority} dataKey="count" nameKey="seniority" cx="50%" cy="45%" innerRadius={70} outerRadius={110} paddingAngle={3} strokeWidth={0}>
                  {by_seniority.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Pie>
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null
                    const { name, value } = payload[0]
                    const total = by_seniority.reduce((s, r) => s + r.count, 0)
                    const pct   = total && value !== undefined ? ((Number(value) / total) * 100).toFixed(1) : 0
                    return (
                      <div className="chart-tooltip">
                        <div className="chart-tooltip-label">{name}</div>
                        <div className="chart-tooltip-value">{value} jobs ({pct}%)</div>
                      </div>
                    )
                  }}
                />
                {/* ← legendColor now adapts to theme */}
                <Legend
                  formatter={(value) => (
                    <span style={{ fontSize: 11, color: legendColor, fontFamily: 'var(--font-mono)' }}>
                      {value}
                    </span>
                  )}
                  iconType="circle"
                  iconSize={8}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* ── Skills by Role ── */}
      {roles.length > 0 && (
        <div className="stats-section">
          <div className="stats-section-header">
            <span className="stats-section-title">Top Skills by Role</span>
            <span className="stats-section-badge">{roles.length} roles</span>
          </div>
          <div className="chart-card">
            <div className="role-tabs">
              {roles.map(role => (
                <button key={role} className={`role-tab ${activeRole === role ? 'active' : ''}`} onClick={() => setActiveRole(role)}>
                  {role}
                </button>
              ))}
            </div>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={roleSkills} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
                <XAxis dataKey="skill" tick={axisStyle} stroke={axisColor} tickLine={false} />
                <YAxis tick={axisStyle} stroke={axisColor} tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTooltip valueLabel="Job postings" />} cursor={{ fill: 'rgba(124,106,247,0.06)' }} />
                <Bar dataKey="count" name="Job postings" radius={[4, 4, 0, 0]} maxBarSize={40}>
                  {roleSkills.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

    </div>
  )
}

function SummaryCard({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="summary-card">
      <span className="summary-label">{label}</span>
      <span className="summary-value">{value}</span>
      <span className="summary-sub">{sub}</span>
    </div>
  )
}