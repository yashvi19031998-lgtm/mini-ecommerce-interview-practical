'use client';

// Scraping / Mining -> Global Directories: find companies outside India from official registers and
// open directories, then deep-search and save them as leads.
// Backend: global_directories.py via /api/global-directories/*.

import React, { useEffect, useMemo, useState } from 'react';
import { Globe, Search, Loader2, X, ExternalLink, Save, Download, AlertTriangle, Sparkles } from 'lucide-react';
import { fetchGlobalDirectories, searchGlobalDirectories, saveGlobalDirectoryResults, runDeepSearch } from '../lib/api';
import CacheNote from './CacheNote';
import MiningForm from './MiningForm';

const GROUPS = [
  { kind: 'directory', status: 'available', label: 'Directories' },
  { kind: 'register', status: 'available', label: 'Official registers' },
  { status: 'needs_key', label: 'Need API key' },
  { status: 'unavailable', label: 'Not available' }
];

const DEEP_LABELS = { found: 'Found', partial: 'Website only', none: 'Nothing found', error: 'Failed' };
const rowKey = (r) => `${r.source_id}|${r.company}|${r.url || r.website || r.email || r.location}`;

function downloadCsv(rows) {
  const cols = ['company', 'email', 'phone', 'website', 'location', 'country', 'category', 'source', 'url', 'details'];
  const esc = (v) => {
    let s = String(v ?? '');
    if (/^[=+@-]/.test(s)) {
      s = `'${s}`;
    }
    return `"${s.replace(/"/g, '""')}"`;
  };
  const csv = [cols.join(','), ...rows.map(r => cols.map(c => esc(r[c])).join(','))].join('\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = `global_directories_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default function GlobalDirectories({ onLeadsSaved, onOpenSearchEngine }) {
  const [sources, setSources] = useState([]);
  const [countries, setCountries] = useState([]);
  const [limits, setLimits] = useState({ maxKeywords: 10 });
  const [catalogError, setCatalogError] = useState('');

  const [keywords, setKeywords] = useState([]);
  const [audience, setAudience] = useState([]);
  const [country, setCountry] = useState('');
  const [region, setRegion] = useState('');
  const [city, setCity] = useState('');
  const [selected, setSelected] = useState(new Set());
  const [errors, setErrors] = useState({});

  const [searching, setSearching] = useState(false);
  const [result, setResult] = useState(null);
  const [notice, setNotice] = useState(null);
  const [picked, setPicked] = useState(new Set());
  const [deep, setDeep] = useState({});
  const [deepRun, setDeepRun] = useState(null);
  const [filter, setFilter] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchGlobalDirectories()
      .then(res => {
        setSources(res.sources || []);
        setCountries(res.countries || []);
        if (res.maxKeywords) setLimits({ maxKeywords: res.maxKeywords });
      })
      .catch(err => setCatalogError(err.message || 'Could not load global sources. Is the Python backend running?'));
  }, []);

  const clear = (f) => setErrors(prev => (prev[f] ? { ...prev, [f]: '' } : prev));

  const submit = async (e, final = null, refresh = false) => {
    e?.preventDefault();
    const kws = final?.keywords || keywords;
    const aud = final?.audience || audience;
    const errs = {};

    if (!kws.length) errs.keywords = 'Enter at least one keyword';
    if (!country) errs.country = 'Select a country';
    if (city && !/^[A-Za-z .'-]{1,60}$/.test(city.trim())) errs.city = 'City must be letters only (max 60 characters)';
    if (region && !/^[A-Za-z .'-]{1,60}$/.test(region.trim())) errs.region = 'Region must be letters only (max 60 characters)';
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
      const res = await searchGlobalDirectories({
        keywords: kws,
        audience: aud,
        country,
        region: region.trim(),
        city: city.trim(),
        sources: [...selected],
        refresh
      });
      setResult(res);
      const st = Object.values(res.sources || {});
      if (!res.total && st.length && st.every(x => x.status !== 'ok')) {
        setNotice({ type: 'error', text: 'No source returned results - hover the source chips below for the reason.' });
        return;
      }
      setNotice({
        type: 'success',
        text: `Found ${res.total} companies across ${Object.keys(res.sources || {}).length} sources${res.cache?.hit ? ' (saved results)' : ''}`
      });
    } catch (err) {
      setNotice({ type: 'error', text: err.message || 'Search failed' });
    } finally {
      setSearching(false);
    }
  };

  // Merge Deep Search discoveries into visible rows
  const rawRows = result?.results || [];
  const rows = useMemo(() => rawRows.map(r => {
    const k = rowKey(r);
    const d = deep[k];
    if (!d) return r;
    return {
      ...r,
      company: r.company || d.company || '',
      email: r.email || (d.emails || []).join(', '),
      phone: r.phone || (d.phones || [])[0] || '',
      website: r.website || d.website || '',
      location: r.location || d.address || '',
      socials: d.socials || {},
      deep_status: d.status,
      deep_steps: d.steps || [],
    };
  }), [rawRows, deep]);

  const visible = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(r =>
      `${r.company} ${r.email} ${r.phone} ${r.website} ${r.location} ${r.country} ${r.category} ${r.source}`.toLowerCase().includes(q)
    );
  }, [rows, filter]);

  const allVisiblePicked = visible.length > 0 && visible.every(r => picked.has(rowKey(r)));
  const togglePick = (k) => {
    const n = new Set(picked);
    if (n.has(k)) n.delete(k); else n.add(k);
    setPicked(n);
  };
  const togglePickAll = () => {
    const n = new Set(picked);
    if (allVisiblePicked) visible.forEach(r => n.delete(rowKey(r))); else visible.forEach(r => n.add(rowKey(r)));
    setPicked(n);
  };

  // Deep Search targets: selected rows, or rows missing an email
  const deepTargets = useMemo(() => (
    picked.size
      ? rows.filter(r => picked.has(rowKey(r)))
      : rows.filter(r => !r.email && !deep[rowKey(r)])
  ), [rows, picked, deep]);

  const runDeep = async () => {
    const targets = deepTargets;
    if (!targets.length) return;
    const batch = 10;
    setDeepRun({ done: 0, total: targets.length });
    setNotice(null);
    let found = 0;
    let failed = 0;

    for (let i = 0; i < targets.length; i += batch) {
      const chunk = targets.slice(i, i + batch);
      try {
        const res = await runDeepSearch({
          items: chunk.map(r => ({
            key: rowKey(r),
            url: r.url,
            website: r.website,
            company: r.company,
            kind: r.website ? 'website' : 'listing'
          })),
          place: city.trim() || region.trim() || country
        });
        const add = {};
        (res.results || []).forEach(d => {
          add[d.key] = d;
          if (d.status === 'found') found += 1;
        });
        setDeep(prev => ({ ...prev, ...add }));
      } catch (err) {
        failed += chunk.length;
        setNotice({ type: 'error', text: `Deep Search stopped: ${err.message}` });
        break;
      }
      setDeepRun({ done: Math.min(i + batch, targets.length), total: targets.length });
    }
    setDeepRun(null);
    if (!failed) {
      setNotice({ type: 'success', text: `Deep Search finished: contact details found for ${found} of ${targets.length}` });
    }
  };

  const save = async () => {
    const chosen = rows.filter(r => picked.has(rowKey(r)));
    if (!chosen.length) return;
    setSaving(true);
    try {
      const res = await saveGlobalDirectoryResults(chosen);
      const parts = [`${res.added} new lead${res.added === 1 ? '' : 's'}`];
      if (res.updated) parts.push(`${res.updated} updated`);
      if (res.duplicate) parts.push(`${res.duplicate} already saved`);
      if (res.skipped_invalid) parts.push(`${res.skipped_invalid} skipped (no contact details)`);
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

  const extraRegionField = (
    <div className="form-group">
      <label className="form-label" htmlFor="gd-region">
        Region / State <span className="jp-hint">(optional — US state for SEC, region for OpenStreetMap)</span>
      </label>
      <input
        id="gd-region"
        className="theme-form-input"
        value={region}
        maxLength={60}
        placeholder="e.g. California, England, Bavaria"
        onChange={(e) => { setRegion(e.target.value); clear('region'); }}
        aria-invalid={!!errors.region}
      />
      {errors.region && <div className="jp-field-error">{errors.region}</div>}
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className="theme-card-panel" style={{ marginBottom: 0 }}>
        <div className="theme-panel-header" style={{ marginBottom: '1rem' }}>
          <div>
            <div className="theme-panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Globe size={18} /> Global Directories
            </div>
            <div className="theme-panel-sub">
              Find international companies from official registries and open directories.
            </div>
          </div>
        </div>

        {catalogError && (
          <div role="alert" className="jp-alert jp-alert-error">
            <AlertTriangle size={14} /> {catalogError}
          </div>
        )}

        <MiningForm
          idPrefix="gd"
          onSubmit={submit}
          busy={searching}
          disabled={!!catalogError}
          busyHint="Searching global directories..."
          keywords={{
            label: 'Keywords / Business category',
            hint: `(Enter or comma, up to ${limits.maxKeywords})`,
            values: keywords,
            setValues: setKeywords,
            max: limits.maxKeywords,
            error: errors.keywords,
            onClear: () => clear('keywords'),
            placeholder: 'e.g. software, fintech, logistics, robotics'
          }}
          audience={{
            values: audience,
            setValues: setAudience,
            max: 5,
            hint: '(optional — narrow results by industry or segment)',
            placeholder: 'e.g. IT / Software, Manufacturing, Startups'
          }}
          location={{
            mode: 'country',
            countries,
            country,
            setCountry,
            countryError: errors.country,
            city,
            setCity,
            cityError: errors.city,
            cityPlaceholder: 'e.g. London, New York, Berlin',
            onClear: clear
          }}
          extra={extraRegionField}
          sources={{
            label: 'Sources',
            items: sources,
            selected,
            setSelected,
            error: errors.sources,
            onClear: () => clear('sources'),
            placeholder: 'Select sources',
            allLabel: 'All available sources',
            groups: GROUPS
          }}
        />
      </div>

      {notice && (
        <div role="status" className={`jp-alert ${notice.type === 'error' ? 'jp-alert-error' : 'jp-alert-success'}`}>
          {notice.type === 'error' && <AlertTriangle size={14} />}
          <span style={{ flex: 1 }}>{notice.text}</span>
          <button type="button" className="jp-alert-close" aria-label="Dismiss message" onClick={() => setNotice(null)}>
            <X size={14} />
          </button>
        </div>
      )}

      {result && <CacheNote cache={result.cache} busy={searching} onRefresh={() => submit(null, null, true)} />}

      {result && (
        <div className="jp-status-row" aria-label="Source results">
          {Object.entries(result.sources || {}).map(([id, st]) => (
            <span
              key={id}
              className={`jp-status-chip ${st.status === 'ok' && st.count === 0 ? 'empty' : st.status}`}
              title={(st.errors || []).join('\n') || `${st.count} results in ${st.seconds}s`}
            >
              {st.name}: {st.status === 'skipped' ? 'skipped' : st.status === 'error' ? 'failed' : `${st.count}`}
            </span>
          ))}
        </div>
      )}

      {result && (
        <div className="theme-table-container">
          <div className="theme-table-controls">
            <div className="theme-control-search">
              <Search size={14} color="#a3a7ae" />
              <input
                type="text"
                placeholder="Filter results…"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                aria-label="Filter results"
              />
            </div>
            <span className="jp-hint">{visible.length} of {rows.length} · {picked.size} selected</span>
            <div style={{ flex: 1 }} />
            <button
              type="button"
              className="theme-pill-btn neutral"
              onClick={runDeep}
              disabled={!rows.length || !!deepRun}
              title="Find emails and direct phones via Deep Search on company websites"
            >
              {deepRun ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
              {deepRun ? `Deep Searching (${deepRun.done}/${deepRun.total})` : 'Deep Search'}
            </button>
            <button
              type="button"
              className="theme-pill-btn neutral"
              onClick={() => downloadCsv(visible)}
              disabled={!visible.length}
            >
              <Download size={13} /> Export CSV
            </button>
            <button
              type="button"
              className="theme-pill-btn primary"
              onClick={save}
              disabled={!picked.size || saving}
            >
              {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
              Save to Leads{picked.size ? ` (${picked.size})` : ''}
            </button>
          </div>

          <div className="theme-table-scroll">
            <table className="jp-table">
              <thead>
                <tr>
                  <th style={{ width: 36 }}>
                    <input
                      type="checkbox"
                      aria-label="Select all visible results"
                      checked={allVisiblePicked}
                      onChange={togglePickAll}
                      disabled={!visible.length}
                    />
                  </th>
                  <th>Company</th>
                  <th>Email</th>
                  <th>Phone</th>
                  <th>Website</th>
                  <th>Location</th>
                  <th>Category</th>
                  <th>Source</th>
                  <th>Status</th>
                  <th style={{ width: 40 }} aria-label="Open" />
                </tr>
              </thead>
              <tbody>
                {visible.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="jp-empty">
                      {rows.length ? 'No results match this filter.' : 'Nothing found. Try another keyword, a city, or more sources.'}
                    </td>
                  </tr>
                ) : visible.map(r => {
                  const k = rowKey(r);
                  return (
                    <tr key={k} className={picked.has(k) ? 'selected' : ''}>
                      <td>
                        <input
                          type="checkbox"
                          aria-label={`Select ${r.company}`}
                          checked={picked.has(k)}
                          onChange={() => togglePick(k)}
                        />
                      </td>
                      <td>
                        <div className="jp-cell-title">{r.company || '—'}</div>
                        {(r.details || r.category) && (
                          <div className="jp-cell-sub" title={r.details}>
                            {[r.details].filter(Boolean).join(' · ')}
                          </div>
                        )}
                      </td>
                      <td>
                        {r.email ? (
                          <span style={{ color: '#047857', fontWeight: 500 }}>{r.email}</span>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td>{r.phone || '—'}</td>
                      <td>
                        {r.website ? (
                          <a href={r.website} target="_blank" rel="noopener noreferrer">
                            {r.website.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '')}
                          </a>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td>{[r.location, r.country].filter(Boolean).join(', ') || '—'}</td>
                      <td>{r.category || '—'}</td>
                      <td><span className="theme-source-badge">{r.source}</span></td>
                      <td>
                        {r.in_leads && <span className="se-badge inleads" title={r.match ? `Matches ${r.match}` : ''}>In leads</span>}
                        {r.deep_status && <span className={`se-badge deep-${r.deep_status}`} title={(r.deep_steps || []).join(' | ')}>{DEEP_LABELS[r.deep_status] || r.deep_status}</span>}
                        {!r.in_leads && !r.deep_status && <span className="jp-hint">New</span>}
                      </td>
                      <td>
                        {r.url && (
                          <a
                            href={r.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            aria-label={`Open ${r.company} on ${r.source}`}
                          >
                            <ExternalLink size={14} />
                          </a>
                        )}
                      </td>
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
