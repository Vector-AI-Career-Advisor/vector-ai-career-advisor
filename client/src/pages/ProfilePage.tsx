// src/pages/ProfilePage.tsx

import { useState, useEffect, useRef, useCallback } from 'react'
import api from '../api/client'
import {
  uploadResume, getMyResume, deleteResume,
  listResumes, getResume, setActiveResume, renameResume,
} from '../api/resumes'
import type { ResumeInfo, ResumeListItem, ResumeDetail } from '../api/resumes'
import type { JobFilters } from '../api/jobs'
import {
  getProfileSummary, type ProfileSummary,
  getJobCore, updateJobCore, type JobCore,
  getJobPreferences, updateJobPreferences, type JobPreferences,
} from '../api/profile'
import { ROLE_OPTIONS, LOCATION_OPTIONS, SENIORITIES, EDUCATION_LEVELS, EXPERIENCE_OPTIONS } from '../constants'
import './ProfilePage.css'

// ── Saved-filter preset shape ──────────────────────────────────────────────

export interface FilterPreset {
  id: string
  name: string
  keyword?: string
  seniority?: string
  location?: string
  posted_date?: string
  roles?: string[]
  years_experience_min?: number
  skills?: string[]
  createdAt: string
}

const PRESETS_KEY = 'vector_saved_filters'

export function loadPresets(): FilterPreset[] {
  try {
    return JSON.parse(localStorage.getItem(PRESETS_KEY) ?? '[]')
  } catch {
    return []
  }
}

export function savePreset(preset: Omit<FilterPreset, 'id' | 'createdAt'>): FilterPreset {
  const presets = loadPresets()
  const next: FilterPreset = {
    ...preset,
    id: crypto.randomUUID(),
    createdAt: new Date().toISOString(),
  }
  localStorage.setItem(PRESETS_KEY, JSON.stringify([next, ...presets]))
  return next
}

export function deletePreset(id: string): void {
  const presets = loadPresets().filter(p => p.id !== id)
  localStorage.setItem(PRESETS_KEY, JSON.stringify(presets))
}

// ── Component ──────────────────────────────────────────────────────────────

interface Props {
  /** Called when the user clicks a saved-filter preset to apply it */
  onApplyFilter?: (filters: JobFilters) => void
}

