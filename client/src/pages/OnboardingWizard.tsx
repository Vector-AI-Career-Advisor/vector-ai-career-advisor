import React, { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadResume } from '../api/resumes'
import {
  updateBasicInfo,
  updateCareerStage,
  addEducation,
  addSkill,
  addSoftSkill,
  addLanguage,
  updatePreferences,
} from '../api/profile'
import './OnboardingWizard.css'

const getStoredUserEmail = () => localStorage.getItem('user_email') ?? ''

type Step = 'welcome' | 'basic-info' | 'career-stage' | 'education' | 'skills' | 'soft-skills' | 'work-experience' | 'extra' | 'preferences' | 'completion'

interface FormData {
  basicInfo: {
    first_name: string
    last_name: string
    phone: string
    city: string
  }
  careerStage: {
    stage: string
    years_experience: number
  }
  education: {
    degree_type: string
    field_of_study: string
    school: string
    graduation_year: number
    relevant_courses: string
    academic_highlights: string
  }
  skills: string[]
  softSkills: string[]
  workPreferences: Record<string, boolean>
}

export default function OnboardingWizard() {
  const navigate = useNavigate()
  const [currentStep, setCurrentStep] = useState<Step>('welcome')
  const [formData, setFormData] = useState<FormData>({
    basicInfo: { first_name: '', last_name: '', phone: '', city: '' },
    careerStage: { stage: '', years_experience: 0 },
    education: {
      degree_type: '',
      field_of_study: '',
      school: '',
      graduation_year: new Date().getFullYear(),
      relevant_courses: '',
      academic_highlights: '',
    },
    skills: [],
    softSkills: [],
    workPreferences: {},
  })
  const [loading, setLoading] = useState(false)
  const [skillInput, setSkillInput] = useState('')
  const [softSkillInput, setSoftSkillInput] = useState('')
  const [resumeFile, setResumeFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [userEmail, setUserEmail] = useState<string>(getStoredUserEmail)
  const resumeInputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    const storedEmail = getStoredUserEmail()
    if (storedEmail) {
      setUserEmail(storedEmail)
      return
    }

    const loadEmail = async () => {
      try {
        const { data } = await fetch('http://localhost:8000/auth/me', {
          headers: {
            Authorization: `Bearer ${localStorage.getItem('token') ?? ''}`,
          },
        }).then((res) => res.json())
        if (data?.email) {
          localStorage.setItem('user_email', data.email)
          setUserEmail(data.email)
        }
      } catch {
        // Ignore if the user has not been loaded yet.
      }
    }

    loadEmail()
  }, [])

  const stepOrder: Step[] = [
    'welcome',
    'basic-info',
    'career-stage',
    'education',
    'skills',
    'soft-skills',
    'work-experience',
    'extra',
    'preferences',
    'completion',
  ]

  const currentStepIndex = stepOrder.indexOf(currentStep)

  const goNext = () => {
    const nextIndex = Math.min(currentStepIndex + 1, stepOrder.length - 1)
    setCurrentStep(stepOrder[nextIndex])
  }

  const goBack = () => {
    const prevIndex = Math.max(currentStepIndex - 1, 0)
    setCurrentStep(stepOrder[prevIndex])
  }

  const isBasicInfoComplete =
    formData.basicInfo.first_name.trim() &&
    formData.basicInfo.last_name.trim() &&
    formData.basicInfo.phone.trim() &&
    formData.basicInfo.city.trim()

  const saveBasicInfo = async () => {
    if (!isBasicInfoComplete) {
      return
    }

    setLoading(true)
    try {
      await updateBasicInfo({
        first_name: formData.basicInfo.first_name.trim(),
        last_name: formData.basicInfo.last_name.trim(),
        email: userEmail || getStoredUserEmail() || 'user@example.com',
        phone: formData.basicInfo.phone.trim(),
        city: formData.basicInfo.city.trim(),
      })
      goNext()
    } catch (err) {
      console.error('Error saving basic info:', err)
    } finally {
      setLoading(false)
    }
  }

  const saveCareerStage = async () => {
    setLoading(true)
    try {
      await updateCareerStage({
        career_stage: formData.careerStage.stage,
        years_experience: formData.careerStage.years_experience,
      })
      goNext()
    } catch (err) {
      console.error('Error saving career stage:', err)
    } finally {
      setLoading(false)
    }
  }

  const isEducationComplete =
    formData.education.degree_type.trim() &&
    formData.education.field_of_study.trim() &&
    formData.education.school.trim()

  const saveEducation = async () => {
    if (!isEducationComplete) {
      return
    }

    setLoading(true)
    try {
      await addEducation({
        degree_type: formData.education.degree_type.trim(),
        field_of_study: formData.education.field_of_study.trim(),
        school: formData.education.school.trim(),
        graduation_year: formData.education.graduation_year,
        relevant_courses: formData.education.relevant_courses.trim(),
        academic_highlights: formData.education.academic_highlights.trim(),
      })
      goNext()
    } catch (err) {
      console.error('Error saving education:', err)
    } finally {
      setLoading(false)
    }
  }

  const saveSkills = async () => {
    if (formData.skills.length === 0) {
      return
    }

    setLoading(true)
    try {
      for (const skill of formData.skills) {
        await addSkill({ skill })
      }
      goNext()
    } catch (err) {
      console.error('Error saving skills:', err)
    } finally {
      setLoading(false)
    }
  }

  const saveSoftSkills = async () => {
    setLoading(true)
    try {
      for (const skill of formData.softSkills) {
        await addSoftSkill({ skill })
      }
      goNext()
    } catch (err) {
      console.error('Error saving soft skills:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleResumeUpload = async (file: File) => {
    if (!file) return

    setLoading(true)
    try {
      await uploadResume(file)
      setResumeFile(file)
      goNext()
    } catch (err) {
      console.error('Error uploading resume:', err)
    } finally {
      setLoading(false)
    }
  }

  const skipToPreferences = () => {
    setCurrentStep('preferences')
  }

  const finishOnboarding = async () => {
    setLoading(true)
    try {
      await updatePreferences({
        work_preferences: formData.workPreferences,
      })
      navigate('/jobs')
    } catch (err) {
      console.error('Error saving preferences:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragging(false)

    const files = e.dataTransfer.files
    if (files.length > 0) {
      const file = files[0]
      if (file.type === 'application/pdf' || file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') {
        setResumeFile(file)
        handleResumeUpload(file)
      }
    }
  }

  // ── Welcome Step ────────────────────────────────────────────────────────
  if (currentStep === 'welcome') {
    return (
      <div className="onboarding-container">
        <div className="onboarding-card">
          <h1>Welcome</h1>
          <p style={{ fontSize: '1.25rem', fontWeight: 600 }}>Your tech career starts here</p>
          <p style={{ color: '#888', marginBottom: '2rem' }}>
            Upload your resume and Vector profile details to get started. No resume yet? Start fresh and we will build one together.
          </p>

          <div
            className={`resume-upload-area ${dragging ? 'dragging' : ''}`}
            onClick={() => resumeInputRef.current?.click()}
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '2.5rem', marginBottom: '1rem' }}>☁️</div>
              <p style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Drop your resume here, or click to browse</p>
              <p style={{ fontSize: '0.9rem', color: '#888' }}>PDF or DOCX, up to 10 MB. We will pull out your experience, skills, and education automatically.</p>
            </div>
            <input
              ref={resumeInputRef}
              type="file"
              accept=".pdf,.docx"
              onChange={(e) => {
                if (e.target.files?.[0]) {
                  handleResumeUpload(e.target.files[0])
                }
              }}
              style={{ display: 'none' }}
              id="resume-input"
            />
          </div>

          <button className="btn-primary" onClick={() => setCurrentStep('basic-info')} style={{ marginTop: '2rem' }}>
            ✏️ Start from scratch
          </button>
        </div>
      </div>
    )
  }

  // ── Basic Info Step ────────────────────────────────────────────────────
  if (currentStep === 'basic-info') {
    return (
      <div className="onboarding-container">
        <div className="onboarding-card">
          <div className="step-header">STEP 1 OF 9</div>
          <h1>The basics</h1>
          <p style={{ color: '#888', marginBottom: '2rem' }}>Quick intro. This shows up on your dashboard and resume.</p>

          <div className="form-group">
            <label>First name</label>
            <input
              type="text"
              value={formData.basicInfo.first_name}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  basicInfo: { ...formData.basicInfo, first_name: e.target.value },
                })
              }
              placeholder="Anna"
            />
          </div>

          <div className="form-group">
            <label>Last name</label>
            <input
              type="text"
              value={formData.basicInfo.last_name}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  basicInfo: { ...formData.basicInfo, last_name: e.target.value },
                })
              }
              placeholder="Ber"
            />
          </div>

          <div className="form-group">
            <label>Email address</label>
            <input type="email" disabled placeholder="anna.x.ber@gmail.com" />
          </div>

          <div className="form-group">
            <label>Phone</label>
            <input
              type="tel"
              value={formData.basicInfo.phone}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  basicInfo: { ...formData.basicInfo, phone: e.target.value },
                })
              }
              placeholder="0584476809"
            />
          </div>

          <div className="form-group">
            <label>City</label>
            <input
              type="text"
              value={formData.basicInfo.city}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  basicInfo: { ...formData.basicInfo, city: e.target.value },
                })
              }
              placeholder="Tel Aviv, Jerusalem, Haifa..."
            />
          </div>

          <div className="button-group">
            <button type="button" className="btn-secondary" onClick={goBack}>
              Back
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={() => { void saveBasicInfo() }}
              disabled={loading || !isBasicInfoComplete}
            >
              {loading ? 'Saving...' : 'Continue'}
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── Career Stage Step ───────────────────────────────────────────────────
  if (currentStep === 'career-stage') {
    return (
      <div className="onboarding-container">
        <div className="onboarding-card">
          <div className="step-header">STEP 2 OF 9</div>
          <h1>Where are you starting from?</h1>
          <p style={{ color: '#888', marginBottom: '2rem' }}>Pick the option that best describes your situation.</p>

          <div className="stage-options">
            {[
              { value: 'student', label: 'Student / currently studying', desc: 'Still in school or finishing a degree' },
              { value: 'recent_graduate', label: 'Recent graduate', desc: 'Degree done, figuring out first steps' },
              { value: 'working_professional', label: 'Working professional looking to grow', desc: 'Looking to level up or shift within tech' },
              { value: 'career_switcher', label: 'Career switcher', desc: 'Coming from another field into tech' },
              { value: 'between_jobs', label: 'Between jobs right now', desc: 'Actively looking for your next role' },
              { value: 'returning', label: 'Returning after a break', desc: 'Coming back from leave, travel, or time out' },
            ].map((stage) => (
              <button
                key={stage.value}
                className={`stage-option ${formData.careerStage.stage === stage.value ? 'selected' : ''}`}
                onClick={() =>
                  setFormData({
                    ...formData,
                    careerStage: { ...formData.careerStage, stage: stage.value },
                  })
                }
              >
                <div className="stage-content">
                  <div style={{ fontWeight: 600 }}>{stage.label}</div>
                  <div style={{ fontSize: '0.9rem', color: '#888' }}>{stage.desc}</div>
                </div>
                <input type="radio" checked={formData.careerStage.stage === stage.value} readOnly />
              </button>
            ))}
          </div>

          <div className="form-group" style={{ marginTop: '2rem' }}>
            <label>Years of tech experience</label>
            <input
              type="range"
              min="0"
              max="20"
              value={formData.careerStage.years_experience}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  careerStage: { ...formData.careerStage, years_experience: parseInt(e.target.value) },
                })
              }
              style={{ width: '100%' }}
            />
            <div style={{ marginTop: '0.5rem', color: '#f87171' }}>{formData.careerStage.years_experience} yrs</div>
          </div>

          <div className="button-group">
            <button className="btn-secondary" onClick={goBack}>
              Back
            </button>
            <button className="btn-primary" onClick={saveCareerStage} disabled={loading || !formData.careerStage.stage}>
              {loading ? 'Saving...' : 'Continue'}
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── Education Step ──────────────────────────────────────────────────────
  if (currentStep === 'education') {
    return (
      <div className="onboarding-container">
        <div className="onboarding-card">
          <div className="step-header">STEP 3 OF 9</div>
          <h1>Education</h1>
          <p style={{ color: '#888', marginBottom: '2rem' }}>Your academic background shapes your resume and helps us find the right opportunities for you.</p>

          <div className="degree-options">
            {['Bachelor', 'Master', 'PhD', 'Bootcamp', 'Self taught', 'Other'].map((deg) => (
              <button
                key={deg}
                className={`degree-btn ${formData.education.degree_type === deg ? 'active' : ''}`}
                onClick={() =>
                  setFormData({
                    ...formData,
                    education: { ...formData.education, degree_type: deg },
                  })
                }
              >
                {deg}
              </button>
            ))}
          </div>

          <div className="form-group">
            <label>Field of study</label>
            <input
              type="text"
              value={formData.education.field_of_study}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  education: { ...formData.education, field_of_study: e.target.value },
                })
              }
              placeholder="Computer Science (Specialization in Data Science and AI)"
            />
          </div>

          <div className="form-group">
            <label>School / University / Institution</label>
            <input
              type="text"
              value={formData.education.school}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  education: { ...formData.education, school: e.target.value },
                })
              }
              placeholder="Academic College of Tel Aviv-Yaffo"
            />
          </div>

          <div className="form-group">
            <label>Graduation year</label>
            <input
              type="number"
              value={formData.education.graduation_year}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  education: { ...formData.education, graduation_year: parseInt(e.target.value) },
                })
              }
            />
          </div>

          <div className="form-group">
            <label>Relevant courses (optional)</label>
            <input
              type="text"
              value={formData.education.relevant_courses}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  education: { ...formData.education, relevant_courses: e.target.value },
                })
              }
              placeholder="Data Structures, Machine Learning, UX Design..."
            />
          </div>

          <div className="form-group">
            <label>Academic highlights (optional)</label>
            <input
              type="text"
              value={formData.education.academic_highlights}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  education: { ...formData.education, academic_highlights: e.target.value },
                })
              }
              placeholder="Dean's list, Scholarship, Honors, Research, Teaching assistant..."
            />
          </div>

          <div className="button-group">
            <button className="btn-secondary" onClick={goBack}>
              Back
            </button>
            <button className="btn-primary" onClick={saveEducation} disabled={loading || !isEducationComplete}>
              {loading ? 'Saving...' : 'Continue'}
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── Skills Step ──────────────────────────────────────────────────────────
  if (currentStep === 'skills') {
    return (
      <div className="onboarding-container">
        <div className="onboarding-card">
          <div className="step-header">STEP 4 OF 9</div>
          <h1>Skills and tools</h1>
          <p style={{ color: '#888', marginBottom: '2rem' }}>Add the tools and technologies you use. These go straight into your resume and help us match you to the right roles.</p>

          <div className="skill-input-group">
            <input
              type="text"
              value={skillInput}
              onChange={(e) => setSkillInput(e.target.value)}
              placeholder="Search or add your own..."
              onKeyPress={(e) => {
                if (e.key === 'Enter' && skillInput) {
                  setFormData({
                    ...formData,
                    skills: [...formData.skills, skillInput],
                  })
                  setSkillInput('')
                }
              }}
            />
            <button
              className="btn-add"
              onClick={() => {
                if (skillInput) {
                  setFormData({
                    ...formData,
                    skills: [...formData.skills, skillInput],
                  })
                  setSkillInput('')
                }
              }}
            >
              Add
            </button>
          </div>

          <div className="quick-picks">
            <div style={{ color: '#888', fontSize: '0.9rem', marginBottom: '1rem' }}>QUICK PICKS - 0 / 5</div>
            <div className="quick-picks-grid">
              {['Python', 'JavaScript', 'TypeScript', 'React', 'Node.js', 'Java', 'Go', 'Rust'].map((skill) => (
                <button
                  key={skill}
                  className="quick-pick-btn"
                  onClick={() => {
                    if (!formData.skills.includes(skill)) {
                      setFormData({
                        ...formData,
                        skills: [...formData.skills, skill],
                      })
                    }
                  }}
                >
                  {skill}
                </button>
              ))}
            </div>
          </div>

          <div className="selected-skills">
            {formData.skills.map((skill, idx) => (
              <span key={idx} className="skill-tag">
                {skill}
                <button onClick={() => setFormData({ ...formData, skills: formData.skills.filter((_, i) => i !== idx) })}>
                  ×
                </button>
              </span>
            ))}
          </div>

          <div className="button-group">
            <button className="btn-secondary" onClick={goBack}>
              Back
            </button>
            <button className="btn-primary" onClick={saveSkills} disabled={loading || formData.skills.length === 0}>
              {loading ? 'Saving...' : 'Continue'}
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── Soft Skills Step ────────────────────────────────────────────────────
  if (currentStep === 'soft-skills') {
    return (
      <div className="onboarding-container">
        <div className="onboarding-card">
          <div className="step-header">STEP 5 OF 9</div>
          <h1>Soft skills and languages</h1>
          <p style={{ color: '#888', marginBottom: '2rem' }}>These matter more than most people think. Add what you genuinely bring to a team.</p>

          <div className="section">
            <h3>Soft skills</h3>
            <div className="skill-input-group">
              <input
                type="text"
                value={softSkillInput}
                onChange={(e) => setSoftSkillInput(e.target.value)}
                placeholder="Add your own soft skill..."
                onKeyPress={(e) => {
                  if (e.key === 'Enter' && softSkillInput) {
                    setFormData({
                      ...formData,
                      softSkills: [...formData.softSkills, softSkillInput],
                    })
                    setSoftSkillInput('')
                  }
                }}
              />
              <button
                className="btn-add"
                onClick={() => {
                  if (softSkillInput) {
                    setFormData({
                      ...formData,
                      softSkills: [...formData.softSkills, softSkillInput],
                    })
                    setSoftSkillInput('')
                  }
                }}
              >
                Add
              </button>
            </div>

            <div className="soft-skills-grid">
              {[
                'Leadership',
                'Communication',
                'Problem solving',
                'Teamwork',
                'Mentoring',
                'Public speaking',
                'Project management',
                'Analytical thinking',
                'Adaptability',
                'Creativity',
                'Conflict resolution',
                'Time management',
                'Cross-functional collaboration',
                'Customer empathy',
              ].map((skill) => (
                <button
                  key={skill}
                  className={`soft-skill-btn ${formData.softSkills.includes(skill) ? 'selected' : ''}`}
                  onClick={() => {
                    if (formData.softSkills.includes(skill)) {
                      setFormData({
                        ...formData,
                        softSkills: formData.softSkills.filter((s) => s !== skill),
                      })
                    } else {
                      setFormData({
                        ...formData,
                        softSkills: [...formData.softSkills, skill],
                      })
                    }
                  }}
                >
                  {skill}
                </button>
              ))}
            </div>
          </div>

          <div className="button-group">
            <button className="btn-secondary" onClick={goBack}>
              Back
            </button>
            <button className="btn-primary" onClick={saveSoftSkills} disabled={loading}>
              {loading ? 'Saving...' : 'Continue'}
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── Work Experience Step ────────────────────────────────────────────────
  if (currentStep === 'work-experience') {
    return (
      <div className="onboarding-container">
        <div className="onboarding-card">
          <div className="step-header">STEP 6 OF 9</div>
          <h1>Work and service experience</h1>
          <p style={{ color: '#888', marginBottom: '2rem' }}>Add jobs, internships, freelance, or military service. The more detail you include, the stronger your resume becomes.</p>

          <div className="add-section">
            <button className="btn-add-position" onClick={() => goNext()}>
              + Add a position
            </button>
          </div>

          <div className="button-group">
            <button className="btn-secondary" onClick={goBack}>
              Back
            </button>
            <button className="btn-primary" onClick={goNext}>
              Continue
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── Extra Step (Certifications, Volunteering, etc.) ───────────────────
  if (currentStep === 'extra') {
    return (
      <div className="onboarding-container">
        <div className="onboarding-card">
          <div className="step-header">STEP 7 OF 9</div>
          <h1>Everything else that makes you, you</h1>
          <p style={{ color: '#888', marginBottom: '2rem' }}>Volunteering, certifications, hackathons, clubs. These help round out your profile and often make the difference in a competitive market.</p>

          <div className="extras-section">
            <div className="extra-item">
              <h4>Volunteering</h4>
              <input type="text" placeholder="e.g. Youth coding instructor at Perach" />
              <button className="btn-add">Add</button>
            </div>

            <div className="extra-item">
              <h4>Certifications</h4>
              <input type="text" placeholder="e.g. AWS Certified Developer, Google Analytics" />
              <button className="btn-add">Add</button>
            </div>

            <div className="extra-item">
              <h4>Hackathons</h4>
              <input type="text" placeholder="e.g. HackIDC 2023" />
              <button className="btn-add">Add</button>
            </div>

            <div className="extra-item">
              <h4>Competitions</h4>
              <input type="text" placeholder="e.g. ICPC, Olympiad" />
              <button className="btn-add">Add</button>
            </div>

            <div className="extra-item">
              <h4>Clubs and organizations</h4>
              <input type="text" placeholder="e.g. Student Union, Tech Club, IEEE" />
              <button className="btn-add">Add</button>
            </div>

            <div className="extra-item">
              <h4>GitHub</h4>
              <input type="text" placeholder="GitHub URL" />
              <button className="btn-add">Add</button>
            </div>

            <div className="extra-item">
              <h4>Portfolio</h4>
              <input type="text" placeholder="Portfolio URL" />
              <button className="btn-add">Add</button>
            </div>
          </div>

          <div className="button-group">
            <button className="btn-secondary" onClick={goBack}>
              Back
            </button>
            <button className="btn-primary" onClick={goNext}>
              Continue
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── Preferences Step ────────────────────────────────────────────────────
  if (currentStep === 'preferences') {
    return (
      <div className="onboarding-container">
        <div className="onboarding-card">
          <div className="step-header">STEP 8 OF 9</div>
          <h1>What excites you most?</h1>
          <p style={{ color: '#888', marginBottom: '2rem' }}>Pick everything that genuinely resonates. This tells us what kind of work will keep you energized.</p>

          <div className="preferences-grid">
            {[
              {
                id: 'building_products',
                icon: '🔧',
                label: 'Building products',
                desc: 'Shipping features, solving real problems',
              },
              {
                id: 'working_with_people',
                icon: '👥',
                label: 'Working with people',
                desc: 'Customers, collaboration, relationships',
              },
              {
                id: 'leading_managing',
                icon: '🚩',
                label: 'Leading and managing',
                desc: 'Owning strategy, growing teams',
              },
              {
                id: 'data_insights',
                icon: '📊',
                label: 'Data and insights',
                desc: 'Finding patterns, driving decisions',
              },
              {
                id: 'design_creativity',
                icon: '🎨',
                label: 'Design and creativity',
                desc: 'Crafting experiences, visual thinking',
              },
              {
                id: 'making_impact',
                icon: '🌍',
                label: 'Making an impact',
                desc: 'Products that actually change things',
              },
              {
                id: 'deep_technical',
                icon: '🎯',
                label: 'Deep technical work',
                desc: 'Architecture, systems, hard problems',
              },
              {
                id: 'fast_growth',
                icon: '📈',
                label: 'Fast growth and scale',
                desc: 'Startups, moving fast, high stakes',
              },
              {
                id: 'automating_optimizing',
                icon: '⚙️',
                label: 'Automating and optimizing',
                desc: 'Making manual, repetitive work disappear',
              },
            ].map((pref) => (
              <button
                key={pref.id}
                className={`pref-card ${formData.workPreferences[pref.id] ? 'selected' : ''}`}
                onClick={() =>
                  setFormData({
                    ...formData,
                    workPreferences: {
                      ...formData.workPreferences,
                      [pref.id]: !formData.workPreferences[pref.id],
                    },
                  })
                }
              >
                <div style={{ fontSize: '2rem' }}>{pref.icon}</div>
                <div style={{ fontWeight: 600 }}>{pref.label}</div>
                <div style={{ fontSize: '0.9rem', color: '#888' }}>{pref.desc}</div>
                {formData.workPreferences[pref.id] && (
                  <div style={{ position: 'absolute', top: 10, right: 10, color: '#30bfb8' }}>✓</div>
                )}
              </button>
            ))}
          </div>

          <div className="button-group">
            <button className="btn-secondary" onClick={goBack}>
              Back
            </button>
            <button className="btn-primary" onClick={goNext}>
              Continue
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── Completion Step ─────────────────────────────────────────────────────
  if (currentStep === 'completion') {
    return (
      <div className="onboarding-container">
        <div className="onboarding-card">
          <div className="step-header">STEP 9 OF 9</div>
          <h1>You are all set!</h1>
          <p style={{ color: '#888', marginBottom: '2rem' }}>Your profile is ready. Vector will now show you opportunities tailored to your skills and preferences.</p>

          <div className="completion-message">
            <p>Based on your profile, here are your top role matches:</p>
            <div style={{ marginTop: '2rem', padding: '1.5rem', background: '#f3f4f6', borderRadius: '0.5rem' }}>
              <p style={{ fontWeight: 600, marginBottom: '0.5rem' }}>🎯 Machine Learning Engineer (Junior)</p>
              <p style={{ color: '#888', marginBottom: '1rem' }}>88% match</p>
              <p style={{ fontWeight: 600, marginBottom: '0.5rem' }}>🤖 AI/LLM Engineer (Junior)</p>
              <p style={{ color: '#888', marginBottom: '1rem' }}>85% match</p>
              <p style={{ fontWeight: 600, marginBottom: '0.5rem' }}>📊 Data Engineer (Junior)</p>
              <p style={{ color: '#888' }}>74% match</p>
            </div>
          </div>

          <button className="btn-primary" onClick={finishOnboarding} disabled={loading} style={{ width: '100%', marginTop: '2rem' }}>
            {loading ? 'Setting up...' : 'Go to Job Board'}
          </button>
        </div>
      </div>
    )
  }

  return null
}
