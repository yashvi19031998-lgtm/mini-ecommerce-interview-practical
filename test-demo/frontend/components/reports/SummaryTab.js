'use client';

// Reports > Summary: the report to show a client. Filters (period, client type, temperature, source) in one
// row; then what happened in plain sentences (with an "Ask AI" analysis), the funnel, the work done, leads
// found vs contacted per day, and the split by client type and by source. Print / save as PDF from the
// browser. Backend: report_summary.py via /api/reports/overview[/insight].

import React, { useEffect, useMemo, useState } from 'react';
import { Download, Loader2, Printer, Sparkles, ArrowRight } from 'lucide-react';
import { apiFetchReportOverview, apiFetchReportInsight } from '../../lib/api';
import { ACTIONS } from '../../lib/leadMeta';

const PRESETS = [
  { id: 'today', label: 'Today' }, { id: '7d', label: '7 days' }, { id: '30d', label: '30 days' },
  { id: '90d', label: '90 days' }, { id: 'month', label: 'This month' }, { id: 'last_month', label: 'Last month' },
  { id: 'all', label: 'All time' }, { id: 'custom', label: 'Custom' },
];
const BANDS = [{ id: '', label: 'All' }, { id: 'hot', label: 'Hot' }, { id: 'warm', label: 'Warm' }, { id: 'cold', label: 'Cold' }];
const WORK = [
  { key: 'mails', label: 'Mails sent' }, { key: 'calls', label: 'Calls' }, { key: 'whatsapps', label: 'WhatsApps' },
  { key: 'post_replies', label: 'Post replies' }, { key: 'replies_received', label: 'Replies received' },
];
const SERIES = { found: '#2a78d6', contacted: '#eb6834' };
const fmt = (n) => Number(n || 0).toLocaleString();

function readSaved() {
  try { return JSON.parse(localStorage.getItem('report_summary_filters') || 'null') || null; } catch { return null; }
}

