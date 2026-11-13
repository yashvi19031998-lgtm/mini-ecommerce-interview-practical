'use client';

import React from 'react';
import { Download, GitFork, ArrowRight, AlertCircle, Clock } from 'lucide-react';
import { exportToCsv, formatNum, formatPct } from './reportUtils';

export default function PipelineTab({ data }) {
  const stages = data?.stages || [];
  const conversions = data?.conversions || [];
  const stuck = data?.stuck_leads || { counts: {}, total_stuck: 0 };
  const totalLeads = data?.total_leads || 0;

  const handleExport = () => {
    const cols = [
      { key: 'stage', label: 'Pipeline Stage' },
      { key: 'count', label: 'Lead Count' },
      { key: 'percentage', label: 'Share %' },
      { key: 'stuck', label: 'Stuck (>14d)' },
    ];
    const rows = stages.map(s => ({
      ...s,
      percentage: `${s.percentage}%`,
      stuck: stuck.counts[s.stage] || 0
    }));
    exportToCsv('pipeline_funnel_stages', cols, rows);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* 8 Stage Cards */}
      <div className="rp-table-card">
        <div className="rp-table-top">
          <div className="rp-table-title">
            <GitFork size={16} color="var(--primary-blue)" />
            Lead Lifecycle Pipeline Stages ({formatNum(totalLeads)} leads in period)
          </div>
          <div className="rp-table-actions">
            <button type="button" className="theme-pill-btn neutral" onClick={handleExport} disabled={stages.length === 0}>
              <Download size={13} /> Export Pipeline CSV
            </button>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '0.75rem', padding: '1.25rem' }}>
          {stages.map(st => (
            <div 
              key={st.stage} 
              style={{
                background: 'var(--bg-subtle)',
                border: '1px solid var(--border-light)',
                borderRadius: 'var(--radius-inner)',
                padding: '0.85rem 0.75rem',
                textAlign: 'center'
              }}
            >
              <div style={{ fontSize: '0.68rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                {st.stage}
              </div>
              <div style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--text-primary)', marginTop: 4 }}>
                {formatNum(st.count)}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: 2 }}>
                {formatPct(st.percentage)} of total
              </div>
              {(stuck.counts[st.stage] || 0) > 0 && (
                <div style={{ fontSize: '0.68rem', color: 'var(--danger-red)', fontWeight: 600, marginTop: 4 }}>
                  {stuck.counts[st.stage]} stuck &gt;14d
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Progression Conversions Funnel */}
      <div className="rp-table-card">
        <div className="rp-table-top">
          <div className="rp-table-title">
            Stage Progression & Conversion Velocity
          </div>
        </div>

        <div style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {conversions.map(c => {
            const hasRate = c.conversion_pct !== null && c.conversion_pct !== undefined;
            return (
              <div 
                key={`${c.from_stage}-${c.to_stage}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.75rem 1rem',
                  background: 'var(--bg-white)',
                  border: '1px solid var(--border-light)',
                  borderRadius: 8,
                  gap: 12
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600, fontSize: '0.82rem' }}>
                  <span className="rp-badge rp-badge-neutral">{c.from_stage} ({formatNum(c.from_count)})</span>
                  <ArrowRight size={14} color="var(--text-muted)" />
                  <span className="rp-badge rp-badge-neutral">{c.to_stage} ({formatNum(c.to_count)})</span>
                </div>

                <div style={{ textAlign: 'right' }}>
                  <span style={{ fontSize: '0.95rem', fontWeight: 800, color: hasRate ? 'var(--primary-blue)' : 'var(--text-muted)' }}>
                    {hasRate ? `${c.conversion_pct}%` : '—'}
                  </span>
                  <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                    {hasRate ? 'Conversion rate' : 'No earlier leads in stage'}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Stuck Leads Alert Box */}
      <div className="jp-alert" style={{ background: 'var(--bg-white)', borderColor: 'var(--border-med)', color: 'var(--text-primary)' }}>
        <Clock size={16} color="var(--warning-amber)" />
        <div style={{ fontSize: '0.8rem' }}>
          <strong>{formatNum(stuck.total_stuck)} leads</strong> have had no activity for more than 14 days across the pipeline. Check Follow-ups to re-engage them.
        </div>
      </div>
    </div>
  );
}

