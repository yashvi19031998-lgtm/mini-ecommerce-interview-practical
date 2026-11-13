'use client';

import React from 'react';
import { exportToCsv, formatNum } from './reportUtils';
import { Calendar, Download, Clock, Activity, ExternalLink } from 'lucide-react';

export default function DailyLogTab({
  data,
  loading,
  selectedDay,
  onDayChange,
  onOpenLeads,
  onOpenScraper
}) {
  if (loading) {
    return (
      <div className="rp-loading-state" role="status" aria-live="polite">
        <div className="rp-spinner" />
        <p>Loading daily event timeline...</p>
      </div>
    );
  }

  const events = data?.events || [];
  const totalEvents = data?.total_events || events.length;
  const currentDay = selectedDay || data?.day || new Date().toISOString().slice(0, 10);

  const handleExport = () => {
    const headers = ['Timestamp', 'Type', 'Badge', 'Title', 'Description', 'Lead ID', 'Lead / Target'];
    const rows = events.map((ev) => [
      ev.time,
      ev.type,
      ev.badge,
      ev.title,
      ev.description,
      ev.lead_id || '',
      ev.lead_name || ''
    ]);
    exportToCsv(`daily_log_${currentDay}.csv`, headers, rows);
  };

  const getBadgeClass = (badge) => {
    const b = (badge || '').toUpperCase();
    if (b.includes('SCRAPER')) return 'rp-timeline-badge-scraper';
    if (b.includes('LEAD')) return 'rp-timeline-badge-lead';
    if (b.includes('EMAIL')) return 'rp-timeline-badge-email';
    if (b.includes('MEETING') || b.includes('WON')) return 'rp-timeline-badge-meeting';
    if (b.includes('CALL')) return 'rp-timeline-badge-call';
    return 'rp-timeline-badge-default';
  };

  return (
    <div className="rp-tab-pane">
      {/* Header bar */}
      <div className="rp-header-row">
        <div>
          <h2 className="rp-section-title">Daily Activity Audit Log</h2>
          <p className="rp-section-sub">
            Chronological log of scraper executions, newly ingested leads, sent emails, and follow-up touchpoints.
          </p>
        </div>

        <div className="rp-header-actions">
          <div className="rp-day-picker-group">
            <Calendar size={14} color="var(--text-secondary)" />
            <input
              type="date"
              className="rp-input-date"
              value={currentDay}
              onChange={(e) => onDayChange && onDayChange(e.target.value)}
              aria-label="Select log date"
            />
          </div>

          <button
            type="button"
            className="rp-btn rp-btn-secondary"
            onClick={handleExport}
            disabled={events.length === 0}
            title="Export daily timeline to CSV"
          >
            <Download size={14} />
            <span>Export CSV</span>
          </button>
        </div>
      </div>

      {/* Events Summary Bar */}
      <div className="rp-timeline-summary-bar">
        <div className="rp-timeline-summary-item">
          <Activity size={16} />
          <span>
            Total Events on <strong>{currentDay}</strong>: <strong>{formatNum(totalEvents)}</strong>
          </span>
        </div>
      </div>

      {/* Timeline Stream */}
      {events.length === 0 ? (
        <div className="rp-empty-state">
          <Clock size={36} color="var(--text-tertiary)" />
          <p>No logged events found for {currentDay}.</p>
          <span className="rp-empty-sub">
            Try selecting another date or check your scraper and outreach activity.
          </span>
        </div>
      ) : (
        <div className="rp-timeline-container">
          <div className="rp-timeline-track" />
          <div className="rp-timeline-list">
            {events.map((ev, idx) => (
              <div key={`${ev.time}-${idx}`} className="rp-timeline-row">
                <div className="rp-timeline-dot" />
                <div className="rp-timeline-card">
                  <div className="rp-timeline-card-header">
                    <div className="rp-timeline-badge-group">
                      <span className={`rp-timeline-badge ${getBadgeClass(ev.badge)}`}>
                        {ev.badge}
                      </span>
                      <span className="rp-timeline-time">{ev.time}</span>
                    </div>

                    {ev.lead_id && (
                      <span className="rp-timeline-lead-ref">
                        Lead: <strong>{ev.lead_name || ev.lead_id}</strong>
                      </span>
                    )}
                  </div>

                  <h3 className="rp-timeline-title">{ev.title}</h3>
                  <p className="rp-timeline-desc">{ev.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

