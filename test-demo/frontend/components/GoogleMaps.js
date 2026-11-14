'use client';

// Scraping / Mining -> Google Maps: local businesses (OpenStreetMap + Google Places API).
// "Without website" finds businesses that have no website = direct leads for a website offer.
// Backend: maps_sources.py via /api/maps/*; Deep Search via /api/search-engine/deep.

import React, { useEffect, useMemo, useState } from 'react';
import { MapPin, Search, Loader2, X, ExternalLink, Save, Download, AlertTriangle, ScanSearch, Star } from 'lucide-react';
import { fetchMapsSources, searchMaps, saveMapsResults, runDeepSearch } from '../lib/api';
import CacheNote from './CacheNote';
import MiningForm from './MiningForm';

const GROUPS = [
  { status: 'available', label: 'Available' },
  { status: 'needs_key', label: 'Needs API key' },
  { status: 'unavailable', label: 'Not available' }
];
const DEEP_LABELS = { found: 'Found', partial: 'Website only', none: 'Nothing found', error: 'Failed' };
const SOCIAL_SHORT = { linkedin: 'in', instagram: 'ig', facebook: 'fb', twitter: 'x', youtube: 'yt', whatsapp: 'wa' };
const rowKey = (r) => r.url || `${r.company}|${r.phone}`;

