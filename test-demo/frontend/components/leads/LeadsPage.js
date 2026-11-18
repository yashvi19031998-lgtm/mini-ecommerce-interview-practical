'use client';

// Leads: the one place to find and work leads. Filters on top (next step, Hot/Warm/Cold, source,
// date found, outcome, contact type, search), then a table or a board. Click a lead to open its panel.
// The filters live in the URL (#/leads?action=call_pending&band=hot), so a view can be bookmarked or shared.
// Data: the annotated list from GET /api/leads (next_action, band, last_contact come from lead_status.py).

import React, { useEffect, useMemo, useState } from 'react';
import {
  Search, X, LayoutList, Columns3, Download, Mail, Phone, ExternalLink, ChevronLeft, ChevronRight,
  SlidersHorizontal, Ban
} from 'lucide-react';
import {
  ACTIONS, TODO_ACTIONS, BANDS, OUTCOMES, OUTCOME_LABEL, leadName, leadAbout, leadEmail,
  leadPhone, postUrl, leadScore, leadOutcome, leadSource, foundDate, niceDate
} from '../../lib/leadMeta';

export const DEFAULT_FILTERS = { q: '', action: '', band: '', source: '', found: '', outcome: '', contact: '', sort: 'score', view: 'table', group: 'action' };

const FOUND = [
  { id: '', label: 'Any time' }, { id: 'today', label: 'Today' }, { id: '7d', label: 'Last 7 days' },
  { id: '30d', label: 'Last 30 days' }, { id: 'month', label: 'This month' },
];
const CONTACT = [
  { id: '', label: 'Any contact' }, { id: 'email', label: 'Has e-mail' }, { id: 'phone', label: 'Has phone' },
  { id: 'post', label: 'Post link only' }, { id: 'none', label: 'No contact' },
];
const SORTS = [
  { id: 'score', label: 'Best score first' }, { id: 'newest', label: 'Newest first' }, { id: 'contact', label: 'Last contacted first' },
];
const PAGE = 50;
const SKIPPED = ['old_post', 'no_contact', 'not_fit', 'closed'];

const pad = (n) => String(n).padStart(2, '0');
const isoDay = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

