import { useState, useRef, useEffect } from 'react'
import { Job, fetchJob } from '../api/jobs'
import {
  generateCoverLetter,
  generateTailoredResume,
  listResumes,
  setActiveResume,
  ResumeListItem,
} from '../api/resumes'
import { getLoginRecommendation } from '../api/agents'
import './AgentChat.css'

// ─── Simple markdown renderer (no external dependency) ───────────────────────
function SimpleMarkdown({ children }: { children: string }) {
  const html = children
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>')
    .replace(/^[-*]\s+(.+)$/gm, '<li>$1</li>')
    .replace(/(<li>[\s\S]+?<\/li>)/g, '<ul>$1</ul>')
    .replace(/\n/g, '<br/>')
  return <span dangerouslySetInnerHTML={{ __html: html }} />
}

// ─── Types ──────────────────────────────────────────────────────────────────

type Role = 'user' | 'agent' | 'system'

interface AgentStep {
  name: string
  description: string
}

interface Message {
  id: string
  role: Role
  text: string
  timestamp: Date
  agentsUsed?: AgentStep[]
  jobIds?: string[]
}

const AGENT_LABELS: Record<string, string> = {
  db_agent:          'Job Search Agent',
  resume_agent:      'Resume Agent',
  job_advisor_agent: 'Career Advisor Agent',
  interview_agent:   'Interview Prep Agent',
}
const agentLabel = (name: string) => AGENT_LABELS[name] ?? name
const formatDesc = (s: string) => {
  if (!s) return ''
  const words = s.trim().split(/\s+/)
  const truncated = words.slice(0, 6).join(' ')
  return truncated.charAt(0).toUpperCase() + truncated.slice(1) + (words.length > 6 ? '…' : '…')
}

interface Props {
  selectedJob: Job | null
  jobs?: Job[]
  onSelectJob?: (job: Job) => void
}

async function callAgent(
  message: string,
  selectedJob: Job | null,
  history: Message[],
  onPlanning: (agents: AgentStep[]) => void,
): Promise<{ reply: string; agentsUsed: AgentStep[]; jobIds: string[] }> {
  const token = localStorage.getItem('token')
  const res = await fetch('/agents/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      message,
      job_id: selectedJob?.id ?? null,
      history: history
        .filter(m => m.role === 'user' || m.role === 'agent')
        .map(m => ({ role: m.role === 'agent' ? 'agents' : 'user', text: m.text })),
    }),
  })

  if (!res.ok) {
    if (res.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    throw new Error(`HTTP ${res.status}`)
  }

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let reply = ''
  let agentsUsed: AgentStep[] = []
  let jobIds: string[] = []

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const raw = line.slice(6).trim()
      if (!raw) continue
      try {
        const event = JSON.parse(raw)
        if (event.type === 'planning') {
          onPlanning(event.agents)
        } else if (event.type === 'reply') {
          reply = event.reply
          agentsUsed = event.agents_used ?? []
          jobIds = event.job_ids ?? []
        } else if (event.type === 'error') {
          throw new Error(event.detail ?? 'Agent error')
        }
      } catch (e) {
        if (e instanceof SyntaxError) continue
        throw e
      }
    }
  }

  return { reply, agentsUsed, jobIds }
}

// ─── Job mini-card ────────────────────────────────────────────────────────────

function JobMiniCard({ jobId, onOpen }: { jobId: string; onOpen?: (job: Job) => void }) {
  const [job, setJob] = useState<Job | null>(null)

  useEffect(() => {
    fetchJob(jobId).then(setJob).catch(() => {})
  }, [jobId])

  if (!job) return (
    <div className="job-mini-card job-mini-card--loading">
      <div className="job-mini-card-shimmer" />
    </div>
  )

  return (
    <div className="job-mini-card">
      <div className="job-mini-card-info">
        <p className="job-mini-card-title">{job.title}</p>
        <p className="job-mini-card-meta">
          {[job.company, job.location].filter(Boolean).join(' · ')}
        </p>
      </div>
      {onOpen && (
        <button className="job-mini-card-btn" onClick={() => onOpen(job)}>
          Open
        </button>
      )}
    </div>
  )
}

