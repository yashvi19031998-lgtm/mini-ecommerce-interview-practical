'use client';

import React from 'react';
import { Database, Mail, CheckCircle2, Clock } from 'lucide-react';

export default function StatsCards({ leads = [] }) {
  const total = leads.length;
  const withEmail = leads.filter(l => l.Email && l.Email.includes('@') && l.Email !== 'N/A').length;
  const emailSent = leads.filter(l => {
    const s = String(l['Email Status'] || l.Status || '').toUpperCase();
    return s === 'SENT' || s === 'EMAIL_SENT';
  }).length;
  const pending = total - emailSent;
  const emailPct = total > 0 ? Math.round((withEmail / total) * 100) : 0;
  const sentPct = total > 0 ? Math.round((emailSent / total) * 100) : 0;

  return (
    <div className="theme-overview-grid">
      {/* 1. Total Scraped Leads - Lavender #ecedfb */}
      <div className="theme-kpi-card card-lavender">
        <div className="theme-kpi-label">Total Leads</div>
        <div className="theme-kpi-val-row">
          <span className="theme-kpi-value">{total.toLocaleString()}</span>
          <span className="theme-kpi-badge badge-pos">
            +100%
            <svg width="12" height="12" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 14L16 6M16 6h-6M16 6v6" />
            </svg>
          </span>
        </div>
      </div>

      {/* 2. Leads with Verified Email - Soft Blue #e7f0fd */}
      <div className="theme-kpi-card card-blue">
        <div className="theme-kpi-label">Verified Emails</div>
        <div className="theme-kpi-val-row">
          <span className="theme-kpi-value">{withEmail.toLocaleString()}</span>
          <span className="theme-kpi-badge badge-neutral">
            {emailPct}% rate
          </span>
        </div>
      </div>

      {/* 3. Outreach Completed - Mint Green #e8f6ee */}
      <div className="theme-kpi-card card-green">
        <div className="theme-kpi-label">Outreach Sent</div>
        <div className="theme-kpi-val-row">
          <span className="theme-kpi-value">{emailSent.toLocaleString()}</span>
          <span className="theme-kpi-badge badge-pos">
            {sentPct}% sent
            <svg width="12" height="12" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 14L16 6M16 6h-6M16 6v6" />
            </svg>
          </span>
        </div>
      </div>

      {/* 4. Pending Master Queue - Peach/Warm Amber #fdf1e3 */}
      <div className="theme-kpi-card card-peach">
        <div className="theme-kpi-label">Pending Queue</div>
        <div className="theme-kpi-val-row">
          <span className="theme-kpi-value">{pending.toLocaleString()}</span>
          <span className="theme-kpi-badge badge-neutral">
            Ready
          </span>
        </div>
      </div>
    </div>
  );
}
