'use client';

// Data Extraction -> Indian Directories: one page per portal (MLMDiary, IndiaMART, Justdial, Sulekha, TradeIndia,
// ExportersIndia). The menu passes sourceId; everything else is shared.
// Backend: indian_directories.py via /api/indian-directories/*; Deep Search via /api/search-engine/deep.

import React, { useEffect, useMemo, useState } from 'react';
import {
  Network, Factory, Phone, Wrench, Store, Ship, Search, Loader2, X, ExternalLink, Save, Download,
  AlertTriangle, ScanSearch, Ban
} from 'lucide-react';
import { fetchIndianDirectorySources, searchIndianDirectories, saveIndianDirectoryResults, runDeepSearch } from '../lib/api';
import CacheNote from './CacheNote';
import MiningForm from './MiningForm';

const META = {
  mlmdiary: { icon: Network, title: 'MLMDiary Scraper',
    sub: 'MLM and direct selling companies directory by location.',
    kwLabel: 'MLM company name', kwHint: '(optional — leave empty for all companies)', kwPlaceholder: 'e.g. Vestige, Zenvex',
    suggestions: [] },
  indiamart: { icon: Factory, title: 'IndiaMART Scraper',
    sub: 'Suppliers and manufacturers directory across Indian cities.',
    kwLabel: 'Product / category', kwPlaceholder: 'e.g. bakery products, packaging material',
    suggestions: ['bakery products', 'packaging material', 'industrial machinery', 'led lights', 'solar panel', 'office furniture'] },
  justdial: { icon: Phone, title: 'Justdial Scraper', sub: 'Local business listings and service providers.' },
  sulekha: { icon: Wrench, title: 'Sulekha Scraper',
    sub: 'Service providers and local professionals across Indian cities.',
    kwLabel: 'Service / category', kwPlaceholder: 'e.g. interior designers decorators, packers and movers',
    suggestions: ['interior designers decorators', 'packers and movers'] },
  tradeindia: { icon: Store, title: 'TradeIndia Scraper',
    sub: 'Manufacturers, exporters, and wholesale suppliers directory.',
    kwLabel: 'Product / category', kwPlaceholder: 'e.g. bakery products',
    suggestions: ['bakery products', 'packaging material', 'industrial machinery'] },
  exportersindia: { icon: Ship, title: 'ExportersIndia Scraper',
    sub: 'B2B exporters, manufacturers, and industrial suppliers.',
    kwLabel: 'Product / category', kwPlaceholder: 'e.g. bakery products',
    suggestions: ['bakery products', 'packaging material'] }
};
const ALTERNATIVES = ['sulekha', 'indiamart'];
const DEEP_LABELS = { found: 'Found', partial: 'Website only', none: 'Nothing found', error: 'Failed' };
const rowKey = (r) => `${r.source_id}|${r.url}|${r.company}`;

