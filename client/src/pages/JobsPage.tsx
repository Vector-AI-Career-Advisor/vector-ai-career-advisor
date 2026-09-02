

import { useState, useEffect, useCallback, useRef } from 'react'
import { fetchJobs, Job, JobFilters } from '../api/jobs'
import { useAuth } from '../hooks/useAuth'
import JobCard from '../components/JobCard'
import JobDrawer from '../components/JobDrawer'
import RangeSlider from '../components/RangeSlider'
import AgentChat from '../components/AgentChat'
import StatsPage from './StatsPage'
import ProfilePage from './ProfilePage'
import ApplicationsPage from './ApplicationsPage'
import ThemeToggle from '../components/ThemeToggle'
import {
  listSavedFilters, createSavedFilter, deleteSavedFilter, type SavedFilter,
} from '../api/savedFilters'
import { summarizeFilterInline } from '../lib/filterSummary'
import {
  SENIORITIES, ROLE_OPTIONS, LOCATION_OPTIONS, POSTED_DATE_OPTIONS, EXP_MIN, EXP_MAX,
} from '../constants'
import './JobsPage.css'

const LIMIT = 50

type Tab = 'jobs' | 'stats' | 'applications' | 'profile'

export default function JobsPage() {
  const { handleLogout } = useAuth()
  const [activeTab, setActiveTab] = useState<Tab>('jobs')

  const [jobs, setJobs]           = useState<Job[]>([])
  const [loading, setLoading]     = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError]         = useState<string | null>(null)
  const [selected, setSelected]   = useState<Job | null>(null)
  const [offset, setOffset]       = useState(0)
  const [hasMore, setHasMore]     = useState(true)
  const [total, setTotal]         = useState(0)

  const [keyword, setKeyword]     = useState('')
  const [seniorities, setSeniorities] = useState<string[]>([])
  const [debouncedKeyword, setDebouncedKeyword] = useState('')
  

  const [postedDate, setPostedDate] = useState('')
  const [roles, setRoles] = useState<string[]>([])
  const [expRange, setExpRange] = useState<[number, number]>([EXP_MIN, EXP_MAX])
  const [debouncedExp, setDebouncedExp] = useState<[number, number]>([EXP_MIN, EXP_MAX])
  const [locations, setLocations] = useState<string[]>([])
  const [skills, setSkills] = useState<string[]>([])
  const [skillInput, setSkillInput] = useState('')

  // Save-filter UX
  const [showSaveModal, setShowSaveModal]   = useState(false)
  const [presetName, setPresetName]         = useState('')
  const [savedMsg, setSavedMsg]             = useState(false)
  const [presets, setPresets]               = useState<SavedFilter[]>([])

  const sentinelRef = useRef<HTMLDivElement | null>(null)

  const [chatOpen, setChatOpen]   = useState(true)
  const [chatWidth, setChatWidth] = useState(700)

  const handleDragStart = (e: React.MouseEvent) => {
    e.preventDefault()
    const startX     = e.clientX
    const startWidth = chatWidth

    const onMove = (e: MouseEvent) => {
      const newWidth = Math.max(280, Math.min(700, startWidth + startX - e.clientX))
      setChatWidth(newWidth)
    }
    const onUp = () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  useEffect(() => {
    const t = setTimeout(() => setDebouncedKeyword(keyword), 350)
    return () => clearTimeout(t)
  }, [keyword])

  // Debounce the experience slider so dragging doesn't fire a request per step
  useEffect(() => {
    const t = setTimeout(() => setDebouncedExp(expRange), 300)
    return () => clearTimeout(t)
  }, [expRange])

  // Keep the saved-filter list in sync whenever we switch tabs
  const reloadPresets = useCallback(() => {
    listSavedFilters().then(setPresets).catch(() => setPresets([]))
  }, [])
  useEffect(() => { reloadPresets() }, [activeTab, reloadPresets])

  const handleDeletePreset = async (id: number) => {
    await deleteSavedFilter(id).catch(() => {})
    reloadPresets()
  }

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    setOffset(0)
    setHasMore(true)
    try {
      const res = await fetchJobs({
        keyword:  debouncedKeyword || undefined,
        seniority: seniorities.length > 0 ? seniorities.join(',') : undefined,
        location: locations.length > 0 ? locations[0] : undefined,
        posted_date: postedDate || undefined,
        roles: roles.length > 0 ? roles : undefined,
        years_experience_min: debouncedExp[0] > EXP_MIN ? debouncedExp[0] : undefined,
        years_experience_max: debouncedExp[1] < EXP_MAX ? debouncedExp[1] : undefined,
        skills: skills.length > 0 ? skills : undefined,
        limit: LIMIT,
        offset: 0,
      })
      setJobs(res.items)
      setTotal(res.total)
      setHasMore(res.items.length < res.total)
      setOffset(res.items.length)
    } catch {
      setError('Failed to load jobs. Please try again.')
    } finally {
      setLoading(false)
    }
  }, [debouncedKeyword, seniorities, locations, postedDate, roles, debouncedExp, skills])

  useEffect(() => { load() }, [load])

  const loadMore = useCallback(async () => {
    if (loadingMore || !hasMore) return
    setLoadingMore(true)
    try {
      const res = await fetchJobs({
        keyword:  debouncedKeyword || undefined,
        seniority: seniorities.length > 0 ? seniorities.join(',') : undefined,
        location: locations.length > 0 ? locations[0] : undefined,
        posted_date: postedDate || undefined,
        roles: roles.length > 0 ? roles : undefined,
        years_experience_min: debouncedExp[0] > EXP_MIN ? debouncedExp[0] : undefined,
        years_experience_max: debouncedExp[1] < EXP_MAX ? debouncedExp[1] : undefined,
        skills: skills.length > 0 ? skills : undefined,
        limit: LIMIT,
        offset,
      })
      setJobs(prev => [...prev, ...res.items])
      setTotal(res.total)
      const newOffset = offset + res.items.length
      setOffset(newOffset)
      setHasMore(newOffset < res.total)
    } catch { /* silent fail */ } finally {
      setLoadingMore(false)
    }
  }, [loadingMore, hasMore, offset, debouncedKeyword, seniorities, locations, postedDate, roles, debouncedExp, skills])

  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel) return
    const observer = new IntersectionObserver(
      entries => { if (entries[0].isIntersecting) loadMore() },
      { rootMargin: '200px' }
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [loadMore])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => e.key === 'Escape' && setSelected(null)
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const clearFilters = () => {
    setKeyword('')
    setSeniorities([])
    setPostedDate('')
    setRoles([])
    setExpRange([EXP_MIN, EXP_MAX])
    setLocations([])
    setSkills([])
    setSkillInput('')
  }

  const expFiltered = expRange[0] > EXP_MIN || expRange[1] < EXP_MAX
  const hasFilters = keyword || seniorities.length > 0 || postedDate || roles.length > 0 || expFiltered || locations.length > 0 || skills.length > 0

  // Apply a saved filter — replaces the whole filter state, then shows Jobs.
  const handleApplyFilter = (filters: JobFilters) => {
    setKeyword(filters.keyword ?? '')
    setSeniorities(filters.seniority ? filters.seniority.split(',') : [])
    setLocations(filters.location ? [filters.location] : [])
    setPostedDate(filters.posted_date ?? '')
    setRoles(filters.roles ?? [])
    setExpRange([filters.years_experience_min ?? EXP_MIN, filters.years_experience_max ?? EXP_MAX])
    setSkills(filters.skills ?? [])
    setActiveTab('jobs')
  }

  // Save current filters as a named, DB-persisted preset
  const handleSavePreset = async () => {
    if (!presetName.trim()) return
    await createSavedFilter(presetName.trim(), {
      keyword:  keyword  || undefined,
      seniority: seniorities.length > 0 ? seniorities.join(',') : undefined,
      location: locations.length > 0 ? locations[0] : undefined,
      posted_date: postedDate || undefined,
      roles: roles.length > 0 ? roles : undefined,
      years_experience_min: expRange[0] > EXP_MIN ? expRange[0] : undefined,
      years_experience_max: expRange[1] < EXP_MAX ? expRange[1] : undefined,
      skills: skills.length > 0 ? skills : undefined,
    }).catch(() => {})
    reloadPresets()
    setPresetName('')
    setShowSaveModal(false)
    setSavedMsg(true)
    setTimeout(() => setSavedMsg(false), 2500)
  }

  return (
    <div className="jobs-root">
      <nav className="navbar">
        <div className="navbar-brand">
          <img src="/icon.ico" alt="Vector" className="logo-icon" style={{ width: '26px', height: '26px' }} />
          <span className="logo-text">Vector</span>
        </div>

        {/* ── Tab switcher ── */}
        <div className="nav-tabs">
          <button
            className={`nav-tab ${activeTab === 'jobs' ? 'active' : ''}`}
            onClick={() => setActiveTab('jobs')}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <rect x="3" y="3" width="7" height="7" rx="1"/>
              <rect x="14" y="3" width="7" height="7" rx="1"/>
              <rect x="3" y="14" width="7" height="7" rx="1"/>
              <rect x="14" y="14" width="7" height="7" rx="1"/>
            </svg>
            Jobs
          </button>

          <button
            className={`nav-tab ${activeTab === 'stats' ? 'active' : ''}`}
            onClick={() => setActiveTab('stats')}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <line x1="18" y1="20" x2="18" y2="10"/>
              <line x1="12" y1="20" x2="12" y2="4"/>
              <line x1="6"  y1="20" x2="6"  y2="14"/>
            </svg>
            Statistics
          </button>

          <button
            className={`nav-tab ${activeTab === 'applications' ? 'active' : ''}`}
            onClick={() => setActiveTab('applications')}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="9" y1="13" x2="15" y2="13"/>
              <line x1="9" y1="17" x2="13" y2="17"/>
            </svg>
            Applications
          </button>

          <button
            className={`nav-tab ${activeTab === 'profile' ? 'active' : ''}`}
            onClick={() => setActiveTab('profile')}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
              <circle cx="12" cy="7" r="4"/>
            </svg>
            Profile
          </button>
        </div>

        <div className="navbar-right">
          <button
            className={`agent-pane-toggle${chatOpen ? ' active' : ''}`}
            onClick={() => setChatOpen(o => !o)}
            title="Career Agent"
            aria-label="Toggle agent chat"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2v3"/>
              <circle cx="12" cy="2" r="1" fill="currentColor" stroke="none"/>
              <rect x="2" y="5" width="20" height="14" rx="6"/>
              <circle cx="9" cy="11" r="1.8" fill="currentColor" stroke="none"/>
              <circle cx="15" cy="11" r="1.8" fill="currentColor" stroke="none"/>
              <path d="M9 15 Q12 17.5 15 15"/>
              <path d="M2 10H0"/><path d="M22 10h2"/>
            </svg>
          </button>
          <ThemeToggle />
          <div className="navbar-divider" />
          <button className="btn-logout" onClick={handleLogout}>
            Sign out
          </button>
        </div>
      </nav>

      <div className="page-body" style={{ paddingRight: chatOpen ? chatWidth : 0 }}>
      {/* ── Statistics view ── */}
      {activeTab === 'stats' && (
        <div className="stats-view">
          <StatsPage />
        </div>
      )}

      {/* ── Applications view ── */}
      {activeTab === 'applications' && (
        <div className="stats-view">
          <ApplicationsPage />
        </div>
      )}

      {/* ── Profile view ── */}
      {activeTab === 'profile' && (
        <div className="stats-view">
          <ProfilePage onApplyFilter={handleApplyFilter} />
        </div>
      )}

      {/* ── Jobs view ── */}
      {activeTab === 'jobs' && (
        <div className="page-columns">

          {/* LEFT: filters + job list */}
          <div className="left-column">
            <div className="jobs-layout">
              <aside className="jobs-sidebar">
                <div className="sidebar-header">
                  <h3>Filters</h3>
                  {hasFilters && (
                    <button className="clear-filters" onClick={clearFilters}>Clear all</button>
                  )}
                </div>

                <div className="filter-group">
                  <label className="filter-label">Search</label>
                  <div className="search-input-wrap">
                    <svg className="search-icon" width="14" height="14" viewBox="0 0 24 24"
                      fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                      <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
                    </svg>
                    <input
                      type="text"
                      placeholder="Role, keyword…"
                      value={keyword}
                      onChange={e => setKeyword(e.target.value)}
                      className="filter-input with-icon"
                    />
                  </div>
                </div>

                <div className="filter-group">
                  <label className="filter-label">Location</label>
                  <div className="filter-tags-input">
                    <div className="tags-display">
                      {locations.map(location => (
                        <span key={location} className="tag">
                          {location}
                          <button
                            type="button"
                            className="tag-remove"
                            onClick={() => setLocations(locations.filter(l => l !== location))}
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                    <select
                      value=""
                      onChange={e => {
                        const loc = e.currentTarget.value
                        if (loc && !locations.includes(loc)) {
                          setLocations([...locations, loc])
                          e.currentTarget.value = ''
                        }
                      }}
                      className="filter-input"
                    >
                      <option value="">Add location…</option>
                      {LOCATION_OPTIONS.map(loc => (
                        <option key={loc} value={loc} disabled={locations.includes(loc)}>
                          {loc}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="filter-group">
                  <label className="filter-label">Seniority</label>
                  <div className="filter-tags-input">
                    <div className="tags-display">
                      {seniorities.map(s => (
                        <span key={s} className="tag">
                          {s}
                          <button
                            type="button"
                            className="tag-remove"
                            onClick={() => setSeniorities(seniorities.filter(x => x !== s))}
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                    <select
                      value={""}
                      onChange={e => {
                        const s = e.currentTarget.value
                        if (s && !seniorities.includes(s)) {
                          setSeniorities([...seniorities, s])
                          e.currentTarget.value = ''
                        }
                      }}
                      className="filter-input"
                    >
                      <option value="">Add seniority…</option>
                      {SENIORITIES.map(s => (
                        <option key={s} value={s} disabled={seniorities.includes(s)}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="filter-group">
                  <label className="filter-label">Posted Date</label>
                  <select
                    value={postedDate}
                    onChange={e => setPostedDate(e.target.value)}
                    className="filter-input"
                  >
                    {POSTED_DATE_OPTIONS.map(option => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="filter-group">
                  <label className="filter-label">Role</label>
                  <div className="filter-tags-input">
                    <div className="tags-display">
                      {roles.map(role => (
                        <span key={role} className="tag">
                          {role}
                          <button
                            type="button"
                            className="tag-remove"
                            onClick={() => setRoles(roles.filter(r => r !== role))}
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                    <select
                      value=""
                      onChange={e => {
                        const role = e.currentTarget.value
                        if (role && !roles.includes(role)) {
                          setRoles([...roles, role])
                          e.currentTarget.value = ''
                        }
                      }}
                      className="filter-input"
                    >
                      <option value="">Add role…</option>
                      {ROLE_OPTIONS.map(role => (
                        <option key={role} value={role} disabled={roles.includes(role)}>
                          {role}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="filter-group">
                  <label className="filter-label">
                    Years of Experience
                    <span className="filter-label-value">
                      {expFiltered
                        ? `${expRange[0]}–${expRange[1] >= EXP_MAX ? `${EXP_MAX}+` : expRange[1]} yrs`
                        : 'Any'}
                    </span>
                  </label>
                  <RangeSlider
                    min={EXP_MIN}
                    max={EXP_MAX}
                    value={expRange}
                    onChange={setExpRange}
                    format={n => (n >= EXP_MAX ? `${EXP_MAX}+` : String(n))}
                  />
                </div>

                <div className="filter-group">
                  <label className="filter-label">Skills</label>
                  <div className="filter-tags-input">
                    <div className="tags-display">
                      {skills.map(skill => (
                        <span key={skill} className="tag">
                          {skill}
                          <button
                            type="button"
                            className="tag-remove"
                            onClick={() => setSkills(skills.filter(s => s !== skill))}
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                    <input
                      type="text"
                      placeholder="Add skill (e.g. Python, React)…"
                      value={skillInput}
                      onChange={e => setSkillInput(e.target.value)}
                      className="filter-input"
                      onKeyDown={e => {
                        if (e.key === 'Enter' && skillInput.trim()) {
                          if (!skills.includes(skillInput.trim())) {
                            setSkills([...skills, skillInput.trim()])
                          }
                          setSkillInput('')
                        }
                      }}
                    />
                  </div>
                </div>

                {/* ── Saved filter presets ── */}
                {presets.length > 0 && (
                  <div className="filter-group">
                    <label className="filter-label">Saved filters</label>
                    <ul className="saved-preset-list">
                      {presets.map(p => (
                        <li key={p.id} className="saved-preset">
                          <button
                            className="saved-preset-apply"
                            title={summarizeFilterInline(p.filters)}
                            onClick={() => handleApplyFilter(p.filters)}
                          >
                            {p.name}
                          </button>
                          <button
                            className="saved-preset-delete"
                            aria-label={`Delete ${p.name}`}
                            onClick={() => handleDeletePreset(p.id)}
                          >
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
                              stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                              <polyline points="3 6 5 6 21 6"/>
                              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                              <path d="M10 11v6M14 11v6"/>
                            </svg>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* ── Save Filters ── */}
                <div className="filter-group" style={{ marginTop: 'auto', paddingTop: '0.5rem' }}>
                  <button
                    className={`btn-save-filters ${!hasFilters ? 'btn-save-filters--dim' : ''}`}
                    onClick={() => hasFilters && setShowSaveModal(true)}
                    disabled={!hasFilters}
                    title={!hasFilters ? 'Set at least one filter to save' : 'Save current filters'}
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
                      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                      <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
                    </svg>
                    Save filters
                  </button>

                  {savedMsg && (
                    <p className="save-success-msg">
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
                        stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                        <polyline points="20 6 9 17 4 12"/>
                      </svg>
                      Saved to your filters
                    </p>
                  )}
                </div>
              </aside>

              <main className="jobs-main">
                {loading ? (
                  <div className="jobs-loading">
                    <div className="spinner" />
                    <p>Loading jobs…</p>
                  </div>
                ) : error ? (
                  <div className="jobs-error">
                    <p>{error}</p>
                    <button className="btn-retry" onClick={load}>Retry</button>
                  </div>
                ) : jobs.length === 0 ? (
                  <div className="jobs-empty">
                    <div className="empty-icon">◈</div>
                    <h3>No jobs found</h3>
                    <p>Try adjusting your filters.</p>
                    {hasFilters && (
                      <button className="btn-retry" onClick={clearFilters}>Clear filters</button>
                    )}
                  </div>
                ) : (
                  <>
                    <div className="jobs-grid">
                      {jobs.map((job, i) => (
                        <div
                          key={job.id}
                          style={{ animationDelay: `${Math.min(i * 30, 400)}ms` }}
                          className="card-wrapper"
                        >
                          <JobCard job={job} onClick={() => setSelected(job)} />
                        </div>
                      ))}
                    </div>
                    <div ref={sentinelRef} style={{ height: 1 }} />
                    {loadingMore && (
                      <div className="jobs-loading-more">
                        <div className="spinner spinner-sm" />
                        <p>Loading more…</p>
                      </div>
                    )}
                    {!hasMore && jobs.length > 0 && (
                      <p className="jobs-end-message">You've seen all {total} listings</p>
                    )}
                  </>
                )}
              </main>
            </div>
          </div>

        </div>
      )}

      </div>

      <div className={`agent-pane${chatOpen ? ' open' : ''}`} style={{ width: chatWidth }}>
        <div className="agent-pane-handle" onMouseDown={handleDragStart} />
        <AgentChat selectedJob={selected} jobs={jobs} onSelectJob={setSelected} />
      </div>

      <JobDrawer job={selected} onClose={() => setSelected(null)} chatWidth={chatOpen ? chatWidth : 0} />

      {/* ── Save Preset Modal ── */}
      {showSaveModal && (
        <>
          <div className="modal-overlay-jobs" onClick={() => setShowSaveModal(false)} />
          <div className="modal-jobs">
            <h3 className="modal-title-jobs">Name this filter preset</h3>
            <p className="modal-sub-jobs">
              {[keyword, seniorities.length > 0 ? seniorities.join(', ') : '', locations.length > 0 ? locations[0] : ''].filter(Boolean).join(' · ')}
            </p>
            <input
              className="modal-input-jobs"
              placeholder="e.g. Senior Berlin Python"
              value={presetName}
              onChange={e => setPresetName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSavePreset()}
              autoFocus
            />
            <div className="modal-actions-jobs">
              <button className="btn-modal-cancel-jobs" onClick={() => setShowSaveModal(false)}>
                Cancel
              </button>
              <button
                className="btn-modal-save-jobs"
                onClick={handleSavePreset}
                disabled={!presetName.trim()}
              >
                Save preset
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}