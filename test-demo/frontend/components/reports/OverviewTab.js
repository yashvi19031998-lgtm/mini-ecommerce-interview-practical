'use client';

import React from 'react';
import { 
  Users, Flame, Mail, Send, CheckCircle2, Calendar, 
  TrendingUp, TrendingDown, AlertTriangle, ArrowRight, ShieldAlert, Bug
} from 'lucide-react';
import { formatNum } from './reportUtils';

export default function OverviewTab({ data, onSwitchTab }) {
  if (!data) return null;

  const { cards = [], daily_series = [], period = {}, attention_counts = {} } = data;

  const maxChartVal = Math.max(
    ...daily_series.map(d => Math.max(d.new_leads || 0, d.emails_sent || 0)),
    1
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* 3 Quick Attention Alerts */}
      <div className="rp-attention-grid">
        <div 
          className="rp-attention-box" 
          onClick={() => onSwitchTab('followups')}
          style={{ borderLeft: '4px solid var(--danger-red)' }}
          role="button"
          tabIndex={0}
        >
          <div>
            <div style={{ fontSize: '0.72rem', color: 'var(--danger-red)', fontWeight: 700, textTransform: 'uppercase' }}>
              Overdue Follow-ups
            </div>
            <div style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-primary)', marginTop: 2 }}>
              {formatNum(attention_counts.overdue_followups || 0)}
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              Scheduled dates passed · Needs immediate action
            </div>
          </div>
          <ArrowRight size={18} color="var(--danger-red)" />
        </div>

        <div 
          className="rp-attention-box" 
          onClick={() => onSwitchTab('scrapers')}
          style={{ borderLeft: '4px solid var(--warning-amber)' }}
          role="button"
          tabIndex={0}
        >
          <div>
            <div style={{ fontSize: '0.72rem', color: 'var(--warning-amber)', fontWeight: 700, textTransform: 'uppercase' }}>
              Scraper Engine Failures
            </div>
            <div style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-primary)', marginTop: 2 }}>
              {formatNum(attention_counts.failed_scrapers || 0)}
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              Execution errors recorded in selected period
            </div>
          </div>
          <ArrowRight size={18} color="var(--warning-amber)" />
        </div>

        <div 
          className="rp-attention-box" 
          onClick={() => onSwitchTab('data-health')}
          style={{ borderLeft: '4px solid var(--primary-blue)' }}
          role="button"
          tabIndex={0}
        >
          <div>
            <div style={{ fontSize: '0.72rem', color: 'var(--primary-blue)', fontWeight: 700, textTransform: 'uppercase' }}>
              Data Quality & Health
            </div>
            <div style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-primary)', marginTop: 2 }}>
              Audit Report
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              Missing contacts, stale leads & duplicate checks
            </div>
          </div>
          <ArrowRight size={18} color="var(--primary-blue)" />
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="rp-kpi-grid">
        {cards.map(card => {
          const hasChange = card.change !== null && card.change !== undefined && !period.is_all_time;
          const isUp = hasChange && card.change > 0;
          const isDown = hasChange && card.change < 0;

          return (
            <div 
              key={card.key} 
              className="rp-kpi-card" 
              title={`${card.title}${card.prev_value !== null ? ` (Previous period: ${formatNum(card.prev_value)})` : ''}`}
            >
              <div className="rp-kpi-header">
                <span className="rp-kpi-title">{card.label}</span>
              </div>
              <div className="rp-kpi-val">{formatNum(card.value)}</div>
              <div className="rp-kpi-sub">
                {hasChange ? (
                  <span className={isUp ? 'rp-change-up' : (isDown ? 'rp-change-down' : '')} style={{ display: 'inline-flex', alignItems: 'center', gap: 2 }}>
                    {isUp && <TrendingUp size={12} />}
                    {isDown && <TrendingDown size={12} />}
                    {card.change > 0 ? `+${card.change}` : card.change} vs prev period
                  </span>
                ) : (
                  <span>{period.is_all_time ? 'All-time total' : 'No previous period'}</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Daily Activity Chart */}
      <div className="rp-chart-card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem', flexWrap: 'wrap', gap: 8 }}>
          <div>
            <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
              Daily Lead Harvesting & Outreach Cadence
            </h4>
            <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
              Shows daily new leads discovered (Blue) and cold outreach emails sent (Green) over {period.days || daily_series.length} days.
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, fontSize: '0.75rem', fontWeight: 600 }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={{ width: 10, height: 10, background: 'var(--primary-blue)', borderRadius: 2 }} />
              New Leads
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={{ width: 10, height: 10, background: 'var(--success-green)', borderRadius: 2 }} />
              Emails Sent
            </span>
          </div>
        </div>

        {daily_series.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.82rem' }}>
            No daily activity recorded in this date range.
          </div>
        ) : (
          <div className="rp-chart-container" role="img" aria-label="Daily leads and emails bar chart">
            {daily_series.map(day => {
              const leadH = Math.round(((day.new_leads || 0) / maxChartVal) * 110);
              const emailH = Math.round(((day.emails_sent || 0) / maxChartVal) * 110);
              const dayLabel = day.date ? day.date.slice(5) : '';

              return (
                <div key={day.date} className="rp-chart-col" title={`${day.date}: ${day.new_leads} new leads, ${day.emails_sent} emails sent`}>
                  <div className="rp-chart-bar-wrap">
                    <div 
                      className="rp-chart-bar-leads" 
                      style={{ height: `${Math.max(leadH, (day.new_leads ? 4 : 0))}px` }} 
                    />
                    <div 
                      className="rp-chart-bar-emails" 
                      style={{ height: `${Math.max(emailH, (day.emails_sent ? 4 : 0))}px` }} 
                    />
                  </div>
                  <span className="rp-chart-date">{dayLabel}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