// ─── Suggested prompts ───────────────────────────────────────────────────────

const SUGGESTIONS = [
  'What skills do I need for this role?',
  'How should I tailor my CV?',
  'What salary should I expect?',
  'Find me similar jobs',
]

// ─── Component ───────────────────────────────────────────────────────────────

export default function AgentChat({ selectedJob, jobs = [], onSelectJob }: Props) {
  const [messages, setMessages]         = useState<Message[]>([])
  const [input, setInput]               = useState('')
  const [isTyping, setIsTyping]         = useState(false)
  const [hasUserInteracted, setHasUserInteracted] = useState(false)
  const [pendingAgents, setPendingAgents] = useState<AgentStep[]>([])
  const [error, setError]               = useState<string | null>(null)
  const [coverLetter, setCoverLetter] = useState<{ text: string; title: string; company: string } | null>(null)
  const [coverLetterState, setCoverLetterState] = useState<'idle' | 'generating' | 'error'>('idle')
  const [coverLetterError, setCoverLetterError] = useState<string | null>(null)
  const [resumeFit, setResumeFit] = useState<{ text: string; title: string; company: string } | null>(null)
  const [resumeFitState, setResumeFitState] = useState<'idle' | 'generating' | 'error'>('idle')
  const [resumeFitError, setResumeFitError] = useState<string | null>(null)
  const [resumes, setResumes] = useState<ResumeListItem[]>([])
  const [activeResumeId, setActiveResumeId] = useState<number | null>(null)
  const [resumeMenuOpen, setResumeMenuOpen] = useState(false)
  const [switchingResume, setSwitchingResume] = useState(false)

  const bottomRef  = useRef<HTMLDivElement>(null)
  const inputRef   = useRef<HTMLTextAreaElement>(null)
  const resumeMenuRef = useRef<HTMLDivElement>(null)

  // Fire a one-shot job recommendation right after a fresh login
  useEffect(() => {
    if (!sessionStorage.getItem('vector_just_logged_in')) return
    sessionStorage.removeItem('vector_just_logged_in')

    setIsTyping(true)
    getLoginRecommendation()
      .then(({ reply, job_ids }) => {
        setMessages(prev => [
          ...prev,
          { id: crypto.randomUUID(), role: 'agent', text: reply, timestamp: new Date(), jobIds: job_ids },
        ])
      })
      .catch(() => {})
      .finally(() => setIsTyping(false))
  }, [])

  // Scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  // Load the user's resumes so the active one can be shown / switched
  useEffect(() => {
    listResumes()
      .then(rows => {
        setResumes(rows)
        setActiveResumeId(rows.find(r => r.is_active)?.id ?? null)
      })
      .catch(() => {})
  }, [])

  // Close the resume dropdown on an outside click
  useEffect(() => {
    if (!resumeMenuOpen) return
    const onDocClick = (e: MouseEvent) => {
      if (resumeMenuRef.current && !resumeMenuRef.current.contains(e.target as Node)) {
        setResumeMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [resumeMenuOpen])

  const handleSelectActiveResume = async (id: number) => {
    setResumeMenuOpen(false)
    if (id === activeResumeId || switchingResume) return
    const previous = activeResumeId
    setActiveResumeId(id)
    setSwitchingResume(true)
    try {
      await setActiveResume(id)
      setResumes(rs => rs.map(r => ({ ...r, is_active: r.id === id })))
    } catch {
      setActiveResumeId(previous)
    } finally {
      setSwitchingResume(false)
    }
  }


  const send = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || isTyping) return

    setHasUserInteracted(true)

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      text: trimmed,
      timestamp: new Date(),
    }

    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsTyping(true)
    setPendingAgents([])
    setError(null)

    try {
      const { reply, agentsUsed, jobIds } = await callAgent(
        trimmed,
        selectedJob,
        messages,
        (agents) => setPendingAgents(agents),
      )
      setPendingAgents([])
      setMessages(prev => [
        ...prev,
        { id: crypto.randomUUID(), role: 'agent', text: reply, timestamp: new Date(), agentsUsed, jobIds },
      ])
    } catch {
      setPendingAgents([])
      setError('Failed to reach the agents. Please try again.')
    } finally {
      setIsTyping(false)
      inputRef.current?.focus()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  const handleGenerateCoverLetter = async () => {
    if (!selectedJob || coverLetterState === 'generating') return
    setCoverLetterState('generating')
    setCoverLetterError(null)
    try {
      const result = await generateCoverLetter(selectedJob.id)
      setCoverLetter({ text: result.cover_letter, title: result.job_title, company: result.company })
      setCoverLetterState('idle')
    } catch (error: any) {
      setCoverLetterState('error')
      setCoverLetterError(error.response?.data?.detail ?? 'Could not generate a cover letter. Upload a resume and try again.')
      setTimeout(() => setCoverLetterState('idle'), 3000)
    }
  }

  const downloadCoverLetter = () => {
    if (!coverLetter) return
    const blob = new Blob([coverLetter.text], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `cover-letter-${(coverLetter.company || 'job').replace(/[^a-z0-9]+/gi, '-').toLowerCase()}.txt`
    link.click()
    URL.revokeObjectURL(url)
  }

  const handleGenerateResumeFit = async () => {
    if (!selectedJob || resumeFitState === 'generating') return
    setResumeFitState('generating')
    setResumeFitError(null)
    try {
      const result = await generateTailoredResume(selectedJob.id)
      setResumeFit({ text: result.tailored_resume, title: result.job_title, company: result.company })
      setResumeFitState('idle')
    } catch (error: any) {
      setResumeFitState('error')
      setResumeFitError(error.response?.data?.detail ?? 'Could not tailor your resume. Upload a resume and try again.')
      setTimeout(() => setResumeFitState('idle'), 3000)
    }
  }

  const downloadResumeFit = () => {
    if (!resumeFit) return
    const blob = new Blob([resumeFit.text], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `resume-fit-${(resumeFit.company || 'job').replace(/[^a-z0-9]+/gi, '-').toLowerCase()}.txt`
    link.click()
    URL.revokeObjectURL(url)
  }

  const showBackdrop = !hasUserInteracted
  const showMessages = messages.length > 0 || isTyping
  const lastAgentId = [...messages].reverse().find(m => m.role === 'agent')?.id

  const activeResume = resumes.find(r => r.id === activeResumeId)
  const activeResumeName = activeResume ? (activeResume.title || activeResume.filename) : 'None'

  return (
    <div className="agent-chat">
      {/* Header */}
      <div className="agent-header">
        <div>
          <p className="agent-name">Career Agent</p>
          <p className="agent-status">
            <span className={`status-dot ${error ? 'offline' : 'online'}`} />
            {isTyping ? 'Typing…' : error ? 'Offline' : 'Online'}
          </p>
        </div>

        <div className="agent-header-pills">
          {selectedJob && (
            <div className="agent-context-pill">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <rect x="2" y="7" width="20" height="14" rx="2"/>
                <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/>
              </svg>
              {selectedJob.title}
            </div>
          )}
        </div>
      </div>

      {selectedJob && (
        <div className="agent-action-bar">
          {resumes.length > 0 && (
            <div className="resume-picker" ref={resumeMenuRef}>
              <button
                className="resume-picker-btn"
                onClick={() => setResumeMenuOpen(o => !o)}
                disabled={switchingResume}
                aria-haspopup="listbox"
                aria-expanded={resumeMenuOpen}
                title="Change which resume the web app and agents use"
              >
                <span className="resume-picker-label">
                  Current active resume: <strong>{activeResumeName}</strong>
                </span>
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>
              {resumeMenuOpen && (
                <ul className="resume-picker-menu" role="listbox">
                  {resumes.map(r => (
                    <li key={r.id}>
                      <button
                        className={`resume-picker-item ${r.id === activeResumeId ? 'is-active' : ''}`}
                        onClick={() => handleSelectActiveResume(r.id)}
                        role="option"
                        aria-selected={r.id === activeResumeId}
                      >
                        <span className="resume-picker-item-name">{r.title || r.filename}</span>
                        {r.id === activeResumeId && <span className="resume-picker-check">✓</span>}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          <button
            className="agent-fit-resume-btn"
            onClick={handleGenerateResumeFit}
            disabled={resumeFitState === 'generating'}
            title="Tailor your resume to the selected job"
          >
            {resumeFitState === 'generating' ? 'Fitting…' : 'Fit resume'}
          </button>
          <button
            className="agent-cover-letter-btn"
            onClick={handleGenerateCoverLetter}
            disabled={coverLetterState === 'generating'}
            title="Generate a cover letter for the selected job"
          >
            {coverLetterState === 'generating' ? 'Drafting…' : 'Draft cover letter'}
          </button>
        </div>
      )}

      {/* Message area */}
      <div className="agent-messages">
        {showBackdrop && (
          <div className="agent-empty">
            <div className="agent-empty-icon">
              <svg width="52" height="52" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2v3"/>
                <circle cx="12" cy="2" r="1" fill="currentColor" stroke="none"/>
                <rect x="2" y="5" width="20" height="14" rx="6"/>
                <circle cx="9" cy="11" r="1.8" fill="currentColor" stroke="none"/>
                <circle cx="15" cy="11" r="1.8" fill="currentColor" stroke="none"/>
                <path d="M9 15 Q12 17.5 15 15"/>
                <path d="M2 10H0"/><path d="M22 10h2"/>
              </svg>
            </div>
            <p className="agent-empty-title">Your career agent</p>
            <p className="agent-empty-sub">
              Ask about any job, get CV tips, salary ranges, or let the agent
              find the best match for your profile.
            </p>
            <div className="agent-suggestions">
              {SUGGESTIONS.map(s => (
                <button key={s} className="suggestion-chip" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {showMessages && (
          <>
            {messages.map(msg => (
              <div key={msg.id} className={`message-row ${msg.role}`}>
                {msg.role === 'system' ? (
                  <div className="system-message">{msg.text}</div>
                ) : msg.role === 'agent' ? (
                  <div className="message-content">
                    <div className="bubble agent">
                      <div className="msg-text">
                        <SimpleMarkdown>{msg.text}</SimpleMarkdown>
                      </div>
                      {msg.jobIds && msg.jobIds.length > 0 && (
                        <div className="job-mini-cards">
                          {msg.jobIds.map(id => (
                            <JobMiniCard key={id} jobId={id} onOpen={onSelectJob} />
                          ))}
                        </div>
                      )}
                      <span className="msg-time">
                        {msg.timestamp.toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </div>
                    {msg.id === lastAgentId && !isTyping && (
                      <div className="agent-bubble-avatar">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                          stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M12 2v3"/>
                          <circle cx="12" cy="2" r="1" fill="currentColor" stroke="none"/>
                          <rect x="2" y="5" width="20" height="14" rx="6"/>
                          <circle cx="9" cy="11" r="1.8" fill="currentColor" stroke="none"/>
                          <circle cx="15" cy="11" r="1.8" fill="currentColor" stroke="none"/>
                          <path d="M9 15 Q12 17.5 15 15"/>
                          <path d="M2 10H0"/><path d="M22 10h2"/>
                        </svg>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="bubble user">
                      <div className="msg-text">
                      <SimpleMarkdown>{msg.text}</SimpleMarkdown>
                    </div>
                    <span className="msg-time"></span>
                   
                    <span className="msg-time">
                      {msg.timestamp.toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                  </div>
                )}
              </div>
            ))}

            {isTyping && (
              <div className="message-row agent">
                <div className="message-content">
                  {pendingAgents.length > 0 && (
                    <div className="agent-chain">
                      {pendingAgents.map((a, i) => (
                        <div key={a.name} className="agent-chain-row">
                          <div className="agent-chain-track">
                            <div className="agent-chain-dot pending" />
                            {i < pendingAgents.length - 1 && <div className="agent-chain-line pending" />}
                          </div>
                          <div className="agent-chain-info">
                            <span className="agent-chain-label pending">{agentLabel(a.name)}</span>
                            {a.description && <span className="agent-chain-desc pending">{formatDesc(a.description)}</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="bubble agent typing-indicator">
                    <span /><span /><span />
                  </div>
                </div>
              </div>
            )}

            {error && <div className="agent-error">{error}</div>}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      {coverLetter && (
        <div className="cover-letter-overlay" onClick={() => setCoverLetter(null)}>
          <div
            className="cover-letter-editor"
            role="dialog"
            aria-modal="true"
            aria-label="Cover letter editor"
            onClick={e => e.stopPropagation()}
          >
            <div className="cover-letter-editor-header">
              <div>
                <p className="cover-letter-editor-title">Cover letter</p>
                <p className="cover-letter-editor-meta">{coverLetter.title}{coverLetter.company ? ` · ${coverLetter.company}` : ''}</p>
              </div>
              <button className="cover-letter-close" onClick={() => setCoverLetter(null)} aria-label="Close editor">×</button>
            </div>
            <textarea
              className="cover-letter-textarea"
              value={coverLetter.text}
              onChange={e => setCoverLetter({ ...coverLetter, text: e.target.value })}
              aria-label="Cover letter text"
            />
            <button className="cover-letter-download" onClick={downloadCoverLetter}>Download edited letter</button>
          </div>
        </div>
      )}
      {resumeFit && (
        <div className="cover-letter-overlay" onClick={() => setResumeFit(null)}>
          <div
            className="cover-letter-editor resume-fit-editor"
            role="dialog"
            aria-modal="true"
            aria-label="Resume fit editor"
            onClick={e => e.stopPropagation()}
          >
            <div className="cover-letter-editor-header">
              <div>
                <p className="cover-letter-editor-title">Tailored resume</p>
                <p className="cover-letter-editor-meta">{resumeFit.title}{resumeFit.company ? ` · ${resumeFit.company}` : ''}</p>
              </div>
              <button className="cover-letter-close" onClick={() => setResumeFit(null)} aria-label="Close editor">×</button>
            </div>
            <textarea
              className="cover-letter-textarea"
              value={resumeFit.text}
              onChange={e => setResumeFit({ ...resumeFit, text: e.target.value })}
              aria-label="Tailored resume text"
            />
            <button className="cover-letter-download" onClick={downloadResumeFit}>Download edited resume</button>
          </div>
        </div>
      )}
      {coverLetterState === 'error' && <div className="agent-error cover-letter-error">{coverLetterError}</div>}
      {resumeFitState === 'error' && <div className="agent-error cover-letter-error">{resumeFitError}</div>}

      {/* Input bar */}
      <div className="agent-input-bar">
        <textarea
          ref={inputRef}
          className="agent-input"
          placeholder="Ask about jobs, your CV, salary…"
          rows={1}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isTyping}
        />
        <button
          className="agent-icon-btn agent-send"
          onClick={() => send(input)}
          disabled={!input.trim() || isTyping}
          aria-label="Send"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <path d="M22 2L11 13M22 2L15 22l-4-9-9-4 20-7z"/>
          </svg>
        </button>
      </div>

    </div>
  )
}