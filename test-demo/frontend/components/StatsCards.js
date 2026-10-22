'use client';

import React from 'react';
import { Database, Mail, CheckCircle2, Clock, TrendingUp, Sparkles } from 'lucide-react';

export default function StatsCards({ leads = [] }) {
  const total = leads.length;
  const withEmail = leads.filter(l => l.Email && l.Email.includes('@') && l.Email !== 'N/A').length;
  const emailSent = leads.filter(l => {
    const s = String(l['Email Status'] || l.Status || '').toUpperCase();
    return s === 'SENT' || s === 'EMAIL_SENT';
  }).length;
  const pending = total - emailSent;
  const emailPct = total > 0 ? Math.round((withEmail / total) * 100) : 0;

  return (
    <div className="stats-row-container">
      {/* 1. Total Leads */}
      <div className="stat-box stat-box-lavender">
        <div className="stat-icon-wrapper stat-icon-lavender">
          <Database size={22} />
        </div>
        <div className="stat-content">
          <div className="stat-number">{total.toLocaleString()}</div>
          <div className="stat-label-text">Total Scraped Leads</div>
          <div className="stat-sub-badge badge-lavender">
            <TrendingUp size={11} /> 100% Real Database
          </div>
        </div>
      </div>

      {/* 2. Leads with Verified Email */}
      <div className="stat-box stat-box-emerald">
        <div className="stat-icon-wrapper stat-icon-emerald">
          <Mail size={22} />
        </div>
        <div className="stat-content">
          <div className="stat-number">{withEmail.toLocaleString()}</div>
          <div className="stat-label-text">
            With Email ({emailPct}%)
          </div>
          <div className="stat-sub-badge badge-emerald">
            <Sparkles size={11} /> Verified Contact Rate
          </div>
        </div>
      </div>

      {/* 3. Outreach Completed */}
      <div className="stat-box stat-box-pink">
        <div className="stat-icon-wrapper stat-icon-pink">
          <CheckCircle2 size={22} />
        </div>
        <div className="stat-content">
          <div className="stat-number">{emailSent.toLocaleString()}</div>
          <div className="stat-label-text">Outreach Completed</div>
          <div className="stat-sub-badge badge-pink">
            Delivered Sequences
          </div>
        </div>
      </div>

      {/* 4. Pending Emails */}
      <div className="stat-box stat-box-amber">
        <div className="stat-icon-wrapper stat-icon-amber">
          <Clock size={22} />
        </div>
        <div className="stat-content">
          <div className="stat-number">{pending.toLocaleString()}</div>
          <div className="stat-label-text">Pending Emails</div>
          <div className="stat-sub-badge badge-amber">
            In Master Queue
          </div>
        </div>
      </div>
    </div>
  );
}
