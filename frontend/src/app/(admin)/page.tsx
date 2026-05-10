'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import type { DashboardStats, Interview } from '@/types';

export default function DashboardPage() {
  const router = useRouter();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [statsData, interviewsData] = await Promise.all([
          api.getStats(),
          api.listInterviews({ limit: 10 }),
        ]);
        setStats(statsData);
        setInterviews(interviewsData.interviews);
      } catch (err) {
        console.error('Failed to load dashboard:', err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="loading-overlay">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">Overview of your AI interview pipeline</p>
        </div>
        <Link href="/interviews/new" className="btn btn-primary btn-lg">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M12 5v14M5 12h14" /></svg>
          Create Interview
        </Link>
      </div>

      {/* Stats */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Total Interviews</div>
          <div className="stat-value purple">{stats?.total_interviews || 0}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Completed</div>
          <div className="stat-value emerald">{stats?.completed || 0}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Average Score</div>
          <div className="stat-value blue">
            {stats?.average_score != null ? `${stats.average_score}` : '--'}
            <span style={{ fontSize: '16px', color: 'var(--text-muted)', fontWeight: 400 }}>/100</span>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Pending</div>
          <div className="stat-value amber">{stats?.pending || 0}</div>
        </div>
      </div>

      {/* Recent Interviews */}
      <div className="table-container">
        <div className="table-header">
          <h2 className="table-title">Recent Interviews</h2>
          <Link href="/interviews" className="btn btn-secondary btn-sm">View All</Link>
        </div>

        {interviews.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">&#128203;</div>
            <div className="empty-state-title">No interviews yet</div>
            <div className="empty-state-text">Create your first AI interview to get started</div>
            <Link href="/interviews/new" className="btn btn-primary">Create Interview</Link>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Candidate</th>
                <th>Job Title</th>
                <th>Status</th>
                <th>Score</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {interviews.map((interview) => (
                <tr key={interview.id} onClick={() => router.push(`/interviews/${interview.id}`)}>
                  <td>{interview.candidate_name}</td>
                  <td>{interview.job_title}</td>
                  <td>
                    <span className={`badge badge-${interview.status}`}>
                      {interview.status.replace('_', ' ')}
                    </span>
                  </td>
                  <td>
                    {interview.report
                      ? <span style={{ color: 'var(--accent-emerald-light)', fontWeight: 600 }}>{interview.report.overall_score}/100</span>
                      : <span style={{ color: 'var(--text-muted)' }}>--</span>
                    }
                  </td>
                  <td>{interview.created_at ? new Date(interview.created_at).toLocaleDateString() : '--'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
