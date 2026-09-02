import { useState, useEffect } from 'react'
import { Job } from '../api/jobs'
import { createApplication } from '../api/applications'
import { formatSkill } from '../lib/skills'
import './JobDrawer.css'

interface Props {
  job: Job | null
  onClose: () => void
  chatWidth?: number
}

export default function JobDrawer({ job, onClose, chatWidth = 0 }: Props) {
  const [showConfirm, setShowConfirm] = useState(false)
  const [applying, setApplying] = useState(false)
  const [applied, setApplied] = useState(false)
  const [logoBroken, setLogoBroken] = useState(false)

  // Reset dialog state whenever a different job is opened
  useEffect(() => {
    setShowConfirm(false)
    setApplying(false)
    setApplied(false)
    setLogoBroken(false)
  }, [job?.id])

  if (!job) return null

  const place = [job.location, job.region]
    .filter((v, i, a) => v && a.indexOf(v) === i)
    .join(', ')

  const availableWidth = window.innerWidth - chatWidth
  const drawerWidth = Math.min(680, Math.max(420, availableWidth - 60))
  const drawerLeft = Math.max(12, (availableWidth - drawerWidth) / 2)

  function handleApplyClick() {
    if (job?.url) window.open(job.url, '_blank', 'noopener,noreferrer')
    setShowConfirm(true)
  }

  async function handleConfirmYes() {
    setApplying(true)
    try {
      await createApplication(job!.id)
    } catch (err: any) {
      // 409 means already tracked — still treat as success
      if (err?.response?.status !== 409) {
        console.error('Failed to save application:', err)
      }
    } finally {
      setApplying(false)
      setApplied(true)
      setShowConfirm(false)
    }
  }

  return (
    <>
      <div className="drawer-overlay" style={{ right: chatWidth }} onClick={onClose} />
      <aside className="drawer" style={{ left: drawerLeft, width: drawerWidth }}>
        <div className="drawer-header">
          <button className="drawer-close" onClick={onClose} aria-label="Close">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <path d="M18 6L6 18M6 6l12 12"/>
            </svg>
          </button>

          <div className="drawer-company-row">
            {job.logo_url && !logoBroken ? (
              <img className="drawer-logo" src={job.logo_url} alt=""
                onError={() => setLogoBroken(true)} />
            ) : (
              <div className="drawer-avatar">
                {(job.company ?? '?').slice(0, 2).toUpperCase()}
              </div>
            )}
            <div>
              <p className="drawer-company">{job.company}</p>
              <p className="drawer-source">{job.source ?? 'linkedin'}</p>
            </div>
          </div>

          <h2 className="drawer-title">{job.title}</h2>

          <div className="drawer-meta">
            {place && <span className="dmeta"><LocationIcon />{place}</span>}
            {job.seniority && <span className="dmeta"><LevelIcon />{job.seniority}</span>}
            {job.yearsexperience != null && (
              <span className="dmeta"><ExpIcon />{job.yearsexperience}yr exp</span>
            )}
          </div>

          {job.url && (
            applied ? (
              <span className="btn-applied"><CheckIcon />Applied</span>
            ) : (
              <button className="btn-apply" onClick={handleApplyClick}>
                Apply Now ↗
              </button>
            )
          )}
        </div>

        <div className="drawer-body">
          {job.skills_must && job.skills_must.length > 0 && (
            <Section title="Must-Have Skills">
              <div className="skill-list">
                {job.skills_must.map(s => (
                  <span key={s} className="skill-chip-drawer must">{formatSkill(s)}</span>
                ))}
              </div>
            </Section>
          )}

          {job.skills_nice && job.skills_nice.length > 0 && (
            <Section title="Nice to Have">
              <div className="skill-list">
                {job.skills_nice.map(s => (
                  <span key={s} className="skill-chip-drawer nice">{formatSkill(s)}</span>
                ))}
              </div>
            </Section>
          )}

          {job.description && (
            <Section title="Job Description">
              <p className="drawer-desc">{job.description}</p>
            </Section>
          )}

          <Section title="Relevant Education">
            {job.education && job.education.length > 0 ? (
              <ul className="exp-list">
                {job.education.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            ) : (
              <p className="drawer-empty">No specific degree requirements in this posting.</p>
            )}
          </Section>

          {job.past_experience && job.past_experience.length > 0 && (
            <Section title="Relevant Experience">
              <ul className="exp-list">
                {job.past_experience.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            </Section>
          )}
        </div>

        {showConfirm && (
          <div className="confirm-backdrop">
            <div className="confirm-dialog">
              <p className="confirm-title">Did you apply?</p>
              <p className="confirm-sub">We'll track it in your applications.</p>
              <div className="confirm-actions">
                <button
                  className="confirm-yes"
                  onClick={handleConfirmYes}
                  disabled={applying}
                >
                  {applying ? 'Saving…' : 'Yes'}
                </button>
                <button
                  className="confirm-no"
                  onClick={() => setShowConfirm(false)}
                  disabled={applying}
                >
                  No
                </button>
              </div>
            </div>
          </div>
        )}
      </aside>
    </>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="drawer-section">
      <h4 className="drawer-section-title">{title}</h4>
      {children}
    </div>
  )
}

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12"/>
    </svg>
  )
}

function LocationIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
      <path d="M12 2a7 7 0 0 1 7 7c0 5-7 13-7 13S5 14 5 9a7 7 0 0 1 7-7z"/>
      <circle cx="12" cy="9" r="2.5"/>
    </svg>
  )
}

function LevelIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
      <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
    </svg>
  )
}

function ExpIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
      <rect x="2" y="7" width="20" height="14" rx="2"/>
      <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/>
    </svg>
  )
}
