'use client';

// Scraping / Mining -> WhatsApp Groups: public group invite links for a topic (group name + link only).
// Members / phone numbers are never collected. Backend: whatsapp_sources.py via /api/whatsapp/*.

import React, { useEffect, useMemo, useState } from 'react';
import { MessageCircle, Search, Loader2, X, ExternalLink, Save, Download, AlertTriangle, ShieldCheck } from 'lucide-react';
import { fetchWhatsAppSources, searchWhatsApp, saveWhatsAppResults } from '../lib/api';
import CacheNote from './CacheNote';
import MiningForm from './MiningForm';

const GROUPS = [
  { status: 'available', label: 'Available' },
  { status: 'unavailable', label: 'Not available' }
];
const rowKey = (r) => r.invite_code;

function downloadCsv(rows) {
  const cols = ['group_name', 'url', 'category', 'location', 'found_on', 'details', 'in_leads', 'source'];
  const cell = (v) => {
    let s = String(v ?? '');
    if (/^[=+\-@]/.test(s)) s = `'${s}`;
    return `"${s.replace(/"/g, '""')}"`;
  };
  const csv = [cols.join(','), ...rows.map(r => cols.map(c => cell(r[c])).join(','))].join('\n');
  const url = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = `whatsapp_groups_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default function WhatsAppGroups({ onLeadsSaved }) {
  const [opts, setOpts] = useState(null);
  const [optsError, setOptsError] = useState('');
  const [keywords, setKeywords] = useState([]);
  const [audience, setAudience] = useState([]);
  const [state, setState] = useState('All India');
  const [city, setCity] = useState('');
  const [selected, setSelected] = useState(new Set());
  const [engine, setEngine] = useState('auto');
  const [errors, setErrors] = useState({});
  const [searching, setSearching] = useState(false);
  const [result, setResult] = useState(null);
  const [notice, setNotice] = useState(null);
  const [picked, setPicked] = useState(new Set());
  const [filter, setFilter] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchWhatsAppSources()
      .then(res => { setOpts(res); setSelected(new Set((res.sources || []).filter(s => s.status === 'available').map(s => s.id))); })
      .catch(err => setOptsError(err.message || 'Could not load sources. Is the Python backend running?'));
  }, []);

  const clear = (f) => setErrors(prev => (prev[f] ? { ...prev, [f]: '' } : prev));

  const submit = async (e, final = null, refresh = false) => {
    e?.preventDefault();
    const kws = final?.keywords || keywords;
    const aud = final?.audience || audience;
    const errs = {};
    if (!kws.length) errs.keywords = 'Enter at least one topic';
    if (city && !/^[A-Za-z .'-]{1,60}$/.test(city.trim())) errs.city = 'City must be letters only (max 60 characters)';
    if (!selected.size) errs.sources = 'Select at least one source';
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setSearching(true); setResult(null); setPicked(new Set()); setFilter(''); setNotice(null);
    try {
      const res = await searchWhatsApp({ keywords: kws, audience: aud, state, city: city.trim(), sources: [...selected], engine, refresh });
      setResult(res);
      const st = Object.values(res.sources || {});
      if (!res.total && st.length && st.every(x => x.status !== 'ok')) {
        setNotice({ type: 'error', text: 'No source returned results - see the reasons below.' });
        return;
      }
      setNotice({ type: res.total ? 'success' : 'info',
        text: `Found ${res.total} group link${res.total === 1 ? '' : 's'}${res.cache?.hit ? ' (saved results)' : ''}` });
    } catch (err) {
      setNotice({ type: 'error', text: err.message || 'Search failed' });
    } finally {
      setSearching(false);
    }
  };

  const rows = result?.results || [];
  const visible = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return q ? rows.filter(r => `${r.group_name} ${r.category} ${r.details}`.toLowerCase().includes(q)) : rows;
  }, [rows, filter]);
  const allVisiblePicked = visible.length > 0 && visible.every(r => picked.has(rowKey(r)));
  const togglePick = (k) => { const n = new Set(picked); if (n.has(k)) n.delete(k); else n.add(k); setPicked(n); };
  const togglePickAll = () => {
    const n = new Set(picked);
    if (allVisiblePicked) visible.forEach(r => n.delete(rowKey(r))); else visible.forEach(r => n.add(rowKey(r)));
    setPicked(n);
  };

  const save = async () => {
    const chosen = rows.filter(r => picked.has(rowKey(r)));
    if (!chosen.length) return;
    setSaving(true);
    try {
      const res = await saveWhatsAppResults(chosen);
      const parts = [`${res.added} new`];
      if (res.updated) parts.push(`${res.updated} updated`);
      if (res.duplicate) parts.push(`${res.duplicate} already saved`);
      setNotice({ type: 'success', text: `Saved to Leads (as communities): ${parts.join(', ')}` });
      setResult(prev => prev && ({ ...prev, results: prev.results.map(r => (picked.has(rowKey(r)) ? { ...r, in_leads: true } : r)) }));
      setPicked(new Set());
      onLeadsSaved && onLeadsSaved();
    } catch (err) {
      setNotice({ type: 'error', text: `Could not save: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const engines = opts?.engines || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className="theme-card-panel" style={{ marginBottom: 0 }}>
        <div className="theme-panel-header" style={{ marginBottom: '1rem' }}>
          <div>
            <div className="theme-panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}><MessageCircle size={18} /> WhatsApp Groups</div>
            <div className="theme-panel-sub">Public group invite links for a topic — join communities where your clients are. Group name and link only.</div>
          </div>
        </div>
        <div className="jp-alert se-alert-info" role="note" style={{ marginBottom: '0.75rem' }}>
          <ShieldCheck size={14} />
          <span>Member phone numbers are never collected: that needs joining groups with automation (WhatsApp bans the number) and personal numbers are protected by India's DPDP Act 2023.</span>
        </div>
        {optsError && <div role="alert" className="jp-alert jp-alert-error"><AlertTriangle size={14} /> {optsError}</div>}
        <MiningForm
          idPrefix="wa" onSubmit={submit} busy={searching} disabled={!!optsError || !opts}
          busyHint="Searching — can take up to a minute."
          keywords={{ label: 'Topics', hint: `(Enter or comma, up to ${opts?.maxKeywords || 5})`,
            values: keywords, setValues: setKeywords, max: opts?.maxKeywords || 5, error: errors.keywords,
            onClear: () => clear('keywords'), placeholder: 'e.g. real estate, startup, freelancers, wholesale' }}
          audience={{ values: audience, setValues: setAudience, max: 5 }}
          extra={(
            <div className="form-group jp-span-2">
              <label className="form-label" htmlFor="wa-engine">Search engine</label>
              <select id="wa-engine" className="theme-form-input" value={engine} onChange={(e) => setEngine(e.target.value)}>
                {engines.map(en => (
                  <option key={en.id} value={en.id} disabled={en.status !== 'available'}>
                    {en.name}{en.status === 'needs_key' ? ' — add key in Settings' : ''}
                  </option>
                ))}
              </select>
              <div className="jp-hint" style={{ marginTop: 4 }}>{engines.find(en => en.id === engine)?.note}</div>
            </div>
          )}
          location={{ mode: 'india', state, setState, states: opts?.states || ['All India'], stateRequired: false,
            city, setCity, cityError: errors.city, onClear: clear }}
          sources={{ label: 'Sources', items: opts?.sources || [], selected, setSelected, error: errors.sources,
            onClear: () => clear('sources'), placeholder: 'Select sources', allLabel: 'All available sources', groups: GROUPS }}
        />
      </div>

      {notice && (
        <div role="status" className={`jp-alert ${notice.type === 'error' ? 'jp-alert-error' : notice.type === 'info' ? 'se-alert-info' : 'jp-alert-success'}`}>
          {notice.type === 'error' && <AlertTriangle size={14} />}<span style={{ flex: 1 }}>{notice.text}</span>
          <button type="button" className="jp-alert-close" aria-label="Dismiss message" onClick={() => setNotice(null)}><X size={14} /></button>
        </div>
      )}
      {result && <CacheNote cache={result.cache} busy={searching} onRefresh={() => submit(null, null, true)} />}
      {result?.hint && <div className="jp-alert se-alert-warn" role="note"><AlertTriangle size={14} /><span>{result.hint}</span></div>}

      {result && (
        <div className="jp-status-row" aria-label="Source results">
          {Object.entries(result.sources || {}).map(([id, st]) => (
            <span key={id} className={`jp-status-chip ${st.status === 'ok' && st.count === 0 ? 'empty' : st.status}`}
              title={(st.errors || []).join(' | ') || `${st.count} results in ${st.seconds}s`}>
              {st.name}: {st.status === 'error' ? 'failed' : st.count}
            </span>
          ))}
          {Object.values(result.sources || {}).flatMap(st => st.errors || []).length > 0 && (
            <ul className="se-errors">{Object.values(result.sources || {}).flatMap(st => st.errors || []).map((er, i) => <li key={i}>{er}</li>)}</ul>
          )}
        </div>
      )}

      {result && (
        <div className="theme-table-container">
          <div className="theme-table-controls" style={{ flexWrap: 'wrap', gap: 10 }}>
            <div className="theme-control-search">
              <Search size={14} color="#a3a7ae" />
              <input type="text" placeholder="Filter groups…" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter results" />
            </div>
            <span className="jp-hint">{visible.length} of {rows.length} · {picked.size} selected</span>
            <div style={{ flex: 1 }} />
            <button type="button" className="theme-pill-btn neutral" onClick={() => downloadCsv(visible)} disabled={!visible.length}><Download size={13} /> Export CSV</button>
            <button type="button" className="theme-pill-btn primary" onClick={save} disabled={!picked.size || saving || searching}>
              {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />} Save to Leads{picked.size ? ` (${picked.size})` : ''}
            </button>
          </div>
          <div className="theme-table-scroll">
            <table className="jp-table">
              <thead>
                <tr>
                  <th style={{ width: 36 }}><input type="checkbox" aria-label="Select all visible results" checked={allVisiblePicked} onChange={togglePickAll} disabled={!visible.length} /></th>
                  <th>Group</th><th>Topic</th><th>Invite link</th><th>Found on</th><th>Status</th>
                </tr>
              </thead>
              <tbody>
                {visible.length === 0 ? (
                  <tr><td colSpan={6} className="jp-empty">{rows.length ? 'No groups match this filter.' : 'No group links found. Try another topic, or add a search engine key in Settings.'}</td></tr>
                ) : visible.map(r => {
                  const k = rowKey(r);
                  return (
                    <tr key={k} className={picked.has(k) ? 'selected' : ''}>
                      <td><input type="checkbox" aria-label={`Select ${r.company}`} checked={picked.has(k)} onChange={() => togglePick(k)} /></td>
                      <td>
                        <div className="jp-cell-title">{r.company}<span className="se-kind">{r.source}</span></div>
                        {r.details && <div className="jp-cell-sub se-snippet" title={r.details}>{r.details}</div>}
                      </td>
                      <td>{[r.category, r.location].filter(Boolean).join(' · ') || '—'}</td>
                      <td className="se-wrap"><a href={r.url} target="_blank" rel="noopener noreferrer">Join <ExternalLink size={12} style={{ verticalAlign: '-1px' }} /></a></td>
                      <td className="se-wrap">{r.found_on ? <a href={r.found_on} target="_blank" rel="noopener noreferrer">{r.found_on.replace(/^https?:\/\/(www\.)?/, '').split('/')[0]}</a> : 'Search result'}</td>
                      <td>{r.in_leads ? <span className="se-badge inleads">In leads</span> : <span className="jp-hint">New</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
