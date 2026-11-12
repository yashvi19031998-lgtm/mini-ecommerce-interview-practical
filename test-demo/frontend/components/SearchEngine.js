'use client';

// Scraping / Mining -> Search Engines: ready-made search queries -> results -> Deep Search for
// email / phone / website -> Save to Leads. Backend: search_engine.py + deep_search.py via /api/search-engine/*.

import React, { useEffect, useMemo, useState } from 'react';
import {
  SearchCode, Search, Loader2, X, ExternalLink, Save, Download, AlertTriangle, ScanSearch, ChevronDown, ChevronRight
} from 'lucide-react';
import { fetchSearchEngineOptions, runSearchEngine, runDeepSearch, saveSearchEngineResults } from '../lib/api';
import CacheNote from './CacheNote';
import ChipInput from './ChipInput';
import MiningForm from './MiningForm';

const TIME_LABELS = { any: 'Any time', day: 'Past day', week: 'Past week', month: 'Past month', year: 'Past year' };
const DEEP_LABELS = { found: 'Found', partial: 'Website only', none: 'Nothing found', error: 'Failed' };
const SOCIAL_SHORT = { linkedin: 'in', instagram: 'ig', facebook: 'fb', twitter: 'x', youtube: 'yt', whatsapp: 'wa' };
const rowKey = (r) => r.url;