function downloadCsv(rows, sourceId) {
  const cols = ['company', 'source', 'product', 'category', 'location', 'phone', 'phone_ext', 'phone_note', 'email', 'website',
    'rating', 'verified', 'since', 'url', 'in_leads', 'details'];
  const cell = (v) => {
    let s = String(v ?? '');
    if (/^[=+\-@]/.test(s)) s = `'${s}`;
    return `"${s.replace(/"/g, '""')}"`;
  };
  const csv = [cols.join(','), ...rows.map(r => cols.map(c => cell(r[c])).join(','))].join('\n');
  const url = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = `${sourceId}_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default function IndianDirectory({ sourceId, onLeadsSaved, onOpenSource }) {
  const meta = META[sourceId] || { icon: Store, title: sourceId, sub: '' };
  const Icon = meta.icon;
  const [opts, setOpts] = useState(null);
  const [optsError, setOptsError] = useState('');
  const [keywords, setKeywords] = useState([]);
  const [audience, setAudience] = useState([]);
  const [state, setState] = useState('All India');
  const [city, setCity] = useState('');
  const [errors, setErrors] = useState({});
  const [searching, setSearching] = useState(false);
  const [result, setResult] = useState(null);
  const [notice, setNotice] = useState(null);
  const [picked, setPicked] = useState(new Set());
  const [filter, setFilter] = useState('');
  const [deep, setDeep] = useState({});
  const [deepRun, setDeepRun] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchIndianDirectorySources()
      .then(setOpts)
      .catch(err => setOptsError(err.message || 'Could not load sources. Is the Python backend running?'));
  }, []);

  const source = (opts?.sources || []).find(s => s.id === sourceId);
  const needsKeyword = source ? source.needsKeyword !== false : true;
  const needsCity = !!source?.needsCity;
  const clear = (f) => setErrors(prev => (prev[f] ? { ...prev, [f]: '' } : prev));
  const place = city.trim() || (state && state !== 'All India' ? state : '');

  const submit = async (e, final = null, refresh = false) => {
    e?.preventDefault();
    const kws = final?.keywords || keywords;
    const aud = final?.audience || audience;
    const errs = {};
    if (needsKeyword && !kws.length) errs.keywords = 'Enter at least one product or category';
    if (needsCity && !city.trim()) errs.city = `${source?.name || 'This site'} lists businesses per city — enter a city`;
    if (city && !/^[A-Za-z .'-]{1,60}$/.test(city.trim())) errs.city = 'City must be letters only (max 60 characters)';
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setSearching(true); setResult(null); setPicked(new Set()); setDeep({}); setFilter(''); setNotice(null);
    try {
      const res = await searchIndianDirectories({ keywords: kws, audience: aud, state, city: city.trim(), sources: [sourceId], refresh });
      setResult(res);
      const st = Object.values(res.sources || {});
      if (!res.total && st.length && st.every(x => x.status !== 'ok')) {
        setNotice({ type: 'error', text: 'Nothing found — see the reason below.' });
        return;
      }
      setNotice({ type: res.total ? 'success' : 'info',
        text: `Found ${res.total} listing${res.total === 1 ? '' : 's'}${res.cache?.hit ? ' (saved results)' : ''}` });
    } catch (err) {
      setNotice({ type: 'error', text: err.message || 'Search failed' });
    } finally {
      setSearching(false);
    }
  };

  const rows = useMemo(() => (result?.results || []).map(r => {
    const d = deep[rowKey(r)];
    if (!d) return r;
    return { ...r, email: r.email || (d.emails || []).join(', '), phone: r.phone || (d.phones || [])[0] || '',
      website: r.website || d.website || '', email_guess: d.email_guess || '', deep_status: d.status, deep_steps: d.steps || [] };
  }), [result, deep]);
  const visible = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return rows.filter(r => !q || `${r.company} ${r.product} ${r.location} ${r.details}`.toLowerCase().includes(q));
  }, [rows, filter]);
  const allVisiblePicked = visible.length > 0 && visible.every(r => picked.has(rowKey(r)));
  const togglePick = (k) => { const n = new Set(picked); if (n.has(k)) n.delete(k); else n.add(k); setPicked(n); };
  const togglePickAll = () => {
    const n = new Set(picked);
    if (allVisiblePicked) visible.forEach(r => n.delete(rowKey(r))); else visible.forEach(r => n.add(rowKey(r)));
    setPicked(n);
  };
  const deepTargets = useMemo(() => (picked.size ? rows.filter(r => picked.has(rowKey(r))) : rows.filter(r => !r.email && !deep[rowKey(r)])),
    [rows, picked, deep]);

  // Deep Search looks for the company's own website by name (the directory page is never treated as the website)
  const runDeep = async () => {
    const batch = opts?.deepBatch || 10;
    const targets = deepTargets;
    if (!targets.length) return;
    setDeepRun({ done: 0, total: targets.length }); setNotice(null);
    let found = 0, failed = false;
    for (let i = 0; i < targets.length; i += batch) {
      const chunk = targets.slice(i, i + batch);
      try {
        const res = await runDeepSearch({ items: chunk.map(r => ({ key: rowKey(r), url: r.url, website: r.website || '', company: r.company, kind: 'listing' })), engine: 'auto', place });
        const add = {};
        (res.results || []).forEach(d => { add[d.key] = d; if (d.status === 'found') found += 1; });
        setDeep(prev => ({ ...prev, ...add }));
      } catch (err) {
        failed = true;
        setNotice({ type: 'error', text: `Deep Search stopped: ${err.message}` });
        break;
      }
      setDeepRun({ done: Math.min(i + batch, targets.length), total: targets.length });
    }
    setDeepRun(null);
    if (!failed) setNotice({ type: 'success', text: `Deep Search finished: contact details found for ${found} of ${targets.length}` });
  };

  const save = async () => {
    const chosen = rows.filter(r => picked.has(rowKey(r)));
    if (!chosen.length) return;
    setSaving(true);
    try {
      const res = await saveIndianDirectoryResults(chosen);
      const parts = [`${res.added} new lead${res.added === 1 ? '' : 's'}`];
      if (res.updated) parts.push(`${res.updated} updated`);
      if (res.duplicate) parts.push(`${res.duplicate} already saved`);
      if (res.skipped_invalid) parts.push(`${res.skipped_invalid} skipped`);
      setNotice({ type: 'success', text: `Saved to Leads: ${parts.join(', ')}` });
      setResult(prev => prev && ({ ...prev, results: prev.results.map(r => (picked.has(rowKey(r)) ? { ...r, in_leads: true } : r)) }));
      setPicked(new Set());
      onLeadsSaved && onLeadsSaved();
    } catch (err) {
      setNotice({ type: 'error', text: `Could not save: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const busy = searching || !!deepRun;
  const isMlm = sourceId === 'mlmdiary';

  const header = (
    <div className="theme-panel-header" style={{ marginBottom: '1rem' }}>
      <div>
        <div className="theme-panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Icon size={18} /> {meta.title}</div>
        <div className="theme-panel-sub">{meta.sub}</div>
      </div>
    </div>
  );

  if (source && source.status !== 'available') {
    return (
      <div className="theme-card-panel" style={{ marginBottom: 0 }}>
        {header}
        <div className="jp-alert jp-alert-error" role="note"><Ban size={14} /><span><strong>Not available.</strong> {source.reason}</span></div>
        <p className="theme-panel-sub" style={{ marginTop: '0.75rem' }}>Similar local business data, collected the allowed way:</p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {ALTERNATIVES.map(id => (
            <button key={id} type="button" className="theme-pill-btn neutral" onClick={() => onOpenSource && onOpenSource(id)}>
              {React.createElement(META[id].icon, { size: 13 })} {META[id].title}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className="theme-card-panel" style={{ marginBottom: 0 }}>
        {header}
        {optsError && <div role="alert" className="jp-alert jp-alert-error"><AlertTriangle size={14} /> {optsError}</div>}
        <MiningForm
          idPrefix={`dx-${sourceId}`} onSubmit={submit} busy={searching} disabled={!!deepRun || !!optsError || !opts}
          busyHint="Searching directories..."
          keywords={{ label: meta.kwLabel || 'Product / category', hint: meta.kwHint || `(Enter or comma, up to ${opts?.maxKeywords || 5})`,
            values: keywords, setValues: setKeywords, max: opts?.maxKeywords || 5, error: errors.keywords,
            onClear: () => clear('keywords'), placeholder: meta.kwPlaceholder, suggestions: meta.suggestions }}
          audience={{ values: audience, setValues: setAudience, max: 5 }}
          location={{ mode: 'india', state, setState, states: opts?.states || [], stateRequired: false,
            city, setCity, cityError: errors.city, onClear: clear, cityHint: needsCity ? '(required)' : '(optional — city pages give local results)' }}
        />
      </div>

      {notice && (
        <div role="status" className={`jp-alert ${notice.type === 'error' ? 'jp-alert-error' : notice.type === 'info' ? 'se-alert-info' : 'jp-alert-success'}`}>
          {notice.type === 'error' && <AlertTriangle size={14} />}<span style={{ flex: 1 }}>{notice.text}</span>
          <button type="button" className="jp-alert-close" aria-label="Dismiss message" onClick={() => setNotice(null)}><X size={14} /></button>
        </div>
      )}
      {result && <CacheNote cache={result.cache} busy={busy} onRefresh={() => submit(null, null, true)} />}
      {result && Object.values(result.sources || {}).flatMap(st => st.errors || []).length > 0 && (
        <ul className="se-errors">{Object.values(result.sources || {}).flatMap(st => st.errors || []).map((er, i) => <li key={i}>{er}</li>)}</ul>
      )}

      {result && (
        <div className="theme-table-container">
          <div className="theme-table-controls" style={{ flexWrap: 'wrap', gap: 10 }}>
            <div className="theme-control-search">
              <Search size={14} color="#a3a7ae" />
              <input type="text" placeholder="Filter results…" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter results" />
            </div>
            <span className="jp-hint">{visible.length} of {rows.length} · {picked.size} selected</span>
            <div style={{ flex: 1 }} />
            <button type="button" className="theme-pill-btn neutral" onClick={runDeep} disabled={busy || !deepTargets.length}
              title="Looks for each company's own website by name, then reads it for email / phone">
              {deepRun ? <Loader2 size={13} className="animate-spin" /> : <ScanSearch size={13} />}
              {deepRun ? ` Deep Search ${deepRun.done}/${deepRun.total}…` : ` Deep Search ${picked.size ? 'selected' : 'missing'} (${deepTargets.length})`}
            </button>
            <button type="button" className="theme-pill-btn neutral" onClick={() => downloadCsv(visible, sourceId)} disabled={!visible.length}><Download size={13} /> Export CSV</button>
            <button type="button" className="theme-pill-btn primary" onClick={save} disabled={!picked.size || saving || busy}>
              {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />} Save to Leads{picked.size ? ` (${picked.size})` : ''}
            </button>
          </div>
          <div className="theme-table-scroll">
            <table className="jp-table">
              <thead>
                <tr>
                  <th style={{ width: 36 }}><input type="checkbox" aria-label="Select all visible results" checked={allVisiblePicked} onChange={togglePickAll} disabled={!visible.length} /></th>
                  <th>{isMlm ? 'MLM company' : 'Business'}</th><th>{isMlm ? 'Plans' : 'Product'}</th><th>Location</th><th>Phone</th><th>Email</th><th>Website</th><th>{isMlm ? 'Members' : 'Info'}</th><th>Status</th><th style={{ width: 40 }} aria-label="Open" />
                </tr>
              </thead>
              <tbody>
                {visible.length === 0 ? (
                  <tr><td colSpan={10} className="jp-empty">{rows.length ? 'No results match this filter.' : 'No listings found. Try the category name the site uses, or another city.'}</td></tr>
                ) : visible.map(r => {
                  const k = rowKey(r);
                  const info = isMlm ? String(r.members || '') : [r.rating, r.verified, r.since && `${r.since} on site`].filter(Boolean).join(' · ');
                  return (
                    <tr key={k} className={picked.has(k) ? 'selected' : ''}>
                      <td><input type="checkbox" aria-label={`Select ${r.company}`} checked={picked.has(k)} onChange={() => togglePick(k)} /></td>
                      <td>
                        <div className="jp-cell-title">{r.company}</div>
                        <div className="jp-cell-sub se-snippet" title={r.details}>{r.details}</div>
                      </td>
                      <td className="se-wrap">{r.product || r.category || '—'}</td>
                      <td>{r.location || '—'}</td>
                      <td style={{ whiteSpace: 'nowrap' }}>
                        {r.phone ? <span title={r.phone_note || ''}>{r.phone}{r.phone_ext ? ` ext ${r.phone_ext}` : ''}{r.phone_note ? ' *' : ''}</span>
                          : <span className="jp-hint" title={r.phone_note || ''}>{r.phone_note ? 'Hidden' : '—'}</span>}
                      </td>
                      <td className="se-wrap">{r.email || (r.email_guess ? <span className="se-guess" title="Guessed - not found on the website. Not saved as the email.">{r.email_guess} (guess)</span> : '—')}</td>
                      <td className="se-wrap">{r.website ? <a href={r.website} target="_blank" rel="noopener noreferrer">{r.website.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '')}</a> : '—'}</td>
                      <td className="se-wrap">{info || '—'}</td>
                      <td>
                        {r.in_leads && <span className="se-badge inleads" title={r.match ? `Matches ${r.match}` : ''}>In leads</span>}
                        {r.deep_status && <span className={`se-badge deep-${r.deep_status}`} title={(r.deep_steps || []).join(' | ')}>{DEEP_LABELS[r.deep_status] || r.deep_status}</span>}
                        {!r.in_leads && !r.deep_status && <span className="jp-hint">New</span>}
                      </td>
                      <td><a href={r.url} target="_blank" rel="noopener noreferrer" aria-label={`Open ${r.company} on ${r.source}`}><ExternalLink size={14} /></a></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {rows.some(r => r.phone_note && r.phone) && <div className="jp-hint" style={{ padding: '6px 12px' }}>* Number from the directory (e.g. an IndiaMART call-forwarding number) — hover it for details.</div>}
        </div>
      )}
    </div>
  );
}

