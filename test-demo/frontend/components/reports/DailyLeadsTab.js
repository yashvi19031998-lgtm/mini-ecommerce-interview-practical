'use client';

// Daily Leads & Mail: one row per day - leads found that day, how many got an e-mail, how many are
// still pending, no e-mail, blocked - for the report's period / source / stage filters plus a score band.
// Click a number to see those leads. Backend: daily_leads_report.py via /api/reports/daily-leads[/list].

import React, { useEffect, useState } from 'react';
import { CalendarDays, Download, Loader2, X } from 'lucide-react';
import { fetchReportDailyLeads, fetchReportDailyLeadsList } from '../../lib/api';
import { exportToCsv, formatNum } from './reportUtils';

const BANDS = [
  { id: 'all', label: 'All scores' },
  { id: 'high', label: 'High (7-10)' },
  { id: 'medium', label: 'Medium (4-6)' },
  { id: 'low', label: 'Low (0-3)' },
  { id: 'unscored', label: 'Not scored' },
];

const COLS = [
  { key: 'found', label: 'Leads found', state: 'found' },
  { key: 'mailed', label: 'Mail sent', state: 'mailed', color: 'var(--success-green)' },
  { key: 'pending', label: 'Pending', state: 'pending', color: 'var(--warning-amber)' },
  { key: 'no_email', label: 'No e-mail', state: 'no_email' },
  { key: 'blocked', label: 'Invalid / blocked', state: 'blocked', color: 'var(--danger-red, #dc2626)' },
];

const MAIL_LABEL = { mailed: 'Mail sent', pending: 'Pending', no_email: 'No e-mail', blocked: 'Invalid / blocked' };

function niceDay(day) {
  const d = new Date(`${day}T00:00:00`);
  return Number.isNaN(d.getTime()) ? day : d.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
}

// Daily score bands -> the Leads page's temperature
const BAND_TO_TEMP = { high: 'hot', medium: 'warm', low: 'cold', unscored: '' };

