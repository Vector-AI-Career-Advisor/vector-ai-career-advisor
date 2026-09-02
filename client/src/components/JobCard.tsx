import { Job } from '../api/jobs'
import './JobCard.css'

interface Props {
  job: Job
  onClick: () => void
}

const seniorityColor: Record<string, string> = {
  junior:     'tag-green',
  mid:        'tag-blue',
  senior:     'tag-purple',
  lead:       'tag-orange',
  staff:      'tag-orange',
  principal:  'tag-red',
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
  const senClass = seniorityColor[job.seniority?.toLowerCase() ?? ''] ?? 'tag-default'
  const initials = (job.company ?? '?').slice(0, 2).toUpperCase()

  return (
    <article className="job-card" onClick={onClick} tabIndex={0}
      onKeyDown={e => e.key === 'Enter' && onClick()}>
      {/* Company avatar */}
      <div className="job-avatar" aria-hidden="true">{initials}</div>

      <div className="job-body">
        <div className="job-meta-top">
          <span className="job-company">{job.company ?? 'Unknown'}</span>
          <span className="job-posted">
            {timeAgo(isValidDate(job.posted_at) ? job.posted_at : job.scraped_at)}
          </span>
        </div>

        <h3 className="job-title">{job.title ?? 'Untitled Role'}</h3>

        <div className="job-tags">
          {job.seniority && (
            <span className={`tag ${senClass}`}>{job.seniority}</span>
          )}
          {job.location && (
            <span className="tag tag-location">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <path d="M12 2a7 7 0 0 1 7 7c0 5-7 13-7 13S5 14 5 9a7 7 0 0 1 7-7z"/>
                <circle cx="12" cy="9" r="2.5"/>
              </svg>
              {job.location}
            </span>
          )}
          {job.yearsexperience != null && (
            <span className="tag tag-default">{job.yearsexperience}yr exp</span>
          )}
        </div>

        {/* Skills preview */}
        {job.skills_must && job.skills_must.length > 0 && (
          <div className="job-skills">
            {job.skills_must.slice(0, 4).map(s => (
              <span key={s} className="skill-chip">{s}</span>
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
