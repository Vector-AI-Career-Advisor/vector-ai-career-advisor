// src/pages/ProfilePage.tsx

import { useState, useEffect, useRef, useCallback } from 'react'
import api from '../api/client'
import { uploadResume, getMyResume, deleteResume } from '../api/resumes'
import type { ResumeInfo } from '../api/resumes'
import type { JobFilters } from '../api/jobs'
import { getProfileSummary, type ProfileSummary } from '../api/profile'
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
      const [nextResume, summary] = await Promise.all([
        getMyResume(),
        getProfileSummary().catch(() => null),
      ])
      setResume(nextResume)
      setProfileSummary(summary)
    } finally {
      setResumeLoading(false)
    }
  }, [])

  useEffect(() => { fetchResume() }, [fetchResume])

  // ── Load presets ────────────────────────────────────────────────────────
  useEffect(() => { setPresets(loadPresets()) }, [])

  // ── Resume upload ───────────────────────────────────────────────────────
  const handleFile = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setUploadMsg({ type: 'err', text: 'Only PDF files are accepted.' })
      return
    }
    setUploading(true)
    setUploadMsg(null)
    try {
      await uploadResume(file)
      setUploadMsg({ type: 'ok', text: 'Resume uploaded successfully!' })
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

      {/* ── Resume ─────────────────────────────────────────────────── */}
      <section className="profile-section">
        <SectionHeader title="Resume" badge={resume ? 'On file' : 'None'} active={!!resume} />

        <div className="profile-card">
          {resumeLoading ? (
            <div className="profile-loading">
              <div className="spinner" />
              <span>Loading resume…</span>
            </div>
          ) : resume ? (
            <div className="resume-info">
              <div className="resume-file-icon">
                <PdfIcon />
              </div>
              <div className="resume-details">
                <p className="resume-filename">{resume.filename}</p>
                <div className="resume-dates">
                  <span>Uploaded {fmt(resume.uploaded_at)}</span>
                  {resume.updated_at !== resume.uploaded_at && (
                    <span>· Updated {fmt(resume.updated_at)}</span>
                  )}
                </div>
              </div>
              <div className="resume-actions">
                <button
                  className="btn-replace"
                  onClick={() => fileRef.current?.click()}
                  disabled={uploading}
                >
                  Replace
                </button>
                <button
                  className="btn-delete-resume"
                  onClick={handleDelete}
                  disabled={deleting}
                  aria-label="Delete resume"
                >
                  <TrashIcon />
                </button>
              </div>
            </div>
          ) : (
            /* Drop zone */
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
                <>
                  <div className="spinner" />
                  <p className="drop-title">Uploading…</p>
                </>
              ) : (
                <>
                  <div className="drop-icon"><UploadIcon /></div>
                  <p className="drop-title">Drop your résumé here</p>
                  <p className="drop-sub">PDF or DOCX · Click or drag to upload</p>
                </>
              )}
            </div>
          )}

          {/* Hidden file input */}
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx"
            style={{ display: 'none' }}
            onChange={handleInputChange}
          />

          {/* Upload feedback */}
          {uploadMsg && (
            <div className={`upload-msg upload-msg-${uploadMsg.type}`}>
              {uploadMsg.type === 'ok' ? <CheckIcon /> : <WarnIcon />}
              {uploadMsg.text}
            </div>
          )}

          {/* Replace drop zone shown when resume exists and replace was clicked */}
          {resume && uploading && (
            <div className="drop-zone uploading" style={{ marginTop: '1rem' }}>
              <div className="spinner" />
              <p className="drop-title">Uploading…</p>
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