// Shared option vocabularies for job filters and the user profile.

export const SENIORITIES = ['Junior', 'Mid', 'Senior', 'Lead', 'Staff', 'Principal']

// Career-stage codes are stored raw (e.g. "recent_graduate"); map them to
// display labels for the profile UI.
export const CAREER_STAGE_LABELS: Record<string, string> = {
  student: 'Student',
  recent_graduate: 'Recent graduate',
  working_professional: 'Working professional',
  career_switcher: 'Career switcher',
  between_jobs: 'Between jobs',
  returning: 'Returning after a break',
}

// Picker options for the profile summary editor — derived from the labels
// above so the two never drift apart.
export const CAREER_STAGE_OPTIONS: { value: string; label: string }[] =
  Object.entries(CAREER_STAGE_LABELS).map(([value, label]) => ({ value, label }))

export function humanizeCareerStage(value?: string | null): string {
  if (!value) return 'Not set'
  return (
    CAREER_STAGE_LABELS[value] ??
    value.replace(/[_-]+/g, ' ').replace(/^\w/, c => c.toUpperCase())
  )
}

export const ROLE_OPTIONS = [
  'Frontend',
  'Backend',
  'Fullstack',
  'AI / ML',
  'Data Scientist',
  'Data Engineer',
  'Data Analyst',
  'DevOps / Cloud',
  'Mobile',
  'QA / Automation',
  'Security',
  'Embedded / Firmware',
  'Solutions Architect',
  'Team Lead',
  'Software Development',
  'Product Manager',
  'Other',
]

// Normalised regions produced by server/etl/locations.py — the job filter and
// profile "preferred locations" both match jobs.region against these.
export const LOCATION_OPTIONS = [
  'Tel Aviv',
  'Center',
  'Sharon',
  'Haifa',
  'North',
  'South',
  'Jerusalem',
  'Remote',
]

export const EDUCATION_LEVELS: { value: string; label: string }[] = [
  { value: '', label: 'No preference' },
  { value: 'none', label: 'No degree required' },
  { value: 'bootcamp', label: 'Bootcamp' },
  { value: 'associate', label: "Associate's" },
  { value: 'bachelor', label: "Bachelor's" },
  { value: 'master', label: "Master's" },
  { value: 'phd', label: 'PhD' },
]

// Years-of-experience picker for the "core" restriction card.
export const EXPERIENCE_OPTIONS: { value: number | ''; label: string }[] = [
  { value: '', label: '—' },
  { value: 0, label: '0' },
  { value: 1, label: '1' },
  { value: 2, label: '2' },
  { value: 3, label: '3' },
  { value: 4, label: '4' },
  { value: 5, label: '5' },
  { value: 7, label: '7' },
  { value: 10, label: '10' },
  { value: 15, label: '15' },
]
