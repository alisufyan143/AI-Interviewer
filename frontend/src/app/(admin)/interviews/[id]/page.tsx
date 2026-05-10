'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import type { Interview } from '@/types';

export default function InterviewDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [interview, setInterview] = useState<Interview | null>(null);
  const [loading, setLoading] = useState(true);
  const [scoring, setScoring] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const data = await api.getInterview(params.id as string);
        setInterview(data as Interview);
      } catch (err) {
        console.error('Failed to load interview:', err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [params.id]);

  if (loading) return <div className="loading-overlay"><div className="spinner" /></div>;
  if (!interview) return <div className="empty-state"><div className="empty-state-title">Interview not found</div></div>;

  const copyLink = () => {
    const link = interview.interview_link || `http://localhost:3000/room/${interview.interview_token}`;
    navigator.clipboard.writeText(link);
    alert('Link copied!');
  };

  const getScoreColor = (score: number) => {
    if (score >= 75) return 'var(--accent-emerald)';
    if (score >= 50) return 'var(--accent-amber)';
    return 'var(--accent-red)';
  };

  return (
    <>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <button className="btn btn-secondary btn-sm" onClick={() => router.push('/interviews')} style={{ marginBottom: '12px' }}>
            &larr; Back to Interviews
          </button>
          <h1 className="page-title">{interview.candidate_name}</h1>
          <p className="page-subtitle">{interview.job_title}</p>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <span className={`badge badge-${interview.status}`} style={{ fontSize: '14px', padding: '6px 16px' }}>
            {interview.status.replace('_', ' ')}
          </span>
          {interview.status === 'pending' && (
            <button className="btn btn-primary" onClick={copyLink}>Copy Interview Link</button>
          )}
        </div>
      </div>

      {/* Pending State */}
      {interview.status === 'pending' && (
        <div className="card" style={{ textAlign: 'center', padding: '48px' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px', opacity: 0.5 }}>&#9203;</div>
          <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '8px' }}>Waiting for candidate</h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '24px' }}>Share the interview link with {interview.candidate_name} to begin</p>
          <div className="interview-link-box" style={{ maxWidth: '500px', margin: '0 auto' }}>
            <span className="interview-link-url">{interview.interview_link || `http://localhost:3000/room/${interview.interview_token}`}</span>
            <button className="btn btn-primary btn-sm" onClick={copyLink}>Copy</button>
          </div>
        </div>
      )}

      {/* Completed but no report — show score button */}
      {interview.status === 'completed' && !interview.report && (
        <div className="card" style={{ textAlign: 'center', padding: '48px' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>&#128202;</div>
          <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '8px' }}>Interview Completed</h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '24px' }}>Generate the AI assessment report for {interview.candidate_name}</p>
          <button 
            className="btn btn-primary btn-lg" 
            disabled={scoring}
            onClick={async () => {
              setScoring(true);
              try {
                await api.scoreInterview(interview.id);
                const data = await api.getInterview(params.id as string);
                setInterview(data as Interview);
              } catch (err) {
                alert('Scoring failed: ' + (err instanceof Error ? err.message : 'Unknown error'));
              } finally {
                setScoring(false);
              }
            }}
          >
            {scoring ? <><div className="spinner" style={{ width: 16, height: 16 }} /> Generating Report...</> : '📊 Generate Report'}
          </button>
        </div>
      )}

      {/* Completed — Report */}
      {interview.status === 'completed' && interview.report && (
        <>
          {/* Score Overview */}
          <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: '24px', marginBottom: '24px' }}>
            <div className="card" style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
              <div className="score-gauge" style={{ background: `conic-gradient(${getScoreColor(interview.report.overall_score)} ${interview.report.overall_score * 3.6}deg, var(--bg-elevated) 0deg)` }}>
                <div style={{ width: '120px', height: '120px', borderRadius: '50%', background: 'var(--bg-card)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                  <div className="score-gauge-value">{interview.report.overall_score}</div>
                  <div className="score-gauge-label">out of 100</div>
                </div>
              </div>
              <span className={`badge badge-${interview.report.recommendation}`} style={{ marginTop: '16px', fontSize: '14px', padding: '6px 16px' }}>
                {interview.report.recommendation.replace('_', ' ')}
              </span>
            </div>

            <div className="card">
              <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '12px' }}>Executive Summary</h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '14px', lineHeight: 1.7 }}>{interview.report.summary || 'No summary available'}</p>
            </div>
          </div>

          {/* Assessment Scores */}
          {interview.report.assessment_scores.length > 0 && (
            <div className="card" style={{ marginBottom: '24px' }}>
              <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '20px' }}>Assessment Breakdown</h3>
              {interview.report.assessment_scores.map((score, idx) => (
                <div key={idx} style={{ marginBottom: '20px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                    <span style={{ fontSize: '14px', fontWeight: 500 }}>{score.point_name}</span>
                    <span style={{ fontSize: '14px', fontWeight: 700, color: getScoreColor(score.score * 10) }}>{score.score}/{score.max_score}</span>
                  </div>
                  <div style={{ height: '8px', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-full)', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${(score.score / score.max_score) * 100}%`, background: `linear-gradient(90deg, ${getScoreColor(score.score * 10)}, ${getScoreColor(score.score * 10)}dd)`, borderRadius: 'var(--radius-full)', transition: 'width 0.6s ease' }} />
                  </div>
                  {score.evidence && <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px', fontStyle: 'italic' }}>{score.evidence}</p>}
                </div>
              ))}
            </div>
          )}

          {/* Strengths & Concerns */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '24px' }}>
            <div className="card">
              <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '12px', color: 'var(--accent-emerald-light)' }}>Strengths</h3>
              <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {(interview.report.strengths || []).map((s, i) => (
                  <li key={i} style={{ fontSize: '14px', color: 'var(--text-secondary)', paddingLeft: '16px', position: 'relative' }}>
                    <span style={{ position: 'absolute', left: 0, color: 'var(--accent-emerald)' }}>+</span>{s}
                  </li>
                ))}
              </ul>
            </div>
            <div className="card">
              <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '12px', color: 'var(--accent-amber)' }}>Concerns</h3>
              <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {(interview.report.concerns || []).map((c, i) => (
                  <li key={i} style={{ fontSize: '14px', color: 'var(--text-secondary)', paddingLeft: '16px', position: 'relative' }}>
                    <span style={{ position: 'absolute', left: 0, color: 'var(--accent-amber)' }}>!</span>{c}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Transcript */}
          {interview.messages && interview.messages.length > 0 && (
            <div className="card">
              <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px' }}>Interview Transcript</h3>
              <div style={{ maxHeight: '400px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {interview.messages.map((msg, idx) => (
                  <div key={idx} style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                    <span style={{ fontSize: '12px', color: 'var(--text-muted)', minWidth: '50px', textAlign: 'right', marginTop: '2px' }}>
                      {Math.floor(msg.timestamp_seconds / 60)}:{String(Math.floor(msg.timestamp_seconds % 60)).padStart(2, '0')}
                    </span>
                    <span style={{ fontSize: '12px', fontWeight: 600, color: msg.role === 'ai' ? 'var(--accent-purple-light)' : 'var(--accent-emerald-light)', minWidth: '70px' }}>
                      {msg.role === 'ai' ? 'AI' : 'Candidate'}
                    </span>
                    <p style={{ fontSize: '14px', color: 'var(--text-secondary)', flex: 1, margin: 0 }}>{msg.content}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Interview Config */}
      <div className="card" style={{ marginTop: '24px' }}>
        <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px' }}>Interview Configuration</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', fontSize: '14px' }}>
          <div><span style={{ color: 'var(--text-muted)' }}>Duration:</span> {interview.max_duration_minutes} minutes</div>
          <div><span style={{ color: 'var(--text-muted)' }}>Points:</span> {Array.isArray(interview.assessment_points) ? interview.assessment_points.length : 'N/A'} assessment criteria</div>
          <div style={{ gridColumn: '1 / -1' }}><span style={{ color: 'var(--text-muted)' }}>Created:</span> {interview.created_at ? new Date(interview.created_at).toLocaleString() : '--'}</div>
        </div>
      </div>
    </>
  );
}