function foundFrom(id) {
  const d = new Date();
  if (id === 'today') return isoDay(d);
  if (id === '7d') { d.setDate(d.getDate() - 6); return isoDay(d); }
  if (id === '30d') { d.setDate(d.getDate() - 29); return isoDay(d); }
  if (id === 'month') return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-01`;
  return '';
}

function matches(l, f, q) {
  if (f.action === 'todo' ? !TODO_ACTIONS.includes(l.next_action) : f.action === 'skipped' ? !SKIPPED.includes(l.next_action) : (f.action && l.next_action !== f.action)) return false;
  if (f.band && l.band !== f.band) return false;
  if (f.source && leadSource(l) !== f.source) return false;
  if (f.outcome && leadOutcome(l) !== f.outcome) return false;
  if (f.found) {
    const from = foundFrom(f.found);
    if (!foundDate(l) || foundDate(l) < from) return false;
  }
  if (f.contact) {
    const em = !!leadEmail(l), ph = !!leadPhone(l), po = !!postUrl(l);
    if (f.contact === 'email' && !em) return false;
    if (f.contact === 'phone' && !ph) return false;
    if (f.contact === 'post' && (em || ph || !po)) return false;
    if (f.contact === 'none' && (em || ph || po)) return false;
  }
  if (q) {
    const hay = `${leadName(l)} ${l.full_name || ''} ${leadEmail(l)} ${leadPhone(l)} ${leadAbout(l)} ${l.ai_tech_stack || ''} ${l.location || ''} ${leadSource(l)}`.toLowerCase();
    if (!hay.includes(q)) return false;
  }
  return true;
}

function sortLeads(list, sort) {
  const by = {
    score: (a, b) => (leadScore(b) ?? -1) - (leadScore(a) ?? -1) || String(b.first_seen_at).localeCompare(String(a.first_seen_at)),
    newest: (a, b) => String(b.first_seen_at).localeCompare(String(a.first_seen_at)),
    contact: (a, b) => String(b.last_contact || '').localeCompare(String(a.last_contact || '')),
  }[sort] || (() => 0);
  return [...list].sort(by);
}

function csvCell(v) {
  const s = String(v ?? '');
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function exportCsv(rows) {
  const head = ['Lead ID', 'Lead', 'Person', 'Score', 'Band', 'Next step', 'Outcome', 'E-mail', 'Phone', 'Post', 'Website', 'Source', 'Found', 'Last contact', 'About'];
  const lines = rows.map(l => [l.id, leadName(l), l.full_name, leadScore(l) ?? '', BANDS[l.band]?.label, ACTIONS[l.next_action]?.label,
    OUTCOME_LABEL[leadOutcome(l)], leadEmail(l), leadPhone(l), postUrl(l), l.website, leadSource(l), foundDate(l), l.last_contact, leadAbout(l)].map(csvCell).join(','));
  const blob = new Blob([`﻿${[head.join(','), ...lines].join('\n')}`], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `leads_${isoDay(new Date())}.csv`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

function ActionPill({ id }) {
  const a = ACTIONS[id];
  if (!a) return <span className="pill tone-gray">–</span>;
  return <span className={`pill tone-${a.tone}`}>{a.label}</span>;
}

function ScoreChip({ lead }) {
  const s = leadScore(lead);
  if (s === null) return <span className="score s-none" title="Not scored">–</span>;
  return <span className={`score s-${lead.band}`} title={`${BANDS[lead.band]?.label} lead`}>{s}</span>;
}

function ContactIcons({ lead }) {
  const em = leadEmail(lead), ph = leadPhone(lead), po = postUrl(lead);
  return (
    <span className="ct-icons" aria-label="Contact details">
      <Mail size={14} className={em ? 'on' : ''} aria-label={em ? 'Has e-mail' : 'No e-mail'} />
      <Phone size={14} className={ph ? 'on' : ''} aria-label={ph ? 'Has phone' : 'No phone'} />
      <ExternalLink size={14} className={po ? 'on' : ''} aria-label={po ? 'Has post link' : 'No post link'} />
    </span>
  );
}

export default function LeadsPage({ leads = [], filters, onFiltersChange, onOpenLead, onBulkEmail, onStatusChange, loading = false }) {
  const f = { ...DEFAULT_FILTERS, ...(filters || {}) };
  const [qInput, setQInput] = useState(f.q);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(new Set());
  const [showMore, setShowMore] = useState(() => !!(f.source || f.found || f.outcome || f.contact));
  const [dragId, setDragId] = useState(null);

  const set = (patch) => { onFiltersChange({ ...f, ...patch }); setPage(1); setSelected(new Set()); };

  useEffect(() => { setQInput(f.q); }, [f.q]);
  useEffect(() => {
    const t = setTimeout(() => { if (qInput.trim() !== f.q) set({ q: qInput.trim() }); }, 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qInput]);

  const sources = useMemo(() => {
    const c = {};
    leads.forEach(l => { const s = leadSource(l); c[s] = (c[s] || 0) + 1; });
    return Object.entries(c).sort((a, b) => b[1] - a[1]);
  }, [leads]);

  // Counts per next step honour every other filter, so the chips say what clicking them will show
  const q = f.q.toLowerCase();
  const base = useMemo(() => leads.filter(l => matches(l, { ...f, action: '' }, q)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [leads, f.band, f.source, f.found, f.outcome, f.contact, q]);
  const counts = useMemo(() => {
    const c = {};
    base.forEach(l => { c[l.next_action] = (c[l.next_action] || 0) + 1; });
    return c;
  }, [base]);
  const todoCount = TODO_ACTIONS.reduce((n, a) => n + (counts[a] || 0), 0);
  const skippedCount = SKIPPED.reduce((n, a) => n + (counts[a] || 0), 0);

  const rows = useMemo(() => sortLeads(base.filter(l => matches(l, { action: f.action }, '')), f.sort), [base, f.action, f.sort]);
  const pages = Math.max(1, Math.ceil(rows.length / PAGE));
  const pageRows = rows.slice((page - 1) * PAGE, page * PAGE);

  const activeExtra = ['band', 'source', 'found', 'outcome', 'contact'].filter(k => f[k]).length + (f.q ? 1 : 0);
  const clearAll = () => { setQInput(''); onFiltersChange({ ...DEFAULT_FILTERS, view: f.view, group: f.group, sort: f.sort }); setPage(1); };

  const toggle = (id) => setSelected(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const allOnPage = pageRows.length > 0 && pageRows.every(l => selected.has(l.id));
  const togglePage = () => setSelected(prev => {
    const n = new Set(prev);
    if (allOnPage) pageRows.forEach(l => n.delete(l.id)); else pageRows.forEach(l => n.add(l.id));
    return n;
  });

  const chip = (id, label, count) => (
    <button key={id || 'all'} type="button" className={`fchip ${f.action === id ? 'on' : ''} ${id && ACTIONS[id] ? `tone-${ACTIONS[id].tone}` : ''}`}
      onClick={() => set({ action: id })} aria-pressed={f.action === id}>
      {label}<span className="fchip-n">{(count ?? 0).toLocaleString()}</span>
    </button>
  );

  // Board columns
  const boardCols = f.group === 'outcome'
    ? OUTCOMES.filter(o => o !== 'DISQUALIFIED').map(o => ({ id: o, label: OUTCOME_LABEL[o], items: rows.filter(l => leadOutcome(l) === o) }))
    : [...TODO_ACTIONS, 'mail_pending', 'waiting'].map(a => ({ id: a, label: ACTIONS[a].label, tone: ACTIONS[a].tone, items: rows.filter(l => l.next_action === a) }));

  return (
    <div className="lv">
      <header className="lv-head">
        <div>
          <h1 className="lv-title">Leads</h1>
          <p className="lv-sub">{rows.length.toLocaleString()} of {leads.length.toLocaleString()} leads{loading ? ' · updating…' : ''}</p>
        </div>
        <div className="lv-head-actions">
          <div className="seg-group" role="group" aria-label="View">
            <button type="button" className={`seg ${f.view === 'table' ? 'on' : ''}`} onClick={() => set({ view: 'table' })} aria-pressed={f.view === 'table'}><LayoutList size={15} /> Table</button>
            <button type="button" className={`seg ${f.view === 'board' ? 'on' : ''}`} onClick={() => set({ view: 'board' })} aria-pressed={f.view === 'board'}><Columns3 size={15} /> Board</button>
          </div>
          <button type="button" className="btn btn-ghost" onClick={() => exportCsv(selected.size ? rows.filter(l => selected.has(l.id)) : rows)} disabled={!rows.length}>
            <Download size={15} /> Export {selected.size ? `${selected.size} selected` : 'list'}
          </button>
        </div>
      </header>

      {/* Filters */}
      <div className="lv-filters">
        <div className="lv-search-row">
          <label className="lv-search">
            <Search size={16} />
            <input value={qInput} onChange={e => setQInput(e.target.value)} placeholder="Search by name, e-mail, phone, need or city" aria-label="Search leads" />
            {qInput && <button type="button" onClick={() => setQInput('')} aria-label="Clear search"><X size={14} /></button>}
          </label>
          <div className="band-group" role="group" aria-label="Lead temperature">
            {['', 'hot', 'warm', 'cold'].map(b => (
              <button key={b || 'all'} type="button" className={`band-btn ${b ? `b-${b}` : ''} ${f.band === b ? 'on' : ''}`} onClick={() => set({ band: b })} aria-pressed={f.band === b}>
                {b ? BANDS[b].label : 'All'}
                {b && <small>{BANDS[b].range}</small>}
              </button>
            ))}
          </div>
          <button type="button" className={`btn btn-ghost ${showMore ? 'on' : ''}`} onClick={() => setShowMore(v => !v)} aria-expanded={showMore}>
            <SlidersHorizontal size={15} /> More filters{['source', 'found', 'outcome', 'contact'].filter(k => f[k]).length ? ` (${['source', 'found', 'outcome', 'contact'].filter(k => f[k]).length})` : ''}
          </button>
        </div>

        {showMore && (
          <div className="lv-more">
            <label className="fsel"><span>Source</span>
              <select value={f.source} onChange={e => set({ source: e.target.value })}>
                <option value="">All sources</option>
                {sources.map(([s, n]) => <option key={s} value={s}>{s} ({n})</option>)}
              </select>
            </label>
            <label className="fsel"><span>Found</span>
              <select value={f.found} onChange={e => set({ found: e.target.value })}>
                {FOUND.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
              </select>
            </label>
            <label className="fsel"><span>Outcome</span>
              <select value={f.outcome} onChange={e => set({ outcome: e.target.value })}>
                <option value="">Any outcome</option>
                {OUTCOMES.map(o => <option key={o} value={o}>{OUTCOME_LABEL[o]}</option>)}
              </select>
            </label>
            <label className="fsel"><span>Contact</span>
              <select value={f.contact} onChange={e => set({ contact: e.target.value })}>
                {CONTACT.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
              </select>
            </label>
            <label className="fsel"><span>Sort</span>
              <select value={f.sort} onChange={e => set({ sort: e.target.value })}>
                {SORTS.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
              </select>
            </label>
          </div>
        )}

        <div className="lv-chips" role="group" aria-label="Next step">
          {chip('', 'All', base.length)}
          {chip('todo', 'Your to-do', todoCount)}
          <span className="lv-chip-sep" aria-hidden="true" />
          {TODO_ACTIONS.map(a => chip(a, ACTIONS[a].label, counts[a]))}
          <span className="lv-chip-sep" aria-hidden="true" />
          {chip('mail_pending', ACTIONS.mail_pending.label, counts.mail_pending)}
          {chip('waiting', ACTIONS.waiting.label, counts.waiting)}
          {chip('skipped', 'Skipped', skippedCount)}
        </div>

        {activeExtra > 0 && (
          <div className="lv-active">
            {f.q && <span className="tag">“{f.q}” <button type="button" onClick={() => { setQInput(''); set({ q: '' }); }} aria-label="Remove search"><X size={12} /></button></span>}
            {f.band && <span className="tag">{BANDS[f.band].label} <button type="button" onClick={() => set({ band: '' })} aria-label="Remove temperature filter"><X size={12} /></button></span>}
            {f.source && <span className="tag">{f.source} <button type="button" onClick={() => set({ source: '' })} aria-label="Remove source filter"><X size={12} /></button></span>}
            {f.found && <span className="tag">Found: {FOUND.find(o => o.id === f.found)?.label} <button type="button" onClick={() => set({ found: '' })} aria-label="Remove date filter"><X size={12} /></button></span>}
            {f.outcome && <span className="tag">{OUTCOME_LABEL[f.outcome]} <button type="button" onClick={() => set({ outcome: '' })} aria-label="Remove outcome filter"><X size={12} /></button></span>}
            {f.contact && <span className="tag">{CONTACT.find(o => o.id === f.contact)?.label} <button type="button" onClick={() => set({ contact: '' })} aria-label="Remove contact filter"><X size={12} /></button></span>}
            <button type="button" className="lv-clear" onClick={clearAll}>Clear all</button>
          </div>
        )}
      </div>

      {/* Bulk bar */}
      {selected.size > 0 && (
        <div className="lv-bulk" role="region" aria-label="Selected leads">
          <strong>{selected.size} selected</strong>
          {onBulkEmail && <button type="button" className="btn btn-primary sm" onClick={() => onBulkEmail([...selected])}><Mail size={14} /> Send mail</button>}
          {onStatusChange && <button type="button" className="btn btn-ghost sm" onClick={() => { [...selected].forEach(id => onStatusChange(id, 'LOST')); setSelected(new Set()); }}><Ban size={14} /> Not interested</button>}
          <button type="button" className="btn btn-ghost sm" onClick={() => setSelected(new Set())}>Clear selection</button>
        </div>
      )}

      {rows.length === 0 ? (
        <div className="lv-empty">
          <p><strong>No leads match these filters.</strong></p>
          <p>{f.action && TODO_ACTIONS.includes(f.action) ? 'Nothing waiting in this step.' : 'Try fewer filters.'}</p>
          {(activeExtra > 0 || f.action) && <button type="button" className="btn btn-ghost" onClick={clearAll}>Show all leads</button>}
        </div>
      ) : f.view === 'board' ? (
        <>
          <div className="lv-board-bar">
            <span>Group by</span>
            <div className="seg-group" role="group" aria-label="Group board by">
              <button type="button" className={`seg ${f.group === 'action' ? 'on' : ''}`} onClick={() => set({ group: 'action' })}>Next step</button>
              <button type="button" className={`seg ${f.group === 'outcome' ? 'on' : ''}`} onClick={() => set({ group: 'outcome' })}>Outcome</button>
            </div>
            {f.group === 'outcome' && <span className="lv-hint">Drag a card to change its outcome.</span>}
          </div>
          <div className="lv-board">
            {boardCols.map(col => (
              <section key={col.id} className={`bcol ${col.tone ? `tone-${col.tone}` : ''} ${dragId ? 'droppable' : ''}`}
                onDragOver={f.group === 'outcome' ? (e) => e.preventDefault() : undefined}
                onDrop={f.group === 'outcome' ? (e) => { e.preventDefault(); if (dragId) onStatusChange?.(dragId, col.id); setDragId(null); } : undefined}>
                <header className="bcol-head"><span>{col.label}</span><span className="bcol-n">{col.items.length.toLocaleString()}</span></header>
                <div className="bcol-list">
                  {col.items.slice(0, 40).map(l => (
                    <button key={l.id} type="button" className="bcard" onClick={() => onOpenLead(l.id)}
                      draggable={f.group === 'outcome'} onDragStart={() => setDragId(l.id)} onDragEnd={() => setDragId(null)}>
                      <span className="bcard-top"><ScoreChip lead={l} /><span className="bcard-name">{leadName(l)}</span></span>
                      {leadAbout(l) && <span className="bcard-about">{leadAbout(l)}</span>}
                      <span className="bcard-meta">{leadSource(l)} · {niceDate(l.first_seen_at)}<ContactIcons lead={l} /></span>
                    </button>
                  ))}
                  {col.items.length > 40 && (
                    <button type="button" className="bcol-more" onClick={() => set(f.group === 'outcome' ? { outcome: col.id, view: 'table' } : { action: col.id, view: 'table' })}>
                      {(col.items.length - 40).toLocaleString()} more – open as table
                    </button>
                  )}
                  {col.items.length === 0 && <p className="bcol-empty">None</p>}
                </div>
              </section>
            ))}
          </div>
        </>
      ) : (
        <>
          <div className="lv-table-wrap">
            <table className="lv-table">
              <thead>
                <tr>
                  <th className="c-check"><input type="checkbox" checked={allOnPage} onChange={togglePage} aria-label="Select all on this page" /></th>
                  <th>Lead</th>
                  <th className="c-score">Score</th>
                  <th>Next step</th>
                  <th className="c-contact">Contact</th>
                  <th className="c-source">Source</th>
                  <th className="c-date">Found</th>
                  <th className="c-date">Last contact</th>
                  <th className="c-outcome">Outcome</th>
                </tr>
              </thead>
              <tbody>
                {pageRows.map(l => (
                  <tr key={l.id} onClick={() => onOpenLead(l.id)} className={selected.has(l.id) ? 'is-selected' : ''}>
                    <td className="c-check" onClick={e => e.stopPropagation()}>
                      <input type="checkbox" checked={selected.has(l.id)} onChange={() => toggle(l.id)} aria-label={`Select ${leadName(l)}`} />
                    </td>
                    <td className="c-lead">
                      <button type="button" className="lv-lead-btn" onClick={(e) => { e.stopPropagation(); onOpenLead(l.id); }}>{leadName(l)}</button>
                      {leadAbout(l) && <span className="lv-lead-about">{leadAbout(l)}</span>}
                      <span className="lv-mobile-step"><ActionPill id={l.next_action} /></span>
                    </td>
                    <td className="c-score"><ScoreChip lead={l} /></td>
                    <td><ActionPill id={l.next_action} /></td>
                    <td className="c-contact"><ContactIcons lead={l} /></td>
                    <td className="c-source">{leadSource(l)}</td>
                    <td className="c-date">{niceDate(l.first_seen_at)}</td>
                    <td className="c-date">{l.last_contact ? niceDate(l.last_contact) : <span className="muted">Never</span>}</td>
                    <td className="c-outcome">{OUTCOME_LABEL[leadOutcome(l)]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <nav className="lv-pager" aria-label="Pages">
            <span>{((page - 1) * PAGE + 1).toLocaleString()}–{Math.min(page * PAGE, rows.length).toLocaleString()} of {rows.length.toLocaleString()}</span>
            <button type="button" className="icon-btn" disabled={page <= 1} onClick={() => setPage(p => p - 1)} aria-label="Previous page"><ChevronLeft size={16} /></button>
            <span>Page {page} of {pages}</span>
            <button type="button" className="icon-btn" disabled={page >= pages} onClick={() => setPage(p => p + 1)} aria-label="Next page"><ChevronRight size={16} /></button>
          </nav>
        </>
      )}
    </div>
  );
}

