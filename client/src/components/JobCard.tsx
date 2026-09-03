import { useState } from 'react'
import { Job } from '../api/jobs'
import { formatSkill } from '../lib/skills'
import './JobCard.css'

interface Props {
  job: Job
  onClick: () => void
}

function isValidDate(dateStr?: string): boolean {
  return !!dateStr && !Number.isNaN(new Date(dateStr).getTime())
}

function timeAgo(dateStr?: string): string {
  if (!isValidDate(dateStr)) return ''
  const days = Math.floor((Date.now() - new Date(dateStr as string).getTime()) / 86400000)
  if (days <= 0) return 'Today'
  if (days === 1) return 'Yesterday'
  if (days < 7) return `${days}d ago`
  if (days < 30) return `${Math.floor(days / 7)}w ago`
  return `${Math.floor(days / 30)}mo ago`
}

export default function JobCard({ job, onClick }: Props) {
  const initials = (job.company ?? '?').slice(0, 2).toUpperCase()
  const [logoBroken, setLogoBroken] = useState(false)
  const posted = timeAgo(isValidDate(job.posted_at) ? job.posted_at : job.scraped_at)
  // "Ramat Gan, Center" — city then region, de-duped when they're the same
  const place = [job.location, job.region]
    .filter((v, i, a) => v && a.indexOf(v) === i)
    .join(', ')

  return (
    <article className="job-card" onClick={onClick} tabIndex={0}
      onKeyDown={e => e.key === 'Enter' && onClick()}>
      {/* Company logo, falling back to initials */}
      {job.logo_url && !logoBroken ? (
        <img className="job-logo" src={job.logo_url} alt="" aria-hidden="true"
          onError={() => setLogoBroken(true)} />
      ) : (
        <div className="job-avatar" aria-hidden="true">{initials}</div>
      )}

      <div className="job-body">
        <div className="job-meta-top">
          <span className="job-company">{job.company ?? 'Unknown'}</span>
        </div>

        <h3 className="job-title">{job.title ?? 'Untitled Role'}</h3>

        <div className="job-meta-line">
          {posted && (
            <span className="job-meta-item job-posted">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <circle cx="12" cy="12" r="9"/>
                <path d="M12 7v5l3 2"/>
              </svg>
              {posted}
            </span>
          )}
          {job.yearsexperience != null && (
            <span className="job-meta-item">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <rect x="2" y="7" width="20" height="14" rx="2"/>
                <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
              </svg>
              {job.yearsexperience}yr exp
            </span>
          )}
          {place && (
            <span className="job-meta-item">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <path d="M12 2a7 7 0 0 1 7 7c0 5-7 13-7 13S5 14 5 9a7 7 0 0 1 7-7z"/>
                <circle cx="12" cy="9" r="2.5"/>
              </svg>
              {place}
            </span>
          )}
        </div>

        {/* Skills preview */}
        {job.skills_must && job.skills_must.length > 0 && (
          <div className="job-skills">
            {job.skills_must.slice(0, 4).map(s => (
              <span key={s} className="skill-chip">{formatSkill(s)}</span>
            ))}
            {job.skills_must.length > 4 && (
              <span className="skill-more">+{job.skills_must.length - 4}</span>
            )}
          </div>
        )}
      </div>

      <div className="job-arrow" aria-hidden="true">→</div>
    </article>
  )
}
