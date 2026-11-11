'use client';

// Dashboard: quick overview of the lead database (the KPI cards above it come from StatsCards).

import React, { useMemo } from 'react';
import { Briefcase, Flame, ArrowRight } from 'lucide-react';

const HOT_SCORE = 7;

const scoreOf = (l) => {
  const n = parseFloat(l.ai_score);
  return Number.isFinite(n) ? n : null;
};

// "Reddit (r/forhire) | Search Engine" -> "Reddit"
const sourceFamily = (l) => String(l.Source || l.source || 'Unknown').split('|')[0].split(' (')[0].trim() || 'Unknown';

export default function Dashboard({ leads = [], onOpenJobPortal, onOpenLeads }) {
  const stats = useMemo(() => {
    const hot = leads
      .filter(l => (scoreOf(l) ?? -1) >= HOT_SCORE)
      .sort((a, b) => scoreOf(b) - scoreOf(a))
      .slice(0, 6);
    const bySource = {};
    leads.forEach(l => { const s = sourceFamily(l); bySource[s] = (bySource[s] || 0) + 1; });
    const sources = Object.entries(bySource).sort((a, b) => b[1] - a[1]).slice(0, 8);
    const jobPortalLeads = leads.filter(l => sourceFamily(l) === 'Job Portal').length;
    return { hot, sources, max: sources.length ? sources[0][1] : 1, jobPortalLeads };
  }, [leads]);

  return (
    <div className="jp-dash-grid">
      {/* Hot leads */}
      <div className="theme-card-panel" style={{ marginBottom: 0 }}>
        <div className="theme-panel-header">
          <div>
            <div className="theme-panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Flame size={16} color="var(--danger-red)" /> Top hot leads
            </div>
            <div className="theme-panel-sub">Highest AI score (7+)</div>
          </div>
          <button type="button" className="theme-pill-btn neutral" onClick={onOpenLeads}>
            View all <ArrowRight size={13} />
          </button>
        </div>
        <div className="jp-dash-list">
          {stats.hot.length === 0 ? (
            <div className="jp-hint">No AI-scored hot leads yet.</div>
          ) : stats.hot.map(l => (
            <div key={l.id} className="jp-dash-row">
              <div style={{ minWidth: 0 }}>
                <div className="jp-cell-title" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {l['Company Name'] || l.company_name || 'Unknown company'}
                </div>
                <div className="jp-cell-sub">{l.ai_summary || sourceFamily(l)}</div>
              </div>
              <span className="jp-status-chip ok">{scoreOf(l)}/10</span>
            </div>
          ))}
        </div>
      </div>

      {/* Leads by source + Job portal entry */}
      <div className="theme-card-panel" style={{ marginBottom: 0 }}>
        <div className="theme-panel-header">
          <div>
            <div className="theme-panel-title">Leads by source</div>
            <div className="theme-panel-sub">{leads.length} leads in total · {stats.jobPortalLeads} from job portals</div>
          </div>
          <button type="button" className="theme-pill-btn primary" onClick={onOpenJobPortal}>
            <Briefcase size={13} /> Job Portal Scraper
          </button>
        </div>
        <div className="jp-dash-list">
          {stats.sources.length === 0 ? (
            <div className="jp-hint">No leads yet. Use the Job Portal Scraper to find companies that are hiring.</div>
          ) : stats.sources.map(([name, count]) => (
            <div key={name} className="jp-dash-row">
              <span style={{ minWidth: 120 }}>{name}</span>
              <div className="jp-bar-track" aria-hidden="true">
                <div className="jp-bar-fill" style={{ width: `${Math.round((count / stats.max) * 100)}%` }} />
              </div>
              <span style={{ fontWeight: 600, minWidth: 40, textAlign: 'right' }}>{count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
