'use client';

import Link from 'next/link';

export default function ThankYouPage() {
  return (
    <div className="app-layout" style={{ justifyContent: 'center', alignItems: 'center', background: 'var(--bg-primary)' }}>
      <div className="card card-glass" style={{ maxWidth: '500px', textAlign: 'center', padding: '48px' }}>
        <div style={{ fontSize: '64px', marginBottom: '24px' }}>&#127881;</div>
        <h1 className="page-title">Interview Completed!</h1>
        <p className="page-subtitle" style={{ marginBottom: '32px' }}>
          Thank you for your time. Your interview has been successfully recorded and submitted for review.
        </p>
        <p style={{ color: 'var(--text-muted)', fontSize: '14px', marginBottom: '32px' }}>
          Our recruitment team will analyze your responses and get back to you soon.
        </p>
        <Link href="/" className="btn btn-secondary">
          Return Home
        </Link>
      </div>
    </div>
  );
}