export default function DailyLeadsTab({ filters, reloadKey = 0, onNotice = () => {}, onOpenLeads = null }) {
  const [band, setBand] = useState(() => {
    try { return localStorage.getItem('reports_daily_band') || 'all'; } catch { return 'all'; }
  });
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [hideEmpty, setHideEmpty] = useState(true);
  const [detail, setDetail] = useState(null); // { day, state, label, items, total, loading }

  useEffect(() => {
    setLoading(true);
    fetchReportDailyLeads(filters, band)
      .then(setData)
      .catch(err => onNotice('error', err.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, band, reloadKey]);

  const pickBand = (id) => {
    setBand(id);
    setDetail(null);
    try { localStorage.setItem('reports_daily_band', id); } catch { /* private mode */ }
  };

  const open = async (day, col) => {
    setDetail({ day, state: col.state, label: col.label, items: [], total: 0, loading: true });
    try {
      const res = await fetchReportDailyLeadsList(filters, { day, state: col.state, band });
      setDetail({ day, state: col.state, label: col.label, items: res.items || [], total: res.total || 0, loading: false });
    } catch (err) {
      setDetail(null);
      onNotice('error', err.message);
    }
  };

  const rows = (data?.rows || []).filter(r => !hideEmpty || r.found || r.mails_sent_that_day);
  const t = data?.totals;

  const handleExport = () => {
    exportToCsv(`daily_leads_${band}.csv`,
      ['Date', 'Leads found', 'Mail sent', 'Pending', 'No e-mail', 'Invalid / blocked', 'High', 'Medium', 'Low', 'Not scored', 'All mails sent that day'],
      rows.map(r => [r.day, r.found, r.mailed, r.pending, r.no_email, r.blocked, r.high, r.medium, r.low, r.unscored, r.mails_sent_that_day]));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className="rp-chip-group" style={{ flexWrap: 'wrap' }}>
        {BANDS.map(b => (
          <button key={b.id} type="button" className={`rp-chip ${band === b.id ? 'active' : ''}`} onClick={() => pickBand(b.id)}>
            {b.label}
          </button>
        ))}
      </div>

      {t && (
        <div className="rp-kpi-grid">
          {COLS.map(c => (
            <div key={c.key} className="rp-kpi-card">
              <div className="rp-kpi-title">{c.label}</div>
              <div className="rp-kpi-val" style={c.color ? { color: c.color } : undefined}>{formatNum(t[c.key])}</div>
              <div className="rp-kpi-sub">
                {c.key === 'found' ? 'in the selected period' : t.found ? `${Math.round((t[c.key] / t.found) * 100)}% of leads found` : '—'}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="rp-table-card">
        <div className="rp-table-top">
          <div className="rp-table-title"><CalendarDays size={16} color="var(--primary-blue)" /> Day by day</div>
          <div className="rp-table-actions" style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <label className="jp-hint" style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
              <input type="checkbox" checked={hideEmpty} onChange={e => setHideEmpty(e.target.checked)} /> Hide days with nothing
            </label>
            <button type="button" className="theme-pill-btn neutral" onClick={handleExport} disabled={!rows.length}>
              <Download size={13} /> Export CSV
            </button>
          </div>
        </div>
        <div className="jp-hint" style={{ padding: '0 1.25rem 0.5rem' }}>
          A lead counts on the day it was found. &quot;Pending&quot; = has an e-mail address but no mail went out yet.
          &quot;All mails&quot; = every e-mail the app sent that day, for leads found on any day. Click a number to see the leads.
        </div>
        <div className="theme-table-scroll">
          <table className="jp-table">
            <thead>
              <tr>
                <th>Date</th>
                {COLS.map(c => <th key={c.key} style={{ textAlign: 'right' }}>{c.label}</th>)}
                <th style={{ textAlign: 'right' }}>High / Med / Low / –</th>
                <th style={{ textAlign: 'right' }}>All mails sent that day</th>
              </tr>
            </thead>
            <tbody>
              {loading && !data ? (
                <tr><td colSpan={8} className="jp-empty"><Loader2 size={14} className="animate-spin" /> Loading…</td></tr>
              ) : rows.length === 0 ? (
                <tr><td colSpan={8} className="jp-empty">No leads in this period for this score group.</td></tr>
              ) : rows.map(r => (
                <tr key={r.day} style={detail?.day === r.day ? { background: 'var(--primary-blue-subtle)' } : undefined}>
                  <td style={{ whiteSpace: 'nowrap' }}>{niceDay(r.day)}</td>
                  {COLS.map(c => (
                    <td key={c.key} style={{ textAlign: 'right' }}>
                      {r[c.key] ? (
                        <button type="button" className="fu-link" style={c.color ? { color: c.color } : undefined}
                          onClick={() => open(r.day, c)} title={`Show the ${c.label.toLowerCase()} leads of ${r.day}`}>
                          {formatNum(r[c.key])}
                        </button>
                      ) : <span className="jp-hint">0</span>}
                    </td>
                  ))}
                  <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }} className="jp-cell-sub">
                    {r.high} / {r.medium} / {r.low} / {r.unscored}
                  </td>
                  <td style={{ textAlign: 'right' }}>{formatNum(r.mails_sent_that_day)}</td>
                </tr>
              ))}
            </tbody>
            {t && rows.length > 0 && (
              <tfoot>
                <tr style={{ fontWeight: 700 }}>
                  <td>Total</td>
                  {COLS.map(c => <td key={c.key} style={{ textAlign: 'right' }}>{formatNum(t[c.key])}</td>)}
                  <td style={{ textAlign: 'right' }}>{t.high} / {t.medium} / {t.low} / {t.unscored}</td>
                  <td style={{ textAlign: 'right' }}>{formatNum(t.mails_sent_that_day)}</td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </div>

      {detail && (
        <div className="rp-table-card">
          <div className="rp-table-top">
            <div className="rp-table-title">
              {detail.label} - {niceDay(detail.day)} {detail.loading ? '' : `(${formatNum(detail.total)})`}
            </div>
            <div className="rp-table-actions">
              {onOpenLeads && (
                <button type="button" className="theme-pill-btn" title="Open these leads on the Leads page to call, WhatsApp or mail them in bulk"
                  onClick={() => onOpenLeads({ found: detail.day, pending: detail.state === 'pending' ? 'email' : '', band: BAND_TO_TEMP[band] || '' })}>
                  Open in Leads
                </button>
              )}
              <button type="button" className="theme-pill-btn neutral" onClick={() => setDetail(null)} aria-label="Close list">
                <X size={13} /> Close
              </button>
            </div>
          </div>
          <div className="theme-table-scroll">
            <table className="jp-table">
              <thead>
                <tr><th style={{ width: 64 }}>Score</th><th>Lead</th><th>E-mail</th><th>Mail</th><th>Found</th></tr>
              </thead>
              <tbody>
                {detail.loading ? (
                  <tr><td colSpan={5} className="jp-empty"><Loader2 size={14} className="animate-spin" /> Loading…</td></tr>
                ) : detail.items.length === 0 ? (
                  <tr><td colSpan={5} className="jp-empty">No leads.</td></tr>
                ) : detail.items.map(i => (
                  <tr key={i.id}>
                    <td><span className={`fu-score b-${i.band}`}>{i.score ?? '—'}</span></td>
                    <td>
                      <div style={{ overflowWrap: 'anywhere' }}>{i.name || i.id}</div>
                      <div className="jp-cell-sub">{i.source}</div>
                    </td>
                    <td style={{ overflowWrap: 'anywhere' }}>{i.email || <span className="jp-hint">—</span>}</td>
                    <td>{MAIL_LABEL[i.mail]}{i.sent_at ? <div className="jp-cell-sub">{i.sent_at}</div> : null}</td>
                    <td className="jp-cell-sub" style={{ whiteSpace: 'nowrap' }}>{i.found_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {detail.total > detail.items.length && (
            <div className="jp-hint" style={{ padding: '0.5rem 1.25rem' }}>Showing {detail.items.length} of {detail.total}.</div>
          )}
        </div>
      )}
    </div>
  );
}
