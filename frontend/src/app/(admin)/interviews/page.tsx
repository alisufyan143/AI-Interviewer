'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import type { Interview } from '@/types';

export default function InterviewsPage() {
  const router = useRouter();
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const [search, setSearch] = useState('');

  const loadInterviews = async () => {
    setLoading(true);
    try {
      const data = await api.listInterviews({
        status: statusFilter !== 'all' ? statusFilter : undefined,
        search: search || undefined,
        limit: 50,
      });
      setInterviews(data.interviews);
      setTotal(data.total);
    } catch (err) {
      console.error('Failed to load interviews:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadInterviews(); }, [statusFilter]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    loadInterviews();
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Delete this interview? This cannot be undone.')) return;
    try {
      await api.deleteInterview(id);
      loadInterviews();
    } catch (err) {
      console.error('Failed to delete:', err);
    }
  };

  const copyLink = (link: string, e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(link);
    alert('Interview link copied!');
  };

  return (
    <>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 className="page-title">Interviews</h1>
          <p className="page-subtitle">{total} total interviews</p>
        </div>
        <Link href="/interviews/new" className="btn btn-primary">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 5v14M5 12h14" /></svg>
          Create New
        </Link>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '24px', alignItems: 'center' }}>
        <form onSubmit={handleSearch} style={{ flex: 1 }}>
          <input
            type="text"
            className="form-input"
            placeholder="Search by candidate or job title..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ maxWidth: '400px' }}
          />
        </form>
        {['all', 'pending', 'in_progress', 'completed'].map((s) => (
          <button
            key={s}
            className={`btn btn-sm ${statusFilter === s ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setStatusFilter(s)}
          >
            {s === 'all' ? 'All' : s.replace('_', ' ')}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="table-container">
        {loading ? (
          <div className="loading-overlay"><div className="spinner" /></div>
        ) : interviews.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">&#128270;</div>
            <div className="empty-state-title">No interviews found</div>
            <div className="empty-state-text">
              {search ? 'Try a different search term' : 'Create your first interview to get started'}
            </div>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Candidate</th>
                <th>Job Title</th>
                <th>Status</th>
                <th>Score</th>
                <th>Duration</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {interviews.map((i) => (
                <tr key={i.id} onClick={() => router.push(`/interviews/${i.id}`)}>
                  <td>{i.candidate_name}</td>
                  <td>{i.job_title}</td>
                  <td><span className={`badge badge-${i.status}`}>{i.status.replace('_', ' ')}</span></td>
                  <td>
                    {i.report
                      ? <span style={{ color: 'var(--accent-emerald-light)', fontWeight: 600 }}>{i.report.overall_score}</span>
                      : '--'
                    }
                  </td>
                  <td>{i.max_duration_minutes} min</td>
                  <td>{i.created_at ? new Date(i.created_at).toLocaleDateString() : '--'}</td>
                  <td>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      {i.interview_link && (
                        <button className="btn btn-secondary btn-sm" onClick={(e) => copyLink(i.interview_link!, e)}>
                          Copy Link
                        </button>
                      )}
                      <button className="btn btn-danger btn-sm" onClick={(e) => handleDelete(i.id, e)}>
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
