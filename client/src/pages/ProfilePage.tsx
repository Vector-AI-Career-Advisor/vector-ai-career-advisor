// src/pages/ProfilePage.tsx

import { useState, useEffect, useRef, useCallback } from 'react'
import api from '../api/client'
import {
  uploadResume, getMyResume, deleteResume,
  listResumes, getResume, setActiveResume, renameResume,
} from '../api/resumes'
import type { ResumeInfo, ResumeListItem, ResumeDetail } from '../api/resumes'
import {
  getProfileSummary, type ProfileSummary,
  updateBasicInfo, updateCareerStage,
  getJobCore, updateJobCore, type JobCore,
  getJobPreferences, updateJobPreferences, type JobPreferences,
  getEducation, addEducation, updateEducation, deleteEducation,
  getWorkExperience, addWorkExperience, updateWorkExperience, deleteWorkExperience,
  type Education, type EducationRow, type WorkExperience, type WorkExperienceRow,
} from '../api/profile'
import {
  ROLE_OPTIONS, LOCATION_OPTIONS, SENIORITIES, EDUCATION_LEVELS, EXPERIENCE_OPTIONS,
  CAREER_STAGE_OPTIONS, humanizeCareerStage,
} from '../constants'
import './ProfilePage.css'

type SummaryUser = ProfileSummary['user']

// Stable identity for the "no summary loaded yet" case, so effects keyed on the
// user object don't re-fire on every render.
const EMPTY_USER: SummaryUser = {}

// ── Component ──────────────────────────────────────────────────────────────