export default function ProfilePage({ onApplyFilter }: Props) {
  const [email, setEmail]         = useState<string | null>(null)
  const [memberSince, setMemberSince] = useState<string | null>(null)
  const [resume, setResume]       = useState<ResumeInfo | null>(null)
  const [resumeLoading, setResumeLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [deleting, setDeleting]   = useState(false)
  const [uploadMsg, setUploadMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)
  const [dragging, setDragging]   = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const [profileSummary, setProfileSummary] = useState<ProfileSummary | null>(null)
  const [presets, setPresets]     = useState<FilterPreset[]>([])
  const [showSaveModal, setShowSaveModal] = useState(false)
  const [presetName, setPresetName] = useState('')

  // ── Résumés (multiple) ─────────────────────────────────────────────────
  const [resumeList, setResumeList] = useState<ResumeListItem[]>([])
  const [resumeSkills, setResumeSkills] = useState<Record<number, ResumeDetail>>({})
  const [expandedResume, setExpandedResume] = useState<number | null>(null)
  const [renamingId, setRenamingId] = useState<number | null>(null)
  const [renameText, setRenameText] = useState('')

  // ── Search restrictions (tier 1) & preferences (tier 2) ────────────────
  const [core, setCore] = useState<JobCore>({ min_experience: null, max_experience: null, education_level: null })
  const [prefsForm, setPrefsForm] = useState<JobPreferences>({
    preferred_roles: [], preferred_locations: [], preferred_seniority: [], remote_only: false,
  })
  const [coreMsg, setCoreMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)
  const [prefsMsg, setPrefsMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)
  const [savingCore, setSavingCore] = useState(false)
  const [savingPrefs, setSavingPrefs] = useState(false)

  // ── Load user info ──────────────────────────────────────────────────────
  useEffect(() => {
    api.get('/auth/me')
      .then(({ data }) => {
        setEmail(data.email)
        if (data.created_at) {
          setMemberSince(
            new Date(data.created_at).toLocaleDateString('en-US', {
              year: 'numeric', month: 'long', day: 'numeric',
            })
          )
        }
      })
      .catch(() => {/* ignore */})
  }, [])

  // ── Load resume and profile summary ──────────────────────────────────────
  const fetchResume = useCallback(async () => {
    setResumeLoading(true)
    try {
      const [nextResume, summary, list] = await Promise.all([
        getMyResume(),
        getProfileSummary().catch(() => null),
        listResumes().catch(() => [] as ResumeListItem[]),
      ])
      setResume(nextResume)
      setProfileSummary(summary)
      setResumeList(list)
    } finally {
      setResumeLoading(false)
    }
  }, [])

  useEffect(() => { fetchResume() }, [fetchResume])

  // ── Load presets ────────────────────────────────────────────────────────
  useEffect(() => { setPresets(loadPresets()) }, [])

  // ── Load core + preferences ─────────────────────────────────────────────
  useEffect(() => {
    getJobCore().then(setCore).catch(() => {/* ignore */})
    getJobPreferences().then(setPrefsForm).catch(() => {/* ignore */})
  }, [])

  const toggleResumeSkills = async (id: number) => {
    if (expandedResume === id) { setExpandedResume(null); return }
    setExpandedResume(id)
    if (!resumeSkills[id]) {
      try {
        const detail = await getResume(id)
        setResumeSkills(prev => ({ ...prev, [id]: detail }))
      } catch {/* ignore */}
    }
  }

  const handleActivateResume = async (id: number) => {
    await setActiveResume(id)
    await fetchResume()
  }

  const handleRenameResume = async (id: number) => {
    const title = renameText.trim()
    setRenamingId(null)
    if (title) {
      await renameResume(id, title)
      await fetchResume()
    }
  }

  const handleDeleteResume = async (id: number) => {
    if (!window.confirm('Remove this résumé?')) return
    await deleteResume(id)
    setResumeSkills(prev => { const n = { ...prev }; delete n[id]; return n })
    await fetchResume()
  }

  const saveCore = async () => {
    setSavingCore(true)
    setCoreMsg(null)
    try {
      const saved = await updateJobCore(core)
      setCore(saved)
      setCoreMsg({ type: 'ok', text: 'Search restrictions saved.' })
    } catch {
      setCoreMsg({ type: 'err', text: 'Could not save. Try again.' })
    } finally {
      setSavingCore(false)
    }
  }

  const savePrefs = async () => {
    setSavingPrefs(true)
    setPrefsMsg(null)
    try {
      const saved = await updateJobPreferences(prefsForm)
      setPrefsForm(saved)
      setPrefsMsg({ type: 'ok', text: 'Job preferences saved.' })
    } catch {
      setPrefsMsg({ type: 'err', text: 'Could not save. Try again.' })
    } finally {
      setSavingPrefs(false)
    }
  }

  const addPref = (key: 'preferred_roles' | 'preferred_locations' | 'preferred_seniority', value: string) => {
    if (!value || prefsForm[key].includes(value)) return
    setPrefsForm({ ...prefsForm, [key]: [...prefsForm[key], value] })
  }
  const removePref = (key: 'preferred_roles' | 'preferred_locations' | 'preferred_seniority', value: string) => {
    setPrefsForm({ ...prefsForm, [key]: prefsForm[key].filter(v => v !== value) })
  }

  // ── Resume upload ───────────────────────────────────────────────────────
  const handleFile = async (file: File) => {
    const name = file.name.toLowerCase()
    if (!name.endsWith('.pdf') && !name.endsWith('.docx')) {
      setUploadMsg({ type: 'err', text: 'Only PDF or DOCX files are accepted.' })
      return
    }
    setUploading(true)
    setUploadMsg(null)
    try {
      await uploadResume(file)
      setUploadMsg({ type: 'ok', text: 'Résumé uploaded — it is now your active résumé.' })
      await fetchResume()
    } catch {
      setUploadMsg({ type: 'err', text: 'Upload failed. Please try again.' })
    } finally {
      setUploading(false)
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
    e.target.value = ''
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleFile(file)
  }

  const handleDelete = async () => {
    if (!window.confirm('Remove your resume?')) return
    setDeleting(true)
    try {
      await deleteResume()
      setResume(null)
      setUploadMsg(null)
    } finally {
      setDeleting(false)
    }
  }

  // ── Presets ──────────────────────────────────────────────────────────────
  const handleDeletePreset = (id: string) => {
    deletePreset(id)
    setPresets(loadPresets())
  }

  const handleSavePreset = () => {
    if (!presetName.trim()) return
    savePreset({ name: presetName.trim() })
    setPresets(loadPresets())
    setPresetName('')
    setShowSaveModal(false)
  }

  // ── Derived ──────────────────────────────────────────────────────────────
  const initials = email ? email.slice(0, 2).toUpperCase() : '??'

  const fmt = (d?: string) =>
    d ? new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) : '—'

  const user = profileSummary?.user ?? {}
  const skills = profileSummary?.skills ?? []
  const softSkills = profileSummary?.soft_skills ?? []
  const education = profileSummary?.education ?? {}
  const experience = profileSummary?.work_experience ?? []
  const prefs = profileSummary?.work_preferences ?? {}

  return (
    <div className="profile-root">

      {/* ── User Info ───────────────────────────────────────────────── */}
      <section className="profile-section">
        <SectionHeader title="Account" badge="You" />

        <div className="profile-card user-card">
          <div className="user-avatar-lg">{initials}</div>
          <div className="user-info">
            <p className="user-email">{email ?? '—'}</p>
            {memberSince && (
              <p className="user-since">Member since {memberSince}</p>
            )}
          </div>
          <div className="user-badge">
            <span className="badge-dot" />
            Active
          </div>
        </div>
      </section>

      {/* ── Profile Snapshot ─────────────────────────────────────────── */}
      <section className="profile-section">
        <SectionHeader title="Profile" badge="Summary" active />
        <div className="profile-card profile-summary-card">
          <div className="summary-grid">
            <div>
              <div className="summary-label">Name</div>
              <div className="summary-value">{user.first_name || user.last_name ? `${user.first_name ?? ''} ${user.last_name ?? ''}`.trim() : 'Not filled yet'}</div>
            </div>
            <div>
              <div className="summary-label">Location</div>
              <div className="summary-value">{user.city || 'Not set'}</div>
            </div>
            <div>
              <div className="summary-label">Career stage</div>
              <div className="summary-value">{user.career_stage || 'Not set'}</div>
            </div>
            <div>
              <div className="summary-label">Experience</div>
              <div className="summary-value">{user.years_experience != null ? `${user.years_experience} yrs` : 'Not set'}</div>
            </div>
          </div>

          <div className="mini-section">
            <div className="mini-title">Education</div>
            <div className="mini-body">
              {education.degree_type || education.field_of_study || education.school ? (
                <>
                  <div>{education.degree_type || 'Degree'} · {education.field_of_study || 'Field'}</div>
                  <div>{education.school || 'School'}{education.graduation_year ? ` · ${education.graduation_year}` : ''}</div>
                </>
              ) : (
                <div>Education not added yet.</div>
              )}
            </div>
          </div>

          <div className="mini-section">
            <div className="mini-title">Skills</div>
            <div className="skill-tags">
              {skills.length ? skills.map(skill => <span key={skill} className="skill-tag">{skill}</span>) : <span className="muted-empty">No skills saved yet.</span>}
            </div>
          </div>

          <div className="mini-section">
            <div className="mini-title">Soft skills</div>
            <div className="skill-tags">
              {softSkills.length ? softSkills.map(skill => <span key={skill} className="skill-tag soft">{skill}</span>) : <span className="muted-empty">No soft skills saved yet.</span>}
            </div>
          </div>

          <div className="mini-section">
            <div className="mini-title">Experience</div>
            <div className="mini-body">
              {experience.length ? experience.map((item, idx) => (
                <div key={`${item.company ?? 'company'}-${idx}`} className="experience-row">
                  <strong>{item.position || 'Role'}</strong>
                  <span>{item.company || 'Company'}</span>
                  <span>{item.start_date ? new Date(item.start_date).getFullYear() : ''}{item.end_date ? ` - ${new Date(item.end_date).getFullYear()}` : ' - Present'}</span>
                </div>
              )) : <div>No work experience added yet.</div>}
            </div>
          </div>

          <div className="mini-section">
            <div className="mini-title">Job filters</div>
            <div className="skill-tags">
              {Object.entries(prefs).filter(([, value]) => value).map(([key]) => (
                <span key={key} className="skill-tag pref">{key}</span>
              ))}
              {!Object.keys(prefs).length && <span className="muted-empty">No preference filters saved yet.</span>}
            </div>
          </div>
        </div>
      </section>

      {/* ── Search restrictions (tier 1: core) ─────────────────────── */}
      <section className="profile-section">
        <SectionHeader title="Search restrictions" badge="Core" active />
        <div className="profile-card">
          <p className="card-hint">Hard limits — jobs outside these are excluded from your matches.</p>
          <div className="core-grid">
            <label className="field">
              <span className="field-label">Min years experience</span>
              <select
                className="pref-select"
                value={core.min_experience ?? ''}
                onChange={e => setCore({ ...core, min_experience: e.target.value === '' ? null : Number(e.target.value) })}
              >
                {EXPERIENCE_OPTIONS.map(o => <option key={`min${o.label}`} value={o.value}>{o.label}</option>)}
              </select>
            </label>
            <label className="field">
              <span className="field-label">Max years experience</span>
              <select
                className="pref-select"
                value={core.max_experience ?? ''}
                onChange={e => setCore({ ...core, max_experience: e.target.value === '' ? null : Number(e.target.value) })}
              >
                {EXPERIENCE_OPTIONS.map(o => <option key={`max${o.label}`} value={o.value}>{o.label}</option>)}
              </select>
            </label>
            <label className="field">
              <span className="field-label">Education level</span>
              <select
                className="pref-select"
                value={core.education_level ?? ''}
                onChange={e => setCore({ ...core, education_level: e.target.value || null })}
              >
                {EDUCATION_LEVELS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </label>
          </div>
          <div className="save-row">
            <button className="btn-modal-save" onClick={saveCore} disabled={savingCore}>
              {savingCore ? 'Saving…' : 'Save restrictions'}
            </button>
            {coreMsg && (
              <span className={`upload-msg upload-msg-${coreMsg.type}`}>
                {coreMsg.type === 'ok' ? <CheckIcon /> : <WarnIcon />}{coreMsg.text}
              </span>
            )}
          </div>
        </div>
      </section>

      {/* ── Job preferences (tier 2) ───────────────────────────────── */}
      <section className="profile-section">
        <SectionHeader title="Job preferences" badge="Soft" active />
        <div className="profile-card">
          <p className="card-hint">Soft filters — used to rank and filter, relaxed automatically when too few jobs match.</p>

          <ChipSelect
            label="Preferred roles" options={ROLE_OPTIONS} selected={prefsForm.preferred_roles}
            onAdd={v => addPref('preferred_roles', v)} onRemove={v => removePref('preferred_roles', v)}
          />
          <ChipSelect
            label="Preferred locations" options={LOCATION_OPTIONS} selected={prefsForm.preferred_locations}
            onAdd={v => addPref('preferred_locations', v)} onRemove={v => removePref('preferred_locations', v)}
          />
          <ChipSelect
            label="Preferred seniority" options={SENIORITIES} selected={prefsForm.preferred_seniority}
            onAdd={v => addPref('preferred_seniority', v)} onRemove={v => removePref('preferred_seniority', v)}
          />

          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={prefsForm.remote_only}
              onChange={e => setPrefsForm({ ...prefsForm, remote_only: e.target.checked })}
            />
            <span>Remote only</span>
          </label>

          <div className="save-row">
            <button className="btn-modal-save" onClick={savePrefs} disabled={savingPrefs}>
              {savingPrefs ? 'Saving…' : 'Save preferences'}
            </button>
            {prefsMsg && (
              <span className={`upload-msg upload-msg-${prefsMsg.type}`}>
                {prefsMsg.type === 'ok' ? <CheckIcon /> : <WarnIcon />}{prefsMsg.text}
              </span>
            )}
          </div>
        </div>
      </section>

      {/* ── Résumés (tier 3: skills) ───────────────────────────────── */}
      <section className="profile-section">
        <SectionHeader
          title="Résumés"
          badge={resumeList.length ? `${resumeList.length}` : 'None'}
          active={resumeList.length > 0}
        />

        <div className="profile-card">
          <p className="card-hint">
            Skills are extracted from each résumé. Your <strong>active</strong> résumé drives job
            matching, cover letters, and résumé tailoring.
          </p>

          {resumeLoading ? (
            <div className="profile-loading"><div className="spinner" /><span>Loading résumés…</span></div>
          ) : (
            <ul className="resume-list">
              {resumeList.map(r => (
                <li key={r.id} className={`resume-list-item ${r.is_active ? 'is-active' : ''}`}>
                  <div className="resume-list-main">
                    <div className="resume-file-icon"><PdfIcon /></div>
                    <div className="resume-details">
                      {renamingId === r.id ? (
                        <input
                          className="modal-input"
                          value={renameText}
                          autoFocus
                          onChange={e => setRenameText(e.target.value)}
                          onKeyDown={e => e.key === 'Enter' && handleRenameResume(r.id)}
                          onBlur={() => handleRenameResume(r.id)}
                        />
                      ) : (
                        <p className="resume-filename">
                          {r.title || r.filename}
                          {r.is_active && <span className="resume-active-badge">Active</span>}
                        </p>
                      )}
                      <div className="resume-dates">
                        <span>{r.filename}</span>
                        <span>· {fmt(r.uploaded_at)}</span>
                        <span>· {r.skill_count} skills</span>
                      </div>
                    </div>
                  </div>
                  <div className="resume-actions">
                    {!r.is_active && (
                      <button className="btn-replace" onClick={() => handleActivateResume(r.id)}>
                        Make active
                      </button>
                    )}
                    <button className="btn-replace" onClick={() => toggleResumeSkills(r.id)}>
                      {expandedResume === r.id ? 'Hide skills' : 'Skills'}
                    </button>
                    <button
                      className="btn-replace"
                      onClick={() => { setRenamingId(r.id); setRenameText(r.title || '') }}
                    >
                      Rename
                    </button>
                    <button
                      className="btn-delete-resume"
                      onClick={() => handleDeleteResume(r.id)}
                      aria-label="Delete résumé"
                    >
                      <TrashIcon />
                    </button>
                  </div>
                  {expandedResume === r.id && (
                    <div className="resume-skill-panel">
                      <div className="mini-title">Extracted skills</div>
                      <div className="skill-tags">
                        {resumeSkills[r.id]?.skills.length
                          ? resumeSkills[r.id].skills.map(s => <span key={s} className="skill-tag">{s}</span>)
                          : <span className="muted-empty">No skills extracted.</span>}
                      </div>
                      {!!resumeSkills[r.id]?.soft_skills.length && (
                        <>
                          <div className="mini-title" style={{ marginTop: '.6rem' }}>Soft skills</div>
                          <div className="skill-tags">
                            {resumeSkills[r.id].soft_skills.map(s => <span key={s} className="skill-tag soft">{s}</span>)}
                          </div>
                        </>
                      )}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}

          {/* Drop zone — always available to add another résumé */}
          <div
            className={`drop-zone ${dragging ? 'dragging' : ''} ${uploading ? 'uploading' : ''}`}
            onDragOver={e => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => !uploading && fileRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={e => e.key === 'Enter' && fileRef.current?.click()}
          >
            {uploading ? (
              <><div className="spinner" /><p className="drop-title">Uploading…</p></>
            ) : (
              <>
                <div className="drop-icon"><UploadIcon /></div>
                <p className="drop-title">Add a résumé</p>
                <p className="drop-sub">PDF or DOCX · Click or drag to upload</p>
              </>
            )}
          </div>

          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx"
            style={{ display: 'none' }}
            onChange={handleInputChange}
          />

          {uploadMsg && (
            <div className={`upload-msg upload-msg-${uploadMsg.type}`}>
              {uploadMsg.type === 'ok' ? <CheckIcon /> : <WarnIcon />}
              {uploadMsg.text}
            </div>
          )}
        </div>
      </section>

      {/* ── Saved Filters ───────────────────────────────────────────── */}
      <section className="profile-section">
        <div className="section-header-row">
          <SectionHeader
            title="Saved Filters"
            badge={presets.length > 0 ? `${presets.length}` : 'None'}
            active={presets.length > 0}
          />
        </div>

        <div className="profile-card presets-card">
          {presets.length === 0 ? (
            <div className="presets-empty">
              <div className="presets-empty-icon"><FilterIcon /></div>
              <p className="presets-empty-title">No saved filters yet</p>
              <p className="presets-empty-sub">
                Head to the Jobs tab, set your filters, then save them here for quick access.
              </p>
            </div>
          ) : (
            <ul className="presets-list">
              {presets.map(p => (
                <li key={p.id} className="preset-item">
                  <div className="preset-meta">
                    <span className="preset-name">{p.name}</span>
                    <div className="preset-tags">
                      {p.keyword   && <Tag label={p.keyword}   color="purple" />}
                      {p.seniority && <Tag label={p.seniority} color="blue"   />}
                      {p.location  && <Tag label={p.location}  color="green"  />}
                    </div>
                  </div>
                  <div className="preset-actions">
                    {onApplyFilter && (
                      <button
                        className="btn-apply-preset"
                        onClick={() => onApplyFilter({
                          keyword:  p.keyword,
                          seniority: p.seniority,
                          location: p.location,
                        })}
                      >
                        Apply
                      </button>
                    )}
                    <button
                      className="btn-delete-preset"
                      onClick={() => handleDeletePreset(p.id)}
                      aria-label="Delete preset"
                    >
                      <TrashIcon />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      {/* ── Save preset modal ───────────────────────────────────────── */}
      {showSaveModal && (
        <>
          <div className="modal-overlay" onClick={() => setShowSaveModal(false)} />
          <div className="modal">
            <h3 className="modal-title">Save Filter Preset</h3>
            <input
              className="modal-input"
              placeholder="e.g. Senior Berlin Python"
              value={presetName}
              onChange={e => setPresetName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSavePreset()}
              autoFocus
            />
            <div className="modal-actions">
              <button className="btn-modal-cancel" onClick={() => setShowSaveModal(false)}>
                Cancel
              </button>
              <button
                className="btn-modal-save"
                onClick={handleSavePreset}
                disabled={!presetName.trim()}
              >
                Save
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

// ── Sub-components ──────────────────────────────────────────────────────────

function SectionHeader({ title, badge, active }: { title: string; badge: string; active?: boolean }) {
  return (
    <div className="stats-section-header" style={{ marginBottom: '1rem' }}>
      <span className="stats-section-title">{title}</span>
      <span className={`stats-section-badge ${active ? 'badge-active' : ''}`}>{badge}</span>
    </div>
  )
}

function Tag({ label, color }: { label: string; color: 'purple' | 'blue' | 'green' }) {
  return <span className={`preset-tag preset-tag-${color}`}>{label}</span>
}

function ChipSelect({
  label, options, selected, onAdd, onRemove,
}: {
  label: string
  options: string[]
  selected: string[]
  onAdd: (v: string) => void
  onRemove: (v: string) => void
}) {
  return (
    <div className="field">
      <span className="field-label">{label}</span>
      <div className="skill-tags">
        {selected.map(v => (
          <span key={v} className="skill-tag pref">
            {v}
            <button className="chip-remove" onClick={() => onRemove(v)} aria-label={`Remove ${v}`}>×</button>
          </span>
        ))}
        {!selected.length && <span className="muted-empty">None selected.</span>}
      </div>
      <select
        className="pref-select"
        value=""
        onChange={e => { onAdd(e.target.value); e.currentTarget.value = '' }}
      >
        <option value="">Add {label.toLowerCase()}…</option>
        {options.filter(o => !selected.includes(o)).map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  )
}

// ── Icons ───────────────────────────────────────────────────────────────────

function PdfIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
      <line x1="9" y1="13" x2="15" y2="13"/>
      <line x1="9" y1="17" x2="13" y2="17"/>
    </svg>
  )
}

function UploadIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
      <polyline points="17 8 12 3 7 8"/>
      <line x1="12" y1="3" x2="12" y2="15"/>
    </svg>
  )
}

function TrashIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6"/>
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
      <path d="M10 11v6M14 11v6"/>
      <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
      <polyline points="20 6 9 17 4 12"/>
    </svg>
  )
}

function WarnIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
      <circle cx="12" cy="12" r="10"/>
      <line x1="12" y1="8" x2="12" y2="12"/>
      <line x1="12" y1="16" x2="12.01" y2="16"/>
    </svg>
  )
}

function FilterIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
    </svg>
  )
}