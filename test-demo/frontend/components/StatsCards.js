'use client';

import React from 'react';
import { Database, Flame, Award, Zap, ArrowUpRight } from 'lucide-react';

export default function StatsCards({ leads = [], onFilterClick = null, activeFilter = 'all' }) {
  const total = leads.length;
  
  // Hot AI leads (Score >= 7)
  const hotCount = leads.filter(l => {
    const score = parseFloat(l.ai_score);
    return Number.isFinite(score) && score >= 7;
  }).length;

  // Senior Fit matches (8-9+ Yrs)
  const seniorCount = leads.filter(l => {
    const fit = String(l.seniority_fit || '').toLowerCase();
    return fit.includes('senior') || fit.includes('lead');
  }).length;

  // Outreach ready: either verified email or WhatsApp ready
  const outreachReadyCount = leads.filter(l => {
    const hasEmail = l.Email && l.Email.includes('@') && l.Email !== 'N/A';
    const hasWa = l.whatsapp_status === 'READY' || (l['Mobile Number'] && l['Mobile Number'] !== 'N/A');
    return hasEmail || hasWa;
  }).length;

  const hotPct = total > 0 ? Math.round((hotCount / total) * 100) : 0;
  const seniorPct = total > 0 ? Math.round((seniorCount / total) * 100) : 0;
  const readyPct = total > 0 ? Math.round((outreachReadyCount / total) * 100) : 0;

  return (
    <div className="theme-overview-grid">
      {/* 1. Total Scraped B2B Leads */}
      <div 
        className={`theme-kpi-card card-blue ${activeFilter === 'all' ? 'active-filter' : ''}`}
        onClick={() => onFilterClick && onFilterClick('all')}
        style={{ cursor: 'pointer' }}
        title="View All Leads"
      >
        <div className="theme-kpi-header-row">
          <div className="theme-kpi-icon-wrap icon-blue">
            <Database size={16} />
          </div>
          <span className="theme-kpi-badge badge-pos">Live Registry</span>
        </div>
        <div className="theme-kpi-label">Total B2B Leads</div>
        <div className="theme-kpi-val-row">
          <span className="theme-kpi-value">{total.toLocaleString()}</span>
          <span className="theme-kpi-subtext">All lead sources</span>
        </div>
      </div>

      {/* 2. Hot AI Qualified (Score 7-10) */}
      <div 
        className={`theme-kpi-card card-peach ${activeFilter === 'hot' ? 'active-filter' : ''}`}
        onClick={() => onFilterClick && onFilterClick('hot')}
        style={{ cursor: 'pointer' }}
        title="Filter Hot AI Qualified Leads (7-10)"
      >
        <div className="theme-kpi-header-row">
          <div className="theme-kpi-icon-wrap icon-peach">
            <Flame size={16} />
          </div>
          <span className="theme-kpi-badge badge-amber">{hotPct}% Match</span>
        </div>
        <div className="theme-kpi-label">🔥 Hot AI Qualified</div>
        <div className="theme-kpi-val-row">
          <span className="theme-kpi-value">{hotCount.toLocaleString()}</span>
          <span className="theme-kpi-subtext">Score 7-10 Fit</span>
        </div>
      </div>

      {/* 3. Senior Engineer Matches (8-9+ Yrs) */}
      <div 
        className={`theme-kpi-card card-lavender ${activeFilter === 'senior' ? 'active-filter' : ''}`}
        onClick={() => onFilterClick && onFilterClick('senior')}
        style={{ cursor: 'pointer' }}
        title="Filter Senior / Tech Lead Matches"
      >
        <div className="theme-kpi-header-row">
          <div className="theme-kpi-icon-wrap icon-lavender">
            <Award size={16} />
          </div>
          <span className="theme-kpi-badge badge-purple">{seniorPct}% High-Value</span>
        </div>
        <div className="theme-kpi-label">💼 Senior Fit (8-9+ Yrs)</div>
        <div className="theme-kpi-val-row">
          <span className="theme-kpi-value">{seniorCount.toLocaleString()}</span>
          <span className="theme-kpi-subtext">$3k - $8k Deal Fit</span>
        </div>
      </div>

      {/* 4. Ready for Outreach */}
      <div 
        className={`theme-kpi-card card-green ${activeFilter === 'ready' ? 'active-filter' : ''}`}
        onClick={() => onFilterClick && onFilterClick('ready')}
        style={{ cursor: 'pointer' }}
        title="Filter Outreach Ready Leads"
      >
        <div className="theme-kpi-header-row">
          <div className="theme-kpi-icon-wrap icon-green">
            <Zap size={16} />
          </div>
          <span className="theme-kpi-badge badge-pos">{readyPct}% Direct</span>
        </div>
        <div className="theme-kpi-label">⚡ Outreach Ready</div>
        <div className="theme-kpi-val-row">
          <span className="theme-kpi-value">{outreachReadyCount.toLocaleString()}</span>
          <span className="theme-kpi-subtext">Email / WhatsApp</span>
        </div>
      </div>
    </div>
  );
}
