'use client';

// Automation -> 1-Hour Auto Lead Scraper & Outreach Engine
// Displays schedule status, real-time trigger, targeting scope, and historical scraper runs.

import React, { useEffect, useState } from 'react';
import { 
  Clock, Play, RefreshCw, CheckCircle2, AlertTriangle, 
  Terminal, Mail, Database, MapPin, Sliders, ExternalLink, Loader2 
} from 'lucide-react';
import { fetchSchedulerStatus, triggerSchedulerJob } from '../lib/api';

export default function AutoScheduler({ onNavigateToSettings, onNavigateToLeads }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [triggering, setTriggering] = useState(false);
  const [notice, setNotice] = useState(null);

  const loadStatus = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetchSchedulerStatus();
      if (res && res.success) {
        setData(res);
      } else {
        setError(res?.error || 'Could not load automation status');
      }
    } catch (err) {
      setError(err.message || 'Failed connecting to automation backend');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
    const interval = setInterval(() => {
      fetchSchedulerStatus().then(res => {
        if (res && res.success) setData(res);
      }).catch(() => {});
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleTriggerRun = async () => {
    // A full cycle runs every scraper and - when auto-send is on - e-mails real people. Never on one stray click.
    const emailNote = data?.auto_send_email
      ? (Number(data?.max_pending_emails) === 0
          ? 'It will also send intro e-mails to EVERY qualified lead it finds (no per-run limit; at most 50 a day, verified mailboxes only).'
          : `It will also send up to ${data?.max_pending_emails ?? 5} intro e-mails to real leads.`)
      : 'Auto e-mail is off, so no e-mails will be sent.';
    if (!window.confirm(`Run the full scraping cycle now? It can take several minutes.

${emailNote}`)) return;
    setTriggering(true);
    setNotice(null);
    try {
      const res = await triggerSchedulerJob();
      if (res.success) {
        setNotice({ type: 'success', text: res.message || '1-Hour Scraper job started in the background!' });
        setTimeout(loadStatus, 2000);
      } else {
        setNotice({ type: 'error', text: res.error || 'Failed triggering scraper run' });
      }
    } catch (err) {
      setNotice({ type: 'error', text: err.message || 'Error triggering scraper job' });
    } finally {
      setTriggering(false);
    }
  };

  const runs = data?.runs || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Top Banner & Control Card */}
      <div className="theme-card-panel" style={{ marginBottom: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.25rem' }}>
          <div>
            <div className="theme-panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Clock size={20} color="var(--primary-lavender)" />
              1-Hour Auto Lead Scraper & Outreach Engine
            </div>
            <div className="theme-panel-sub">
              Runs every scraper once an hour, applies AI qualification, and dispatches verified email outreach.
            </div>
          </div>

          <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
            <button
              type="button"
              className="theme-pill-btn neutral"
              onClick={loadStatus}
              disabled={loading}
              title="Refresh status"
            >
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
              Refresh
            </button>

            <button
              type="button"
              className="theme-pill-btn primary"
              onClick={handleTriggerRun}
              disabled={triggering || data?.is_running}
              title="Trigger a full 1-hour scraping & outreach cycle immediately"
            >
              {triggering || data?.is_running ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  {data?.is_running ? 'Running 1-Hr Scraper…' : 'Triggering…'}
                </>
              ) : (
                <>
                  <Play size={14} />
                  Run 1-Hour Cycle Now
                </>
              )}
            </button>
          </div>
        </div>

        {notice && (
          <div role="status" className={`jp-alert ${notice.type === 'error' ? 'jp-alert-error' : 'jp-alert-success'}`} style={{ marginBottom: '1rem' }}>
            {notice.type === 'error' ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}
            <span style={{ flex: 1 }}>{notice.text}</span>
            <button type="button" className="jp-alert-close" aria-label="Dismiss message" onClick={() => setNotice(null)}>×</button>
          </div>
        )}

        {/* 4 Metrics Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
          <div className="glass-panel" style={{ padding: '0.85rem 1rem' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Execution Schedule
            </div>
            <div style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px' }}>
              {data?.schedule || 'Every 1 Hour'}
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              Cron: {data?.cron || '23 * * * *'} (GitHub Actions & Local)
            </div>
          </div>

          <div className="glass-panel" style={{ padding: '0.85rem 1rem' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Automated Email Outreach
            </div>
            <div style={{ fontSize: '1.05rem', fontWeight: 700, color: data?.auto_send_email ? '#10b981' : '#f59e0b', marginTop: '4px', display: 'flex', alignItems: 'center', gap: 6 }}>
              <Mail size={16} />
              {data?.auto_send_email ? 'Active (Auto-Send ON)' : 'Manual Review Only'}
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              {data?.auto_send_email
                ? `${Number(data?.max_pending_emails) === 0 ? 'Every qualified lead (no per-run limit)' : `Max ${data?.max_pending_emails ?? 5} outreach emails per cycle`} · max ${data?.max_emails_per_day ?? 50}/day${data?.smtp_configured === false ? ' · mail login missing in .env' : ''}`
                : (data?.auto_send_reason || 'Auto e-mail is off')}
            </div>
          </div>

          <div className="glass-panel" style={{ padding: '0.85rem 1rem' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Targeting Scope
            </div>
            <div style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px', display: 'flex', alignItems: 'center', gap: 6 }}>
              <MapPin size={16} color="var(--primary-lavender)" />
              {data?.default_city || 'Ahmedabad'}, {data?.default_state || 'Gujarat'}
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={(data?.default_keywords || []).join(', ')}>
              Keywords: {(data?.default_keywords || []).slice(0, 3).join(', ') || 'software, web, IT'}
            </div>
            {data?.excluded_companies && data.excluded_companies.length > 0 && (
              <div style={{ fontSize: '0.68rem', color: '#f43f5e', marginTop: '3px', fontWeight: 600 }}>
                🛡️ Do-Not-Contact: {data.excluded_companies.join(', ')}
              </div>
            )}
          </div>

          <div className="glass-panel" style={{ padding: '0.85rem 1rem' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Scraper Engine Status
            </div>
            <div style={{ fontSize: '1.05rem', fontWeight: 700, color: data?.is_running ? '#3b82f6' : '#10b981', marginTop: '4px', display: 'flex', alignItems: 'center', gap: 6 }}>
              <Terminal size={16} />
              {data?.is_running ? 'Executing Jobs…' : 'Idle & Ready'}
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              {data?.last_run ? `Last run: ${data.last_run}` : 'Hourly background task'}
            </div>
          </div>
        </div>

        {/* Quick Link to Settings */}
        {onNavigateToSettings && (
          <div style={{ marginTop: '1rem', display: 'flex', justifyContent: 'flex-end' }}>
            <button
              type="button"
              className="theme-pill-btn neutral"
              onClick={onNavigateToSettings}
              style={{ fontSize: '0.76rem', padding: '4px 10px' }}
            >
              <Sliders size={12} /> Configure Default Keywords, City & Outreach Rules in Settings
            </button>
          </div>
        )}
      </div>

      {/* Execution Logs Table */}
      <div className="theme-table-container">
        <div className="theme-table-controls" style={{ flexWrap: 'wrap', gap: 10 }}>
          <span style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--text-primary)' }}>
            Recent Automated Scraper Executions & Outreach Logs
          </span>
          <span className="jp-hint">
            {data?.total_runs
              ? `Latest ${runs.length} scraper results · ${data.total_runs.toLocaleString()} runs so far · ${Number(data.total_added || 0).toLocaleString()} leads added`
              : 'No runs recorded yet'}
          </span>
          <div style={{ flex: 1 }} />
          {onNavigateToLeads && (
            <button
              type="button"
              className="theme-pill-btn neutral"
              onClick={onNavigateToLeads}
            >
              <Database size={13} /> View Master Leads Database
            </button>
          )}
        </div>

        <div className="theme-table-scroll">
          <table className="jp-table">
            <thead>
              <tr>
                <th>Run ID / Time</th>
                <th>Scraper Engine</th>
                <th>Status</th>
                <th>Harvested</th>
                <th>New Added</th>
                <th>Updated</th>
                <th>Duplicates</th>
                <th>Notes / Error</th>
              </tr>
            </thead>
            <tbody>
              {runs.length === 0 ? (
                <tr>
                  <td colSpan={8} className="jp-empty">
                    {loading ? 'Loading execution logs…' : 'No execution logs recorded yet. Click "Run 1-Hour Cycle Now" to start the first run.'}
                  </td>
                </tr>
              ) : (
                runs.map((r, i) => (
                  <tr key={i}>
                    <td style={{ whiteSpace: 'nowrap' }}>
                      <div style={{ fontWeight: 600, fontSize: '0.82rem' }}>{r.run_id}</div>
                      <div className="jp-hint" style={{ fontSize: '0.7rem' }}>{r.start_time}</div>
                    </td>
                    <td>
                      <span style={{ fontWeight: 600 }}>{r.scraper_name}</span>
                    </td>
                    <td>
                      <span className={`jp-status-chip ${r.status === 'Success' ? 'ok' : 'error'}`}>
                        {r.status}
                      </span>
                    </td>
                    <td style={{ fontWeight: 600 }}>{r.records || '0'}</td>
                    <td>
                      <span style={{ color: Number(r.added) > 0 ? '#10b981' : 'inherit', fontWeight: Number(r.added) > 0 ? 700 : 400 }}>
                        {r.added || '0'}
                      </span>
                    </td>
                    <td>{r.updated || '0'}</td>
                    <td className="jp-hint">{r.duplicates || '0'}</td>
                    <td className="se-wrap" style={{ fontSize: '0.75rem', color: r.error_summary ? '#ef4444' : 'var(--text-muted)' }}>
                      {r.error_summary || 'Normal execution'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

