'use client';

import { useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';

interface AssessmentPoint {
  name: string;
  description: string;
  weight: number;
}

const STEP_LABELS = ['Job Details', 'Resume', 'Assessment Points', 'Review'];

const TEMPLATE_POINTS: AssessmentPoint[] = [
  { name: 'Technical Skills', description: 'Assess core technical competencies relevant to the role', weight: 5 },
  { name: 'Communication', description: 'Clarity, articulation, and ability to explain concepts', weight: 4 },
  { name: 'Problem Solving', description: 'Approach to challenges and analytical thinking', weight: 4 },
  { name: 'Cultural Fit', description: 'Alignment with company values and team dynamics', weight: 3 },
  { name: 'Motivation', description: 'Interest in the role and long-term career goals', weight: 3 },
];

export default function CreateInterviewPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [createdLink, setCreatedLink] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [jobTitle, setJobTitle] = useState('');
  const [jobDescription, setJobDescription] = useState('');
  const [candidateName, setCandidateName] = useState('');
  const [candidateEmail, setCandidateEmail] = useState('');
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [duration, setDuration] = useState(15);
  const [points, setPoints] = useState<AssessmentPoint[]>([
    { name: '', description: '', weight: 3 },
    { name: '', description: '', weight: 3 },
    { name: '', description: '', weight: 3 },
  ]);

  const addPoint = () => {
    if (points.length < 10) {
      setPoints([...points, { name: '', description: '', weight: 3 }]);
    }
  };

  const removePoint = (idx: number) => {
    if (points.length > 3) {
      setPoints(points.filter((_, i) => i !== idx));
    }
  };

  const updatePoint = (idx: number, field: keyof AssessmentPoint, value: string | number) => {
    const updated = [...points];
    // Fix: Cast to unknown then to the record to satisfy TS index signature requirements
    (updated[idx] as unknown as Record<string, string | number>)[field] = value;
    setPoints(updated);
  };

  const useTemplate = () => {
    setPoints([...TEMPLATE_POINTS]);
  };

  const canProceed = () => {
    switch (step) {
      case 0: return jobTitle.trim() && jobDescription.trim().length >= 10;
      case 1: return candidateName.trim();
      case 2: return points.length >= 3 && points.every(p => p.name.trim());
      case 3: return true;
      default: return false;
    }
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('job_title', jobTitle.trim());
      formData.append('job_description', jobDescription.trim());
      formData.append('candidate_name', candidateName.trim());
      if (candidateEmail.trim()) formData.append('candidate_email', candidateEmail.trim());
      formData.append('assessment_points', JSON.stringify(points.filter(p => p.name.trim())));
      formData.append('max_duration_minutes', String(duration));
      if (resumeFile) formData.append('resume', resumeFile);

      const result = await api.createInterview(formData);
      setCreatedLink(result.interview_link || `http://localhost:3000/room/${result.interview_token}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create interview');
    } finally {
      setSubmitting(false);
    }
  };

  const copyLink = () => {
    if (createdLink) {
      navigator.clipboard.writeText(createdLink);
      alert('Link copied to clipboard!');
    }
  };

  // Success modal
  if (createdLink) {
    return (
      <div style={{ maxWidth: '600px', margin: '80px auto', textAlign: 'center' }}>
        <div style={{ fontSize: '48px', marginBottom: '16px' }}>&#9989;</div>
        <h1 className="page-title" style={{ marginBottom: '8px' }}>Interview Created!</h1>
        <p className="page-subtitle" style={{ marginBottom: '32px' }}>Share this link with {candidateName} to begin the interview</p>

        <div className="interview-link-box">
          <span className="interview-link-url">{createdLink}</span>
          <button className="btn btn-primary btn-sm" onClick={copyLink}>Copy</button>
        </div>

        <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', marginTop: '32px' }}>
          <button className="btn btn-secondary" onClick={() => router.push('/interviews')}>View All Interviews</button>
          <button className="btn btn-primary" onClick={() => {
            setCreatedLink(null);
            setStep(0);
            setJobTitle(''); setJobDescription(''); setCandidateName('');
            setCandidateEmail(''); setResumeFile(null);
            setPoints([{ name: '', description: '', weight: 3 }, { name: '', description: '', weight: 3 }, { name: '', description: '', weight: 3 }]);
          }}>
            Create Another
          </button>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Create Interview</h1>
        <p className="page-subtitle">Set up an AI interview for a candidate</p>
      </div>

      {/* Wizard Steps */}
      <div className="wizard-steps">
        {STEP_LABELS.map((label, i) => (
          <div key={i} style={{ display: 'contents' }}>
            <div className={`wizard-step ${i === step ? 'active' : i < step ? 'completed' : ''}`}>
              <div className="wizard-step-number">{i < step ? '\u2713' : i + 1}</div>
              <span className="wizard-step-label">{label}</span>
            </div>
            {i < STEP_LABELS.length - 1 && <div className="wizard-divider" />}
          </div>
        ))}
      </div>

      <div className="card" style={{ maxWidth: '720px' }}>
        {error && (
          <div style={{ padding: '12px 16px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 'var(--radius-md)', color: 'var(--accent-red)', fontSize: '14px', marginBottom: '20px' }}>
            {error}
          </div>
        )}

        {/* Step 0: Job Details */}
        {step === 0 && (
          <>
            <div className="form-group">
              <label className="form-label">Job Title *</label>
              <input className="form-input" placeholder="e.g. Senior React Developer" value={jobTitle} onChange={e => setJobTitle(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Job Description / Specifications *</label>
              <textarea className="form-textarea" rows={8} placeholder="Paste the full job description, requirements, and specifications..." value={jobDescription} onChange={e => setJobDescription(e.target.value)} />
            </div>
          </>
        )}

        {/* Step 1: Candidate + Resume */}
        {step === 1 && (
          <>
            <div className="form-group">
              <label className="form-label">Candidate Name *</label>
              <input className="form-input" placeholder="Full name" value={candidateName} onChange={e => setCandidateName(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Candidate Email (optional)</label>
              <input className="form-input" type="email" placeholder="candidate@email.com" value={candidateEmail} onChange={e => setCandidateEmail(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Resume Upload (optional)</label>
              <input ref={fileInputRef} type="file" accept=".pdf,.docx,.doc,.png,.jpg,.jpeg" style={{ display: 'none' }} onChange={e => setResumeFile(e.target.files?.[0] || null)} />
              <div className="upload-zone" onClick={() => fileInputRef.current?.click()}>
                {resumeFile ? (
                  <div>
                    <div style={{ fontSize: '24px', marginBottom: '8px' }}>&#128196;</div>
                    <div style={{ color: 'var(--accent-emerald-light)', fontWeight: 600 }}>{resumeFile.name}</div>
                    <div className="upload-zone-hint">{(resumeFile.size / 1024 / 1024).toFixed(2)} MB - Click to change</div>
                  </div>
                ) : (
                  <div>
                    <div className="upload-zone-icon">&#128228;</div>
                    <div className="upload-zone-text">Click to upload resume</div>
                    <div className="upload-zone-hint">PDF, DOCX, PNG, or JPG (any format)</div>
                  </div>
                )}
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Interview Duration</label>
              <select className="form-select" value={duration} onChange={e => setDuration(Number(e.target.value))}>
                <option value={5}>5 minutes</option>
                <option value={10}>10 minutes</option>
                <option value={15}>15 minutes (recommended)</option>
                <option value={20}>20 minutes</option>
                <option value={30}>30 minutes</option>
              </select>
            </div>
          </>
        )}

        {/* Step 2: Assessment Points */}
        {step === 2 && (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <div>
                <div style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>Define what the AI should assess ({points.length}/10)</div>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={useTemplate}>Use Template</button>
            </div>

            {points.map((point, idx) => (
              <div className="point-item" key={idx}>
                <div className="point-item-number">{idx + 1}</div>
                <div className="point-item-fields">
                  <input className="form-input" placeholder="Assessment point name (e.g. Technical Skills)" value={point.name} onChange={e => updatePoint(idx, 'name', e.target.value)} />
                  <input className="form-input" placeholder="What should the AI assess? (optional)" value={point.description} onChange={e => updatePoint(idx, 'description', e.target.value)} />
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Weight:</span>
                    <div className="weight-selector">
                      {[1, 2, 3, 4, 5].map(w => (
                        <span key={w} className={`weight-star ${w <= point.weight ? 'filled' : ''}`} onClick={() => updatePoint(idx, 'weight', w)} style={{ cursor: 'pointer', fontSize: '18px' }}>
                          {w <= point.weight ? '\u2605' : '\u2606'}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
                {points.length > 3 && (
                  <button className="point-remove" onClick={() => removePoint(idx)} title="Remove">&times;</button>
                )}
              </div>
            ))}

            {points.length < 10 && (
              <button className="btn btn-secondary" onClick={addPoint} style={{ width: '100%', marginTop: '8px' }}>
                + Add Assessment Point
              </button>
            )}
          </>
        )}

        {/* Step 3: Review */}
        {step === 3 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div>
              <div className="form-label">Job Title</div>
              <div style={{ fontSize: '16px', fontWeight: 600 }}>{jobTitle}</div>
            </div>
            <div>
              <div className="form-label">Job Description</div>
              <div style={{ fontSize: '14px', color: 'var(--text-secondary)', maxHeight: '100px', overflow: 'auto' }}>{jobDescription}</div>
            </div>
            <div style={{ display: 'flex', gap: '40px' }}>
              <div><div className="form-label">Candidate</div><div>{candidateName}</div></div>
              <div><div className="form-label">Duration</div><div>{duration} min</div></div>
              <div><div className="form-label">Resume</div><div>{resumeFile ? resumeFile.name : 'None'}</div></div>
            </div>
            <div>
              <div className="form-label">Assessment Points ({points.filter(p => p.name.trim()).length})</div>
              {points.filter(p => p.name.trim()).map((p, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                  <span style={{ color: 'var(--accent-purple-light)', fontWeight: 600, width: '24px' }}>{i + 1}.</span>
                  <span style={{ flex: 1 }}>{p.name}</span>
                  <span style={{ color: 'var(--accent-amber)', fontSize: '13px' }}>{'★'.repeat(p.weight)}{'☆'.repeat(5 - p.weight)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Navigation */}
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '32px', paddingTop: '20px', borderTop: '1px solid var(--border-subtle)' }}>
          <button className="btn btn-secondary" onClick={() => setStep(Math.max(0, step - 1))} disabled={step === 0}>
            Back
          </button>
          {step < 3 ? (
            <button className="btn btn-primary" onClick={() => setStep(step + 1)} disabled={!canProceed()}>
              Continue
            </button>
          ) : (
            <button className="btn btn-primary btn-lg" onClick={handleSubmit} disabled={submitting || !canProceed()}>
              {submitting ? <><div className="spinner" style={{ width: 16, height: 16 }} /> Creating...</> : 'Create Interview'}
            </button>
          )}
        </div>
      </div>
    </>
  );
}