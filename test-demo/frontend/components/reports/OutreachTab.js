'use client';

import React from 'react';
import { Download, Mail, Send, Reply, ShieldAlert, AlertOctagon, UserX } from 'lucide-react';
import { exportToCsv, formatNum, formatPct } from './reportUtils';

export default function OutreachTab({ data }) {
  const totalSent = data?.total_sent || 0;
  const byChannel = data?.by_channel || {};
  const perf = data?.performance || {};
  const dncBlocked = data?.dnc_blocked_leads || 0;
  const topSent = data?.top_subjects_sent || [];
  const topReplied = data?.top_subjects_replied || [];

  const handleExport = () => {
    const cols = [
      { key: 'subject', label: 'Email Subject' },
      { key: 'sends', label: 'Sends' },
      { key: 'replies', label: 'Replies' },
    ];
    const allSubjects = new Set([...topSent.map(s => s.subject), ...topReplied.map(s => s.subject)]);
    const rows = Array.from(allSubjects).map(sub => {
      const sObj = topSent.find(s => s.subject === sub);
      const rObj = topReplied.find(r => r.subject === sub);
      return {
        subject: sub,
        sends: sObj ? sObj.count : 0,
        replies: rObj ? rObj.count : 0
      };
    });
    exportToCsv('outreach_email_performance', cols, rows);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* 4 Outcome Metrics */}
      <div className="rp-kpi-grid">
        <div className="rp-kpi-card" title="Total emails dispatched across all outreach channels">
          <div className="rp-kpi-title">Total Outbound Sends</div>
          <div className="rp-kpi-val" style={{ color: 'var(--primary-blue)' }}>{formatNum(totalSent)}</div>
          <div className="rp-kpi-sub">Across cold pitches & follow-up sequences</div>
        </div>

        <div className="rp-kpi-card" title="Verified prospect replies received">
          <div className="rp-kpi-title">Direct Replies</div>
          <div className="rp-kpi-val" style={{ color: 'var(--success-green)' }}>{formatNum(perf.replies || 0)}</div>
          <div className="rp-kpi-sub">{formatPct(perf.reply_rate_pct)} reply rate</div>
        </div>

        <div className="rp-kpi-card" title="Permanent SMTP bounce failures">
          <div className="rp-kpi-title">Bounces</div>
          <div className="rp-kpi-val" style={{ color: 'var(--danger-red)' }}>{formatNum(perf.bounces || 0)}</div>
          <div className="rp-kpi-sub">Invalid or expired prospect domains</div>
        </div>

        <div className="rp-kpi-card" title="Leads blocked from email outreach by Do-Not-Contact blacklist">
          <div className="rp-kpi-title">Do-Not-Contact Shield</div>
          <div className="rp-kpi-val" style={{ color: 'var(--warning-amber)' }}>{formatNum(dncBlocked)}</div>
          <div className="rp-kpi-sub">Shielded from outreach (e.g. 8dots)</div>
        </div>
      </div>

      {/* Sends Split By Channel */}
      <div className="rp-table-card">
        <div className="rp-table-top">
          <div className="rp-table-title">
            <Send size={16} color="var(--primary-blue)" />
            Outreach Channels Breakdown
          </div>
        </div>

        <div style={{ padding: '1.25rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem' }}>
          <div style={{ background: 'var(--bg-subtle)', padding: '1rem', borderRadius: 'var(--radius-inner)' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 600 }}>1-HOUR AUTO SCRAPER</div>
            <div style={{ fontSize: '1.35rem', fontWeight: 800, marginTop: 4 }}>{formatNum(byChannel.auto || 0)}</div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Automated introductory pitches</div>
          </div>

          <div style={{ background: 'var(--bg-subtle)', padding: '1rem', borderRadius: 'var(--radius-inner)' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 600 }}>FOLLOW-UP SEQUENCES</div>
            <div style={{ fontSize: '1.35rem', fontWeight: 800, marginTop: 4 }}>{formatNum(byChannel.sequence || 0)}</div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Day 3, 7, 14 sequence steps</div>
          </div>

          <div style={{ background: 'var(--bg-subtle)', padding: '1rem', borderRadius: 'var(--radius-inner)' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 600 }}>DASHBOARD MANUAL</div>
            <div style={{ fontSize: '1.35rem', fontWeight: 800, marginTop: 4 }}>{formatNum(byChannel.manual || 0)}</div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Individual 1-click sends</div>
          </div>

          <div style={{ background: 'var(--bg-subtle)', padding: '1rem', borderRadius: 'var(--radius-inner)' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 600 }}>BULK EMAIL CAMPAIGNS</div>
            <div style={{ fontSize: '1.35rem', fontWeight: 800, marginTop: 4 }}>{formatNum(byChannel.bulk || 0)}</div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Multi-select bulk dispatches</div>
          </div>

          <div style={{ background: 'var(--bg-subtle)', padding: '1rem', borderRadius: 'var(--radius-inner)' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 600 }}>SENT BEFORE TRACKING</div>
            <div style={{ fontSize: '1.35rem', fontWeight: 800, marginTop: 4 }}>{formatNum(byChannel.before_tracking || 0)}</div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Archived in sent_emails.csv</div>
          </div>
        </div>
      </div>

      {/* Top Performing Subjects */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1rem' }}>
        <div className="rp-table-card">
          <div className="rp-table-top">
            <div className="rp-table-title" style={{ fontSize: '0.85rem' }}>
              Top Outgoing Email Subjects
            </div>
            <button type="button" className="theme-pill-btn neutral" onClick={handleExport} style={{ fontSize: '0.72rem', padding: '3px 8px' }}>
              <Download size={11} /> CSV
            </button>
          </div>
          <div className="theme-table-scroll">
            <table className="jp-table">
              <thead>
                <tr>
                  <th>Subject</th>
                  <th style={{ textAlign: 'right' }}>Sends</th>
                </tr>
              </thead>
              <tbody>
                {topSent.length === 0 ? (
                  <tr><td colSpan={2} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No emails recorded yet</td></tr>
                ) : (
                  topSent.map((s, idx) => (
                    <tr key={idx}>
                      <td style={{ fontSize: '0.76rem', fontWeight: 500 }}>{s.subject}</td>
                      <td style={{ textAlign: 'right', fontWeight: 700 }}>{formatNum(s.count)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="rp-table-card">
          <div className="rp-table-top">
            <div className="rp-table-title" style={{ fontSize: '0.85rem' }}>
              Top Reply-Generating Subjects
            </div>
          </div>
          <div className="theme-table-scroll">
            <table className="jp-table">
              <thead>
                <tr>
                  <th>Subject</th>
                  <th style={{ textAlign: 'right' }}>Replies</th>
                </tr>
              </thead>
              <tbody>
                {topReplied.length === 0 ? (
                  <tr><td colSpan={2} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No replies recorded in this range</td></tr>
                ) : (
                  topReplied.map((s, idx) => (
                    <tr key={idx}>
                      <td style={{ fontSize: '0.76rem', fontWeight: 500 }}>{s.subject}</td>
                      <td style={{ textAlign: 'right', fontWeight: 700, color: 'var(--success-green)' }}>{formatNum(s.count)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