function DayChart({ rows }) {
  const [hover, setHover] = useState(null);
  const max = Math.max(1, ...rows.map(r => Math.max(r.found, r.contacted)));
  if (!rows.length) return <p className="sm-empty">Pick 120 days or fewer to see the daily chart.</p>;
  const tickEvery = Math.ceil(rows.length / 8);
  return (
    <div className="sm-chart" onMouseLeave={() => setHover(null)}>
      <div className="sm-legend" aria-hidden="true">
        <span><i style={{ background: SERIES.found }} /> Leads found</span>
        <span><i style={{ background: SERIES.contacted }} /> Leads contacted</span>
      </div>
      <div className="sm-plot" role="img" aria-label={`Leads found and contacted per day, ${rows[0].day} to ${rows[rows.length - 1].day}`}>
        <div className="sm-ymax">{fmt(max)}</div>
        {rows.map((r, i) => (
          <div key={r.day} className={`sm-col ${hover === i ? 'on' : ''}`} onMouseEnter={() => setHover(i)} onFocus={() => setHover(i)} tabIndex={0}
            aria-label={`${r.day}: ${r.found} found, ${r.contacted} contacted`}>
            <div className="sm-bars">
              <span style={{ height: `${(r.found / max) * 100}%`, background: SERIES.found }} />
              <span style={{ height: `${(r.contacted / max) * 100}%`, background: SERIES.contacted }} />
            </div>
            <div className="sm-x">{i % tickEvery === 0 ? new Date(`${r.day}T00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short' }) : ''}</div>
            {hover === i && (
              <div className={`sm-tip ${i > rows.length * 0.7 ? 'left' : ''}`}>
                <strong>{new Date(`${r.day}T00:00`).toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })}</strong>
                <span><i style={{ background: SERIES.found }} /> {fmt(r.found)} found</span>
                <span><i style={{ background: SERIES.contacted }} /> {fmt(r.contacted)} contacted</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function GroupTable({ title, rows, onPick }) {
  if (!rows?.length) return null;
  return (
    <section className="sm-card">
      <h3 className="sm-h">{title}</h3>
      <div className="sm-table-wrap">
        <table className="sm-table">
          <thead><tr><th>{title.replace('By ', '')}</th><th>Found</th><th>Hot</th><th>Contacted</th><th>Replied</th><th>Reply rate</th></tr></thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.name}>
                <td>{onPick ? <button type="button" className="sm-link" onClick={() => onPick(r)}>{r.name}</button> : r.name}</td>
                <td>{fmt(r.found)}</td>
                <td>{fmt(r.hot)} <small>{r.hot_pct}%</small></td>
                <td>{fmt(r.contacted)} <small>{r.contacted_pct}%</small></td>
                <td>{fmt(r.replied)}</td>
                <td>{r.contacted ? `${r.reply_rate}%` : '–'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function SummaryTab({ onOpenLeads, onNotice = () => {} }) {
  const [f, setF] = useState(() => readSaved() || { preset: '30d', date_from: '', date_to: '', client_type: '', band: '', source: '' });
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [ai, setAi] = useState(null);
  const [aiBusy, setAiBusy] = useState(false);

  const query = useMemo(() => ({ ...f, preset: f.preset === 'custom' ? '' : f.preset }), [f]);

  useEffect(() => {
    if (f.preset === 'custom' && !f.date_from) return;
    try { localStorage.setItem('report_summary_filters', JSON.stringify(f)); } catch { /* private mode */ }
    setLoading(true);
    setAi(null);
    apiFetchReportOverview(query)
      .then(setData)
      .catch(err => onNotice('error', err.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  const set = (patch) => setF(prev => ({ ...prev, ...patch }));

  const askAi = async () => {
    setAiBusy(true);
    try {
      setAi(await apiFetchReportInsight(query));
    } catch (err) {
      onNotice('error', err.message);
    } finally {
      setAiBusy(false);
    }
  };

  const exportCsv = () => {
    if (!data) return;
    const lines = [['Section', 'Name', 'Found', 'Hot', 'Contacted', 'Replied', 'Reply rate %']];
    data.by_client_type.forEach(r => lines.push(['Client type', r.name, r.found, r.hot, r.contacted, r.replied, r.reply_rate]));
    data.by_source.forEach(r => lines.push(['Source', r.name, r.found, r.hot, r.contacted, r.replied, r.reply_rate]));
    data.funnel.forEach(r => lines.push(['Funnel', r.label, r.count, '', '', '', `${r.pct}`]));
    data.by_day.forEach(r => lines.push(['Day', r.day, r.found, '', r.contacted, '', '']));
    const csv = lines.map(l => l.map(v => (/[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : v)).join(',')).join('\n');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([`﻿${csv}`], { type: 'text/csv;charset=utf-8' }));
    a.download = `lead_report_${data.period.from}_${data.period.to}.csv`;
    a.click();
  };

  const funnelMax = data?.funnel?.[0]?.count || 1;
  const periodText = data ? `${new Date(`${data.period.from}T00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })} – ${new Date(`${data.period.to}T00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })}` : '';

  return (
    <div className="sm-root">
      {/* Filters */}
      <div className="sm-filters" role="group" aria-label="Report filters">
        <div className="seg-group sm-presets">
          {PRESETS.map(p => (
            <button key={p.id} type="button" className={`seg ${f.preset === p.id ? 'on' : ''}`} onClick={() => set({ preset: p.id })} aria-pressed={f.preset === p.id}>{p.label}</button>
          ))}
        </div>
        {f.preset === 'custom' && (
          <div className="sm-dates">
            <label className="fsel"><span>From</span><input type="date" value={f.date_from} onChange={e => set({ date_from: e.target.value })} /></label>
            <label className="fsel"><span>To</span><input type="date" value={f.date_to} onChange={e => set({ date_to: e.target.value })} /></label>
          </div>
        )}
        <div className="sm-filter-row">
          <label className="fsel"><span>Client type</span>
            <select value={f.client_type} onChange={e => set({ client_type: e.target.value })}>
              <option value="">All client types</option>
              {(data?.options?.client_types || []).map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
            </select>
          </label>
          <label className="fsel"><span>Temperature</span>
            <select value={f.band} onChange={e => set({ band: e.target.value })}>
              {BANDS.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
            </select>
          </label>
          <label className="fsel"><span>Source</span>
            <select value={f.source} onChange={e => set({ source: e.target.value })}>
              <option value="">All sources</option>
              {(data?.options?.sources || []).map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <div className="sm-actions">
            <button type="button" className="btn btn-ghost sm" onClick={exportCsv} disabled={!data}><Download size={14} /> CSV</button>
            <button type="button" className="btn btn-ghost sm" onClick={() => window.print()} disabled={!data}><Printer size={14} /> Print / PDF</button>
          </div>
        </div>
      </div>

      {!data ? (
        <div className="td-loading"><Loader2 size={16} className="animate-spin" /> Loading the report…</div>
      ) : (
        <div className={`sm-body ${loading ? 'is-loading' : ''}`}>
          <p className="sm-period">Leads found {periodText}{data.filters.client_type || data.filters.band || data.filters.source ? ' · filtered' : ''}</p>

          {/* What happened */}
          <section className="sm-card sm-story">
            <div className="sm-story-head">
              <h3 className="sm-h">What happened</h3>
              <button type="button" className="btn btn-soft sm" onClick={askAi} disabled={aiBusy}>
                {aiBusy ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />} {ai ? 'Ask AI again' : 'Ask AI for advice'}
              </button>
            </div>
            <ul className="sm-points">{data.highlights.map(h => <li key={h}>{h}</li>)}</ul>
            {ai && ai.by === 'ai' && (
              <div className="sm-ai">
                <div className="sm-ai-label">AI analysis</div>
                {ai.text.split('\n').filter(Boolean).map((line, i) => <p key={i}>{line.replace(/^[-*•]\s*/, '')}</p>)}
              </div>
            )}
            {ai && ai.by !== 'ai' && (
              <p className="sm-ai-off">AI advice needs an AI key (GEMINI_API_KEY is free) in the backend .env file. The findings above work without it.</p>
            )}
          </section>

          <div className="sm-grid">
            {/* Funnel */}
            <section className="sm-card">
              <h3 className="sm-h">From lead to client</h3>
              <ol className="sm-funnel">
                {data.funnel.map(s => (
                  <li key={s.key}>
                    <div className="sm-funnel-top"><span>{s.label}</span><strong>{fmt(s.count)}</strong><small>{s.key === 'found' ? '' : `${s.pct}%`}</small></div>
                    <div className="sm-funnel-bar"><span style={{ width: `${Math.max(s.count ? 1.5 : 0, (s.count / funnelMax) * 100)}%` }} /></div>
                  </li>
                ))}
              </ol>
            </section>

            {/* Work done */}
            <section className="sm-card">
              <h3 className="sm-h">Work done in this period</h3>
              <dl className="sm-work">
                {WORK.map(w => <div key={w.key}><dt>{w.label}</dt><dd>{fmt(data.work[w.key])}</dd></div>)}
              </dl>
              {data.todo > 0 && onOpenLeads && (
                <button type="button" className="td-lane-all" onClick={() => onOpenLeads({ action: 'todo' })}>
                  {fmt(data.todo)} of these leads are on the to-do list <ArrowRight size={14} />
                </button>
              )}
            </section>
          </div>

          <section className="sm-card">
            <h3 className="sm-h">Leads found and contacted per day</h3>
            <DayChart rows={data.by_day} />
          </section>

          <GroupTable title="By client type" rows={data.by_client_type} />
          <GroupTable title="By source" rows={data.by_source} onPick={onOpenLeads ? (r) => onOpenLeads({ source: r.name }) : null} />

          {data.next_steps.length > 0 && (
            <section className="sm-card">
              <h3 className="sm-h">Where these leads are now</h3>
              <div className="sm-steps">
                {data.next_steps.map(s => (
                  <button key={s.id} type="button" className="sm-step" onClick={() => onOpenLeads && onOpenLeads({ action: s.id })}>
                    <strong>{fmt(s.count)}</strong><span>{ACTIONS[s.id]?.label || s.label}</span>
                  </button>
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