function downloadCsv(rows) {
  const cols = ['company', 'phone', 'email', 'website', 'no_website', 'rating', 'reviews', 'category', 'location', 'socials', 'in_leads', 'source', 'url'];
  const cell = (v) => {
    let s = typeof v === 'object' && v !== null ? Object.entries(v).map(([k, x]) => `${k}: ${x}`).join(' | ') : String(v ?? '');
    if (/^[=+\-@]/.test(s)) s = `'${s}`;
    return `"${s.replace(/"/g, '""')}"`;
  };
  const csv = [cols.join(','), ...rows.map(r => cols.map(c => cell(r[c])).join(','))].join('\n');
  const url = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = `google_maps_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default function GoogleMaps({ onLeadsSaved }) {
  const [opts, setOpts] = useState(null);
  const [optsError, setOptsError] = useState('');

  const [keywords, setKeywords] = useState([]);
  const [audience, setAudience] = useState([]);
  const [state, setState] = useState('');
  const [city, setCity] = useState('');
  const [selected, setSelected] = useState(new Set());
  const [website, setWebsite] = useState('any');
  const [minRating, setMinRating] = useState(0);
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
    fetchMapsSources()
      .then(res => { setOpts(res); setSelected(new Set((res.sources || []).filter(s => s.status === 'available').map(s => s.id))); })
      .catch(err => setOptsError(err.message || 'Could not load sources. Is the Python backend running?'));
  }, []);

  const clear = (f) => setErrors(prev => (prev[f] ? { ...prev, [f]: '' } : prev));
  const place = city.trim() || (state && state !== 'All India' ? state : '');

  const submit = async (e, final = null, refresh = false) => {
    e?.preventDefault();
    const kws = final?.keywords || keywords;
    const aud = final?.audience || audience;
    const errs = {};
    if (!kws.length) errs.keywords = 'Enter at least one business category or keyword';
    if (!state) errs.state = 'Select a state';
    if (city && !/^[A-Za-z .'-]{1,60}$/.test(city.trim())) errs.city = 'City must be letters only (max 60 characters)';
    if (!selected.size) errs.sources = 'Select at least one source';
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setSearching(true);
    setResult(null);
    setPicked(new Set());
    setDeep({});
    setFilter('');
    setNotice(null);
    try {
      const res = await searchMaps({ keywords: kws, audience: aud, state, city: city.trim(), sources: [...selected],
        min_rating: minRating, website, refresh });
      setResult(res);
      const hidden = (res.hidden?.website || 0) + (res.hidden?.rating || 0);
      const st = Object.values(res.sources || {});
      if (!res.total && st.length && st.every(x => x.status === 'error')) {
        setNotice({ type: 'error', text: 'No source answered this time - see the reason below and try again in a few minutes.' });
        return;
      }
      setNotice({ type: res.total ? 'success' : 'info',
        text: `Found ${res.total} business${res.total === 1 ? '' : 'es'}${hidden ? ` (${hidden} hidden by your filters)` : ''}${res.cache?.hit ? ' (saved results)' : ''}` });
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
      website: r.website || d.website || '', socials: d.socials || {}, email_guess: d.email_guess || '',
      deep_status: d.status, deep_steps: d.steps || [] };
  }), [result, deep]);
  const visible = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return q ? rows.filter(r => `${r.company} ${r.category} ${r.location} ${r.phone}`.toLowerCase().includes(q)) : rows;
  }, [rows, filter]);
  const allVisiblePicked = visible.length > 0 && visible.every(r => picked.has(rowKey(r)));
  const togglePick = (k) => { const n = new Set(picked); if (n.has(k)) n.delete(k); else n.add(k); setPicked(n); };
  const togglePickAll = () => {
    const n = new Set(picked);
    if (allVisiblePicked) visible.forEach(r => n.delete(rowKey(r))); else visible.forEach(r => n.add(rowKey(r)));
    setPicked(n);
  };
  // Deep Search needs a website (businesses without one have nothing to crawl)
  const deepTargets = useMemo(() => (picked.size ? rows.filter(r => picked.has(rowKey(r))) : rows.filter(r => !r.email && !deep[rowKey(r)]))
    .filter(r => r.website), [rows, picked, deep]);

  const runDeep = async () => {
    const batch = opts?.deepBatch || 10;
    const targets = deepTargets;
    if (!targets.length) return;
    setDeepRun({ done: 0, total: targets.length });
    setNotice(null);
    let found = 0, failed = false;
    for (let i = 0; i < targets.length; i += batch) {
      const chunk = targets.slice(i, i + batch);
      try {
        const res = await runDeepSearch({ items: chunk.map(r => ({ key: rowKey(r), url: r.website, website: r.website, company: r.company, kind: 'website' })), place });
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
      const res = await saveMapsResults(chosen.map(r => ({
        source_id: r.source_id, source: r.source, company: r.company, phone: r.phone, email: r.email, website: r.website,
        location: r.location, category: r.category, url: r.url, rating: r.rating, reviews: r.reviews, details: r.details
      })));
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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className="theme-card-panel" style={{ marginBottom: 0 }}>
        <div className="theme-panel-header" style={{ marginBottom: '1rem' }}>
          <div>
            <div className="theme-panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}><MapPin size={18} /> Google Maps</div>
            <div className="theme-panel-sub">Find local businesses with phone, website, address, and ratings.</div>
          </div>
        </div>
        {optsError && <div role="alert" className="jp-alert jp-alert-error"><AlertTriangle size={14} /> {optsError}</div>}
        <MiningForm
          idPrefix="gm" onSubmit={submit} busy={searching} disabled={!!deepRun || !!optsError || !opts}
          busyHint="Searching map sources..."
          keywords={{ label: 'Business category / keywords', hint: `(Enter or comma, up to ${opts?.maxKeywords || 5})`,
            values: keywords, setValues: setKeywords, max: opts?.maxKeywords || 5, error: errors.keywords,
            onClear: () => clear('keywords'), placeholder: 'e.g. restaurant, hospital, school, furniture shop' }}
          audience={{ values: audience, setValues: setAudience, max: 5,
            hint: '(optional — keeps businesses whose name or category mentions it)' }}
          extra={(
            <>
              <div className="form-group">
                <label className="form-label" htmlFor="gm-website">Website</label>
                <select id="gm-website" className="theme-form-input" value={website} onChange={(e) => setWebsite(e.target.value)}>
                  <option value="any">Any</option>
                  <option value="without">Without website (website leads)</option>
                  <option value="with">With website</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="gm-rating">Minimum rating <span className="jp-hint">(Google Places only)</span></label>
                <select id="gm-rating" className="theme-form-input" value={minRating} onChange={(e) => setMinRating(Number(e.target.value))}>
                  {(opts?.minRatings || [0, 3, 3.5, 4, 4.5]).map(n => <option key={n} value={n}>{n ? `${n}+ ★` : 'Any'}</option>)}
                </select>
              </div>
            </>
          )}
          location={{ mode: 'india', state, setState, states: opts?.states || [], stateRequired: true, stateError: errors.state,
            city, setCity, cityError: errors.city, onClear: clear, cityHint: '(recommended — searching a whole state is slow)' }}
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
      {result && <CacheNote cache={result.cache} busy={busy} onRefresh={() => submit(null, null, true)} />}

      {result && (
        <div className="jp-status-row" aria-label="Source results">
          {Object.entries(result.sources || {}).map(([id, st]) => (
            <span key={id} className={`jp-status-chip ${st.status === 'ok' && st.count === 0 ? 'empty' : st.status}`}
              title={(st.errors || []).join('\n') || `${st.count} results in ${st.seconds}s`}>
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
              <input type="text" placeholder="Filter results…" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter results" />
            </div>
            <span className="jp-hint">{visible.length} of {rows.length} · {picked.size} selected · {rows.filter(r => !r.website).length} without website</span>
            <div style={{ flex: 1 }} />
            <button type="button" className="theme-pill-btn neutral" onClick={runDeep} disabled={busy || !deepTargets.length}
              title="Opens the business website to find email / phone (businesses without a website are skipped)">
              {deepRun ? <Loader2 size={13} className="animate-spin" /> : <ScanSearch size={13} />}
              {deepRun ? ` Deep Search ${deepRun.done}/${deepRun.total}…` : ` Deep Search ${picked.size ? 'selected' : 'missing'} (${deepTargets.length})`}
            </button>
            <button type="button" className="theme-pill-btn neutral" onClick={() => downloadCsv(visible)} disabled={!visible.length}><Download size={13} /> Export CSV</button>
            <button type="button" className="theme-pill-btn primary" onClick={save} disabled={!picked.size || saving || busy}>
              {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />} Save to Leads{picked.size ? ` (${picked.size})` : ''}
            </button>
          </div>
          <div className="theme-table-scroll">
            <table className="jp-table">
              <thead>
                <tr>
                  <th style={{ width: 36 }}><input type="checkbox" aria-label="Select all visible results" checked={allVisiblePicked} onChange={togglePickAll} disabled={!visible.length} /></th>
                  <th>Business</th><th>Phone</th><th>Website</th><th>Rating</th><th>Email</th><th>Status</th><th style={{ width: 40 }} aria-label="Open" />
                </tr>
              </thead>
              <tbody>
                {visible.length === 0 ? (
                  <tr><td colSpan={8} className="jp-empty">{rows.length ? 'No results match this filter.' : 'Nothing found. Try another category, a city, or change the filters.'}</td></tr>
                ) : visible.map(r => {
                  const k = rowKey(r);
                  return (
                    <tr key={k} className={picked.has(k) ? 'selected' : ''}>
                      <td><input type="checkbox" aria-label={`Select ${r.company}`} checked={picked.has(k)} onChange={() => togglePick(k)} /></td>
                      <td>
                        <div className="jp-cell-title">{r.company}<span className="se-kind">{r.source}</span></div>
                        <div className="jp-cell-sub">{[r.category, r.location].filter(Boolean).join(' · ')}</div>
                      </td>
                      <td style={{ whiteSpace: 'nowrap' }}>{r.phone || '—'}</td>
                      <td className="se-wrap">{r.website
                        ? <a href={r.website} target="_blank" rel="noopener noreferrer">{r.website.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '')}</a>
                        : <span className="se-badge inleads" title="No website listed - a website / digital presence lead">No website</span>}</td>
                      <td style={{ whiteSpace: 'nowrap' }}>{r.rating ? <><Star size={12} style={{ verticalAlign: '-1px' }} /> {r.rating} <span className="jp-hint">({r.reviews})</span></> : '—'}</td>
                      <td className="se-wrap">
                        {r.email || (r.email_guess ? <span className="se-guess" title="Guessed - not found on the website. Not saved as the email.">{r.email_guess} (guess)</span> : '—')}
                        {r.socials && Object.keys(r.socials).length > 0 && (
                          <div className="se-socials" style={{ marginTop: 3 }}>{Object.entries(r.socials).map(([n, u]) => <a key={n} href={u} target="_blank" rel="noopener noreferrer" title={u}>{SOCIAL_SHORT[n] || n}</a>)}</div>
                        )}
                      </td>
                      <td>
                        {r.in_leads && <span className="se-badge inleads" title={r.match ? `Matches ${r.match}` : ''}>In leads</span>}
                        {r.deep_status && <span className={`se-badge deep-${r.deep_status}`} title={(r.deep_steps || []).join('\n')}>{DEEP_LABELS[r.deep_status] || r.deep_status}</span>}
                        {!r.in_leads && !r.deep_status && <span className="jp-hint">New</span>}
                      </td>
                      <td>{r.url && <a href={r.url} target="_blank" rel="noopener noreferrer" aria-label={`Open ${r.company} on the map`}><ExternalLink size={14} /></a>}</td>
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