// Spreadsheet-safe CSV (cells starting with = + - @ are prefixed so Excel doesn't run them as formulas)
function downloadCsv(rows) {
  const cols = ['company', 'email', 'phone', 'website', 'address', 'socials', 'email_guess', 'in_leads', 'kind', 'url', 'snippet', 'keyword', 'engine', 'query'];
  const cell = (v) => {
    let s = typeof v === 'object' && v !== null ? Object.entries(v).map(([k, x]) => `${k}: ${x}`).join(' | ') : String(v ?? '');
    if (/^[=+\-@]/.test(s)) s = `'${s}`;
    return `"${s.replace(/"/g, '""')}"`;
  };
  const csv = [cols.join(','), ...rows.map(r => cols.map(c => cell(r[c])).join(','))].join('\n');
  const url = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = `search_engine_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default function SearchEngine({ onLeadsSaved }) {
  const [opts, setOpts] = useState(null);
  const [optsError, setOptsError] = useState('');

  const [keywords, setKeywords] = useState([]);
  const [audience, setAudience] = useState([]);
  const [mode, setMode] = useState('companies');
  const [customQuery, setCustomQuery] = useState('');
  const [state, setState] = useState('All India');
  const [city, setCity] = useState('');
  const [engine, setEngine] = useState('auto');
  const [time, setTime] = useState('any');
  const [maxResults, setMaxResults] = useState(25);
  const [excludes, setExcludes] = useState([]);
  const [errors, setErrors] = useState({});

  const [searching, setSearching] = useState(false);
  const [result, setResult] = useState(null);
  const [notice, setNotice] = useState(null);
  const [showQueries, setShowQueries] = useState(false);
  const [picked, setPicked] = useState(new Set());
  const [filter, setFilter] = useState('');
  const [onlyMissing, setOnlyMissing] = useState(false);

  const [deep, setDeep] = useState({});            // url -> deep search result
  const [deepRun, setDeepRun] = useState(null);    // { done, total }
  const [useHunter, setUseHunter] = useState(false);

  const [saving, setSaving] = useState(false);
  const [sendEmail, setSendEmail] = useState(false);

  useEffect(() => {
    fetchSearchEngineOptions()
      .then(setOpts)
      .catch(err => setOptsError(err.message || 'Could not load options. Is the Python backend running?'));
  }, []);

  const clear = (f) => setErrors(prev => (prev[f] ? { ...prev, [f]: '' } : prev));
  const modeInfo = opts?.modes?.find(m => m.id === mode);
  const place = city.trim() || (state !== 'All India' ? state : '');

  const submit = async (e, final = null, refresh = false) => {
    e?.preventDefault();
    const kws = final?.keywords || keywords;
    const aud = final?.audience || audience;
    const errs = {};
    if (!kws.length) errs.keywords = 'Enter at least one keyword';
    if (mode === 'custom' && !customQuery.trim()) errs.custom = 'Write a custom query';
    if (city && !/^[A-Za-z .'-]{1,60}$/.test(city.trim())) errs.city = 'City must be letters only (max 60 characters)';
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setSearching(true);
    setResult(null);
    setPicked(new Set());
    setDeep({});
    setFilter('');
    setNotice(null);
    try {
      const res = await runSearchEngine({
        keywords: kws, audience: aud, mode, custom_query: customQuery.trim(), state, city: city.trim(), engine, time,
        max_results: maxResults, exclude_sites: excludes, refresh
      });
      setResult(res);
      const eng = Object.values(res.engines || {})[0];
      setNotice({
        type: res.total ? 'success' : 'info',
        text: `Found ${res.total} result${res.total === 1 ? '' : 's'} with ${eng?.name || 'search'} (${eng?.queries_run ?? 0} of ${eng?.queries_total ?? 0} queries)${res.cache?.hit ? ' (saved results)' : ''}`
      });
    } catch (err) {
      setNotice({ type: 'error', text: err.message || 'Search failed' });
    } finally {
      setSearching(false);
    }
  };

  // Results merged with Deep Search findings (the original search value wins when present)
  const rows = useMemo(() => (result?.results || []).map(r => {
    const d = deep[rowKey(r)];
    if (!d) return r;
    return {
      ...r,
      company: r.kind === 'listing' || !r.company ? (r.company || d.company) : r.company,
      email: r.email || (d.emails || []).join(', '),
      phone: r.phone || (d.phones || [])[0] || '',
      website: r.website || d.website || '',
      address: d.address || '',
      socials: d.socials || {},
      email_guess: d.email_guess || '',
      cin: d.cin || '',
      contacts: d.contacts || [],
      deep_status: d.status,
      deep_steps: d.steps || [],
    };
  }), [result, deep]);

  const visible = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return rows.filter(r => (!onlyMissing || !(r.email || r.phone)) &&
      (!q || `${r.company} ${r.domain} ${r.snippet} ${r.email} ${r.keyword}`.toLowerCase().includes(q)));
  }, [rows, filter, onlyMissing]);
  const allVisiblePicked = visible.length > 0 && visible.every(r => picked.has(rowKey(r)));
  const togglePick = (k) => { const n = new Set(picked); if (n.has(k)) n.delete(k); else n.add(k); setPicked(n); };
  const togglePickAll = () => {
    const n = new Set(picked);
    if (allVisiblePicked) visible.forEach(r => n.delete(rowKey(r))); else visible.forEach(r => n.add(rowKey(r)));
    setPicked(n);
  };

  // Deep Search: the selected rows, or (nothing selected) every row still missing an email that wasn't deep-searched yet
  const deepTargets = useMemo(() => (picked.size
    ? rows.filter(r => picked.has(rowKey(r)))
    : rows.filter(r => !r.email && !deep[rowKey(r)] && r.kind !== 'article')), [rows, picked, deep]);

  const runDeep = async () => {
    const targets = deepTargets;
    if (!targets.length) return;
    const batch = opts?.deepBatch || 10;
    setDeepRun({ done: 0, total: targets.length });
    setNotice(null);
    let found = 0, failed = 0;
    for (let i = 0; i < targets.length; i += batch) {
      const chunk = targets.slice(i, i + batch);
      try {
        const res = await runDeepSearch({
          items: chunk.map(r => ({ key: rowKey(r), url: r.url, website: r.website, company: r.company, kind: r.kind })),
          engine, use_hunter: useHunter, place
        });
        const add = {};
        (res.results || []).forEach(d => { add[d.key] = d; if (d.status === 'found') found += 1; });
        setDeep(prev => ({ ...prev, ...add }));
      } catch (err) {
        failed += chunk.length;
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
    if (sendEmail) {
      const withEmail = chosen.filter(r => r.email).length;
      if (!window.confirm(`This will send the intro email right away to new leads that have an email (up to ${withEmail}). Continue?`)) return;
    }
    setSaving(true);
    try {
      const res = await saveSearchEngineResults({
        results: chosen.map(r => ({
          company: r.company, url: r.url, website: r.website, email: r.email, phone: r.phone, snippet: r.snippet,
          address: r.address || '', socials: r.socials || {}, engine: r.engine, mode: r.mode, location: place
        })),
        send_outreach_email: sendEmail
      });
      const parts = [`${res.added} new lead${res.added === 1 ? '' : 's'}`];
      if (res.updated) parts.push(`${res.updated} updated`);
      if (res.duplicate) parts.push(`${res.duplicate} already saved`);
      if (res.skipped_invalid) parts.push(`${res.skipped_invalid} skipped`);
      if (sendEmail) parts.push(`${res.emails_sent} email${res.emails_sent === 1 ? '' : 's'} sent`);
      setNotice({ type: 'success', text: `Saved to Leads: ${parts.join(', ')}` });
      setResult(prev => prev && ({
        ...prev, results: prev.results.map(r => (picked.has(rowKey(r)) ? { ...r, in_leads: true } : r))
      }));
      setPicked(new Set());
      onLeadsSaved && onLeadsSaved();
    } catch (err) {
      setNotice({ type: 'error', text: `Could not save: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const engineStatus = result ? Object.values(result.engines || {})[0] : null;
  const busy = searching || !!deepRun;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className="theme-card-panel" style={{ marginBottom: 0 }}>
        <div className="theme-panel-header" style={{ marginBottom: '1rem' }}>
          <div>
            <div className="theme-panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}><SearchCode size={18} /> Search Engines</div>
            <div className="theme-panel-sub">Ready-made searches find companies and listings; Deep Search opens their websites for email and phone.</div>
          </div>
        </div>
        {optsError && <div role="alert" className="jp-alert jp-alert-error"><AlertTriangle size={14} /> {optsError}</div>}

        <MiningForm
          idPrefix="se" onSubmit={submit} busy={searching} disabled={!!deepRun || !!optsError || !opts}
          busyHint="Queries run one by one to respect rate limits — can take up to a minute."
          keywords={{ label: 'Keywords', hint: `(Enter or comma, up to ${opts?.maxKeywords || 5})`, values: keywords,
            setValues: setKeywords, max: opts?.maxKeywords || 5, error: errors.keywords, onClear: () => clear('keywords'),
            placeholder: 'e.g. software company, furniture manufacturer, CA firm' }}
          audience={{ values: audience, setValues: setAudience, max: 5,
            hint: '(optional — industries or segments, up to 5; added to every query as "A" OR "B")' }}
          extra={(
            <>
              <div className="form-group">
                <label className="form-label" htmlFor="se-mode">Search type</label>
                <select id="se-mode" className="theme-form-input" value={mode} onChange={(e) => { setMode(e.target.value); clear('custom'); }}>
                  {(opts?.modes || []).map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
                </select>
                {modeInfo && <div className="jp-hint" style={{ marginTop: 4 }}>{modeInfo.help}</div>}
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="se-engine">Search engine</label>
                <select id="se-engine" className="theme-form-input" value={engine} onChange={(e) => setEngine(e.target.value)}>
                  {(opts?.engines || []).map(en => (
                    <option key={en.id} value={en.id} disabled={en.status !== 'available'}>
                      {en.name}{en.status === 'needs_key' ? ' — add key in Settings' : ''}
                    </option>
                  ))}
                </select>
                <div className="jp-hint" style={{ marginTop: 4 }}>{(opts?.engines || []).find(en => en.id === engine)?.note}</div>
              </div>
              {mode === 'custom' && (
                <div className="form-group jp-span-2">
                  <label className="form-label" htmlFor="se-custom">Custom query <span className="jp-hint">({'{keyword}'} and {'{city}'} are replaced; max 300 characters)</span></label>
                  <input id="se-custom" className="theme-form-input" maxLength={300} value={customQuery}
                    placeholder={'e.g. "{keyword}" {city} "contact us" -jobs'} onChange={(e) => { setCustomQuery(e.target.value); clear('custom'); }}
                    aria-invalid={!!errors.custom} />
                  {errors.custom && <div className="jp-field-error">{errors.custom}</div>}
                </div>
              )}
              <div className="form-group">
                <label className="form-label" htmlFor="se-time">Published</label>
                <select id="se-time" className="theme-form-input" value={time} onChange={(e) => setTime(e.target.value)}>
                  {(opts?.timeFilters || ['any']).map(t => <option key={t} value={t}>{TIME_LABELS[t] || t}</option>)}
                </select>
              </div>
              <div className="form-group">
                <ChipInput id="se-exclude" label="Exclude sites" hint="(optional, e.g. justdial.com)" values={excludes}
                  setValues={setExcludes} max={10} placeholder="Sites to leave out" />
              </div>
            </>
          )}
          location={{ mode: 'india', state, setState, states: opts?.states || ['All India'], stateRequired: false,
            city, setCity, cityError: errors.city, onClear: clear }}
          maxResults={{ value: maxResults, setValue: setMaxResults, choices: opts?.maxResultsChoices || [10, 25, 50, 100] }}
        />
      </div>

      {notice && (
        <div role="status" className={`jp-alert ${notice.type === 'error' ? 'jp-alert-error' : notice.type === 'info' ? 'se-alert-info' : 'jp-alert-success'}`}>
          {notice.type === 'error' && <AlertTriangle size={14} />}<span style={{ flex: 1 }}>{notice.text}</span>
          <button type="button" className="jp-alert-close" aria-label="Dismiss message" onClick={() => setNotice(null)}><X size={14} /></button>
        </div>
      )}
      {result && <CacheNote cache={result.cache} busy={busy} onRefresh={() => submit(null, null, true)} />}
      {result?.rate_limited && (
        <div className="jp-alert se-alert-warn" role="note"><AlertTriangle size={14} />
          <span>The search engine asked us to slow down, so the search stopped early. Results found so far are shown — try again in a few minutes.</span>
        </div>
      )}
      {result?.hint && <div className="jp-alert se-alert-warn" role="note"><AlertTriangle size={14} /><span>{result.hint}</span></div>}

      {result && (
        <div className="se-meta">
          {engineStatus && (
            <span className={`jp-status-chip ${engineStatus.status === 'ok' && !engineStatus.count ? 'empty' : engineStatus.status}`}
              title={(engineStatus.errors || []).join('\n') || `${engineStatus.count} results in ${engineStatus.seconds}s`}>
              {engineStatus.name}: {engineStatus.status === 'error' ? 'failed' : engineStatus.count}
              {engineStatus.status === 'partial' ? ' (partial)' : ''}
            </span>
          )}
          {result.ignored_off_target > 0 && <span className="jp-hint">{result.ignored_off_target} off-target results hidden</span>}
          <button type="button" className="se-link-btn" onClick={() => setShowQueries(!showQueries)} aria-expanded={showQueries}>
            {showQueries ? <ChevronDown size={13} /> : <ChevronRight size={13} />} Queries used ({(result.queries || []).length})
          </button>
          {showQueries && <ul className="se-queries">{(result.queries || []).map(q => <li key={q}><code>{q}</code></li>)}</ul>}
          {(engineStatus?.errors || []).length > 0 && (
            <ul className="se-errors">{engineStatus.errors.map((er, i) => <li key={i}>{er}</li>)}</ul>
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
            <label className="se-check"><input type="checkbox" checked={onlyMissing} onChange={(e) => setOnlyMissing(e.target.checked)} /> Only without email/phone</label>
            <span className="jp-hint">{visible.length} of {rows.length} · {picked.size} selected</span>
            <div style={{ flex: 1 }} />
            {opts?.hunterAvailable && (
              <label className="se-check" title="Uses Hunter.io credits for rows where the website shows no email">
                <input type="checkbox" checked={useHunter} onChange={(e) => setUseHunter(e.target.checked)} /> Use Hunter credits
              </label>
            )}
            <button type="button" className="theme-pill-btn neutral" onClick={runDeep} disabled={busy || !deepTargets.length}
              title={picked.size ? 'Deep search the selected rows' : 'Deep search every row without an email'}>
              {deepRun ? <Loader2 size={13} className="animate-spin" /> : <ScanSearch size={13} />}
              {deepRun ? ` Deep Search ${deepRun.done}/${deepRun.total}…` : ` Deep Search ${picked.size ? 'selected' : 'missing'} (${deepTargets.length})`}
            </button>
            <button type="button" className="theme-pill-btn neutral" onClick={() => downloadCsv(visible)} disabled={!visible.length}><Download size={13} /> Export CSV</button>
            <label className="se-check" title="Uses your SMTP settings and the default email template">
              <input type="checkbox" checked={sendEmail} onChange={(e) => setSendEmail(e.target.checked)} /> Send intro email on save
            </label>
            <button type="button" className="theme-pill-btn primary" onClick={save} disabled={!picked.size || saving || busy}>
              {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />} Save to Leads{picked.size ? ` (${picked.size})` : ''}
            </button>
          </div>
          <div className="theme-table-scroll">
            <table className="jp-table">
              <thead>
                <tr>
                  <th style={{ width: 36 }}><input type="checkbox" aria-label="Select all visible results" checked={allVisiblePicked} onChange={togglePickAll} disabled={!visible.length} /></th>
                  <th>Company</th><th>Email</th><th>Phone</th><th>Website</th><th>Social</th><th>Status</th><th style={{ width: 40 }} aria-label="Open" />
                </tr>
              </thead>
              <tbody>
                {visible.length === 0 ? (
                  <tr><td colSpan={8} className="jp-empty">{rows.length ? 'No results match this filter.' : 'Nothing found. Try other keywords, another search type, or add a search engine key in Settings.'}</td></tr>
                ) : visible.map(r => {
                  const k = rowKey(r);
                  return (
                    <tr key={k} className={picked.has(k) ? 'selected' : ''}>
                      <td><input type="checkbox" aria-label={`Select ${r.company}`} checked={picked.has(k)} onChange={() => togglePick(k)} /></td>
                      <td>
                        <div className="jp-cell-title">{r.company || r.domain}{r.kind === 'listing' && <span className="se-kind">{r.domain}</span>}{r.kind === 'article' && <span className="se-kind" title="A list of companies, not one company's website">list article</span>}</div>
                        {r.snippet && <div className="jp-cell-sub se-snippet" title={r.snippet}>{r.snippet}</div>}
                        {r.address && <div className="jp-cell-sub">📍 {r.address}</div>}
                        {r.cin && <div className="jp-cell-sub">CIN {r.cin}</div>}
                      </td>
                      <td className="se-wrap">
                        {r.email || (r.email_guess ? <span className="se-guess" title="Guessed - not found on the website. Not saved as the email.">{r.email_guess} (guess)</span> : '—')}
                        {(r.contacts || []).length > 0 && <div className="jp-cell-sub">{r.contacts.map(c => [c.name, c.position].filter(Boolean).join(' – ')).filter(Boolean).slice(0, 2).join('; ')}</div>}
                      </td>
                      <td style={{ whiteSpace: 'nowrap' }}>{r.phone || '—'}</td>
                      <td className="se-wrap">{r.website ? <a href={r.website} target="_blank" rel="noopener noreferrer">{r.website.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '')}</a> : '—'}</td>
                      <td>
                        {r.socials && Object.keys(r.socials).length
                          ? <span className="se-socials">{Object.entries(r.socials).map(([n, u]) => <a key={n} href={u} target="_blank" rel="noopener noreferrer" title={u}>{SOCIAL_SHORT[n] || n}</a>)}</span>
                          : '—'}
                      </td>
                      <td>
                        {r.in_leads && <span className="se-badge inleads" title={r.match ? `Matches ${r.match}` : ''}>In leads</span>}
                        {r.deep_status && <span className={`se-badge deep-${r.deep_status}`} title={(r.deep_steps || []).join('\n')}>{DEEP_LABELS[r.deep_status] || r.deep_status}</span>}
                        {!r.in_leads && !r.deep_status && <span className="jp-hint">New</span>}
                      </td>
                      <td>{r.url && <a href={r.url} target="_blank" rel="noopener noreferrer" aria-label={`Open ${r.company}`}><ExternalLink size={14} /></a>}</td>
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