export default function ProfilePage() {
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
  const [educationList, setEducationList]   = useState<EducationRow[]>([])
  const [experienceList, setExperienceList] = useState<WorkExperienceRow[]>([])

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

  // Re-read just the summary after an inline edit — no résumé spinner.
  const reloadSummary = useCallback(async () => {
    const summary = await getProfileSummary().catch(() => null)
    if (summary) setProfileSummary(summary)
  }, [])

  // ── Load education + work experience (editable) ─────────────────────────
  const loadEduExp = useCallback(async () => {
    const [edu, exp] = await Promise.all([
      getEducation().catch(() => [] as EducationRow[]),
      getWorkExperience().catch(() => [] as WorkExperienceRow[]),
    ])
    setEducationList(edu)
    setExperienceList(exp)
  }, [])

  useEffect(() => { loadEduExp() }, [loadEduExp])

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

  // ── Derived ──────────────────────────────────────────────────────────────
  const initials = email ? email.slice(0, 2).toUpperCase() : '??'

  const fmt = (d?: string) =>
    d ? new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) : '—'

  const user = profileSummary?.user ?? EMPTY_USER
  const prefs = profileSummary?.work_preferences ?? {}

  return (
    <div className="profile-root">

      <header className="profile-header">
        <h1 className="profile-title">Your Profile</h1>
        <p className="profile-subtitle">Everything Vector uses to match you with jobs.</p>
      </header>

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
          <BasicsSection user={user} reload={reloadSummary} />

          <EducationSection rows={educationList} reload={loadEduExp} />

          <ExperienceSection rows={experienceList} reload={loadEduExp} />

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

// ── Editable basics (name / location / career stage / experience) ──────────

interface BasicsForm {
  first_name: string
  last_name: string
  city: string
  career_stage: string
  years_experience: number | null
}

function BasicsSection({ user, reload }: { user: SummaryUser; reload: () => Promise<void> }) {
  const toForm = (u: SummaryUser): BasicsForm => ({
    first_name: u.first_name ?? '',
    last_name: u.last_name ?? '',
    city: u.city ?? '',
    career_stage: u.career_stage ?? '',
    years_experience: u.years_experience ?? null,
  })

  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState<BasicsForm>(() => toForm(user))
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)

  // Adopt freshly loaded values, but never clobber an edit in progress.
  useEffect(() => {
    if (!editing) setForm(toForm(user))
  }, [user])   // eslint-disable-line react-hooks/exhaustive-deps

  const fullName = user.first_name || user.last_name
    ? `${user.first_name ?? ''} ${user.last_name ?? ''}`.trim()
    : 'Not filled yet'

  const save = async () => {
    if (busy) return
    const first = form.first_name.trim()
    const last = form.last_name.trim()
    const city = form.city.trim()

    // The two endpoints back different columns — only call the ones that moved.
    const basicDirty =
      first !== (user.first_name ?? '') ||
      last !== (user.last_name ?? '') ||
      city !== (user.city ?? '')
    const careerDirty =
      form.career_stage !== (user.career_stage ?? '') ||
      form.years_experience !== (user.years_experience ?? null)

    if (basicDirty && (!first || !last)) {
      setMsg({ type: 'err', text: 'First and last name are both required.' })
      return
    }
    if (careerDirty && !form.career_stage) {
      setMsg({ type: 'err', text: 'Pick a career stage.' })
      return
    }
    if (!basicDirty && !careerDirty) {
      setEditing(false)
      setMsg(null)
      return
    }

    setBusy(true)
    setMsg(null)
    try {
      if (basicDirty) {
        // phone isn't edited here, but the endpoint rewrites the whole row —
        // pass the current value through so it isn't nulled out.
        await updateBasicInfo({
          first_name: first,
          last_name: last,
          email: user.email,
          phone: user.phone,
          city: city || undefined,
        })
      }
      if (careerDirty) {
        await updateCareerStage({
          career_stage: form.career_stage,
          years_experience: form.years_experience ?? 0,
        })
      }
      setEditing(false)
      await reload()
      setMsg({ type: 'ok', text: 'Profile updated.' })
    } catch {
      setMsg({ type: 'err', text: 'Could not save. Try again.' })
    } finally {
      setBusy(false)
    }
  }

  const cancel = () => {
    setForm(toForm(user))
    setEditing(false)
    setMsg(null)
  }

  return (
    <div className="summary-section">
      <div className="mini-head">
        <div className="mini-title">Basics</div>
        {!editing && <button className="mini-add" onClick={() => { setMsg(null); setEditing(true) }}>Edit</button>}
      </div>

      {editing ? (
        <div className="entry-edit">
          <div className="entry-edit-grid basics-grid">
            <label className="field">
              <span className="field-label">First name</span>
              <input className="entry-input" value={form.first_name} placeholder="Ada"
                onChange={e => setForm({ ...form, first_name: e.target.value })} />
            </label>
            <label className="field">
              <span className="field-label">Last name</span>
              <input className="entry-input" value={form.last_name} placeholder="Lovelace"
                onChange={e => setForm({ ...form, last_name: e.target.value })} />
            </label>
            <label className="field">
              <span className="field-label">Location</span>
              <input className="entry-input" value={form.city} placeholder="Tel Aviv"
                onChange={e => setForm({ ...form, city: e.target.value })} />
            </label>
            <label className="field field-stage">
              <span className="field-label">Career stage</span>
              <select className="entry-input" value={form.career_stage}
                onChange={e => setForm({ ...form, career_stage: e.target.value })}>
                <option value="">Select…</option>
                {CAREER_STAGE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </label>
            <label className="field">
              <span className="field-label">Years of experience</span>
              {/* text + digit filter rather than type="number": no spinner
                  arrows, and no way to type "e"/"+"/"-" either */}
              <input className="entry-input" type="text" inputMode="numeric"
                value={form.years_experience ?? ''} placeholder="0" maxLength={2}
                onChange={e => {
                  const digits = e.target.value.replace(/\D/g, '')
                  setForm({
                    ...form,
                    years_experience: digits === '' ? null : Math.min(Number(digits), 60),
                  })
                }} />
            </label>
          </div>
          <div className="entry-edit-actions">
            <button className="btn-replace" onClick={cancel} disabled={busy}>Cancel</button>
            <button className="btn-modal-save" onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Save'}</button>
          </div>
        </div>
      ) : (
        <div className="summary-grid">
          <div>
            <div className="summary-label">Name</div>
            <div className="summary-value">{fullName}</div>
          </div>
          <div>
            <div className="summary-label">Location</div>
            <div className="summary-value">{user.city || 'Not set'}</div>
          </div>
          <div>
            <div className="summary-label">Career stage</div>
            <div className="summary-value">{humanizeCareerStage(user.career_stage)}</div>
          </div>
          <div>
            <div className="summary-label">Experience</div>
            <div className="summary-value">{user.years_experience != null ? `${user.years_experience} yrs` : 'Not set'}</div>
          </div>
        </div>
      )}

      {msg && (
        <div className={`upload-msg upload-msg-${msg.type}`}>
          {msg.type === 'ok' ? <CheckIcon /> : <WarnIcon />}{msg.text}
        </div>
      )}
    </div>
  )
}

// ── Editable Education / Experience ────────────────────────────────────────

const yearOf = (d?: string | null) => (d ? new Date(d).getFullYear() : '')

function EducationSection({ rows, reload }: { rows: EducationRow[]; reload: () => void }) {
  const [adding, setAdding] = useState(false)
  return (
    <div className="mini-section">
      <div className="mini-head">
        <div className="mini-title">Education</div>
        {!adding && <button className="mini-add" onClick={() => setAdding(true)}>+ Add</button>}
      </div>
      <div className="entry-list">
        {rows.map(r => <EducationEntry key={r.id} row={r} reload={reload} />)}
        {adding && (
          <EducationEntry
            row={{ id: 0, degree_type: '', field_of_study: '', school: '', graduation_year: new Date().getFullYear() }}
            startEditing
            onCancelNew={() => setAdding(false)}
            reload={() => { setAdding(false); reload() }}
          />
        )}
        {!rows.length && !adding && <span className="muted-empty">No education added yet.</span>}
      </div>
    </div>
  )
}

function EducationEntry({
  row, reload, startEditing, onCancelNew,
}: {
  row: EducationRow
  reload: () => void
  startEditing?: boolean
  onCancelNew?: () => void
}) {
  const toForm = (r: EducationRow): Education => ({
    degree_type: r.degree_type ?? '',
    field_of_study: r.field_of_study ?? '',
    school: r.school ?? '',
    graduation_year: r.graduation_year ?? new Date().getFullYear(),
    relevant_courses: r.relevant_courses ?? undefined,
    academic_highlights: r.academic_highlights ?? undefined,
  })
  const [editing, setEditing] = useState(!!startEditing)
  const [form, setForm] = useState<Education>(toForm(row))
  const [busy, setBusy] = useState(false)

  const valid = form.degree_type.trim() && form.field_of_study.trim() && form.school.trim() && !!form.graduation_year

  const save = async () => {
    if (!valid || busy) return
    setBusy(true)
    try {
      if (row.id === 0) await addEducation(form)
      else await updateEducation(row.id, form)
      setEditing(false)
      reload()
    } finally { setBusy(false) }
  }
  const remove = async () => {
    if (!window.confirm('Remove this education entry?')) return
    setBusy(true)
    try { await deleteEducation(row.id); reload() } finally { setBusy(false) }
  }
  const cancel = () => {
    if (row.id === 0) { onCancelNew?.(); return }
    setForm(toForm(row))
    setEditing(false)
  }

  if (!editing) {
    return (
      <div className="entry-row">
        <div className="experience-row">
          <strong>{row.degree_type || 'Degree'} · {row.field_of_study || 'Field'}</strong>
          <span>{row.school || 'School'}</span>
          {row.graduation_year ? <span>· {row.graduation_year}</span> : null}
        </div>
        <div className="entry-actions">
          <button className="btn-replace" onClick={() => setEditing(true)}>Edit</button>
          <button className="btn-delete-resume" onClick={remove} disabled={busy} aria-label="Delete education"><TrashIcon /></button>
        </div>
      </div>
    )
  }

  return (
    <div className="entry-edit">
      <div className="entry-edit-grid">
        <label className="field">
          <span className="field-label">Degree</span>
          <input className="entry-input" value={form.degree_type} placeholder="B.Sc."
            onChange={e => setForm({ ...form, degree_type: e.target.value })} />
        </label>
        <label className="field">
          <span className="field-label">Field of study</span>
          <input className="entry-input" value={form.field_of_study} placeholder="Computer Science"
            onChange={e => setForm({ ...form, field_of_study: e.target.value })} />
        </label>
        <label className="field">
          <span className="field-label">School</span>
          <input className="entry-input" value={form.school} placeholder="University name"
            onChange={e => setForm({ ...form, school: e.target.value })} />
        </label>
        <label className="field">
          <span className="field-label">Graduation year</span>
          <input className="entry-input" type="number" value={form.graduation_year || ''} placeholder="2026"
            onChange={e => setForm({ ...form, graduation_year: e.target.value ? Number(e.target.value) : 0 })} />
        </label>
      </div>
      <div className="entry-edit-actions">
        <button className="btn-replace" onClick={cancel} disabled={busy}>Cancel</button>
        <button className="btn-modal-save" onClick={save} disabled={busy || !valid}>{busy ? 'Saving…' : 'Save'}</button>
      </div>
    </div>
  )
}

function ExperienceSection({ rows, reload }: { rows: WorkExperienceRow[]; reload: () => void }) {
  const [adding, setAdding] = useState(false)
  return (
    <div className="mini-section">
      <div className="mini-head">
        <div className="mini-title">Experience</div>
        {!adding && <button className="mini-add" onClick={() => setAdding(true)}>+ Add</button>}
      </div>
      <div className="entry-list">
        {rows.map(r => <ExperienceEntry key={r.id} row={r} reload={reload} />)}
        {adding && (
          <ExperienceEntry
            row={{ id: 0, position: '', company: '', start_date: '', end_date: null }}
            startEditing
            onCancelNew={() => setAdding(false)}
            reload={() => { setAdding(false); reload() }}
          />
        )}
        {!rows.length && !adding && <span className="muted-empty">No work experience added yet.</span>}
      </div>
    </div>
  )
}

function ExperienceEntry({
  row, reload, startEditing, onCancelNew,
}: {
  row: WorkExperienceRow
  reload: () => void
  startEditing?: boolean
  onCancelNew?: () => void
}) {
  const toForm = (r: WorkExperienceRow): WorkExperience => ({
    position: r.position ?? '',
    company: r.company ?? '',
    start_date: r.start_date ?? '',
    end_date: r.end_date ?? '',
    description: r.description ?? null,
  })
  const [editing, setEditing] = useState(!!startEditing)
  const [form, setForm] = useState<WorkExperience>(toForm(row))
  const [busy, setBusy] = useState(false)

  const valid = form.position.trim() && form.company.trim() && !!form.start_date

  const save = async () => {
    if (!valid || busy) return
    setBusy(true)
    const payload: WorkExperience = { ...form, end_date: form.end_date || null }
    try {
      if (row.id === 0) await addWorkExperience(payload)
      else await updateWorkExperience(row.id, payload)
      setEditing(false)
      reload()
    } finally { setBusy(false) }
  }
  const remove = async () => {
    if (!window.confirm('Remove this experience entry?')) return
    setBusy(true)
    try { await deleteWorkExperience(row.id); reload() } finally { setBusy(false) }
  }
  const cancel = () => {
    if (row.id === 0) { onCancelNew?.(); return }
    setForm(toForm(row))
    setEditing(false)
  }

  if (!editing) {
    return (
      <div className="entry-row">
        <div className="experience-row">
          <strong>{row.position || 'Role'}</strong>
          <span>{row.company || 'Company'}</span>
          <span>{yearOf(row.start_date)}{row.end_date ? ` - ${yearOf(row.end_date)}` : ' - Present'}</span>
        </div>
        <div className="entry-actions">
          <button className="btn-replace" onClick={() => setEditing(true)}>Edit</button>
          <button className="btn-delete-resume" onClick={remove} disabled={busy} aria-label="Delete experience"><TrashIcon /></button>
        </div>
      </div>
    )
  }

  return (
    <div className="entry-edit">
      <div className="entry-edit-grid">
        <label className="field">
          <span className="field-label">Title</span>
          <input className="entry-input" value={form.position} placeholder="Software Engineer"
            onChange={e => setForm({ ...form, position: e.target.value })} />
        </label>
        <label className="field">
          <span className="field-label">Company</span>
          <input className="entry-input" value={form.company} placeholder="Company name"
            onChange={e => setForm({ ...form, company: e.target.value })} />
        </label>
        <label className="field">
          <span className="field-label">Start date</span>
          <input className="entry-input" type="date" value={form.start_date}
            onChange={e => setForm({ ...form, start_date: e.target.value })} />
        </label>
        <label className="field">
          <span className="field-label">End date <span className="field-hint">— leave blank if current</span></span>
          <input className="entry-input" type="date" value={form.end_date ?? ''}
            onChange={e => setForm({ ...form, end_date: e.target.value })} />
        </label>
      </div>
      <div className="entry-edit-actions">
        <button className="btn-replace" onClick={cancel} disabled={busy}>Cancel</button>
        <button className="btn-modal-save" onClick={save} disabled={busy || !valid}>{busy ? 'Saving…' : 'Save'}</button>
      </div>
    </div>
  )
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