'use client';

// CRM Sources: find businesses (directories) and decision makers (B2B contact databases), then save
// them as leads. Backend: crm_sources.py via /api/crm-sources/*.

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Building2, Search, Loader2, X, ChevronDown, ExternalLink, Save, Download, AlertTriangle } from 'lucide-react';
import { fetchCrmSources, searchCrmSources, saveCrmResultsToLeads } from '../lib/api';

const MAX_LEN = 80;
const GROUPS = [
  { kind: 'directory', status: 'available', label: 'Business directories' },
  { kind: 'database', status: 'available', label: 'Contact databases' },
  { kind: 'database', status: 'needs_key', label: 'Contact databases — need API key' },
  { kind: null, status: 'unavailable', label: 'Not available' }
];
const rowKey = (r) => `${r.source_id}|${r.company}|${r.contact_name}|${r.email}|${r.url}`;

function downloadCsv(rows) {
  const cols = ['company', 'contact_name', 'contact_title', 'email', 'phone', 'website', 'location', 'category', 'source', 'url', 'linkedin', 'details'];
  const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const csv = [cols.join(','), ...rows.map(r => cols.map(c => esc(r[c])).join(','))].join('\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = `crm_sources_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function ChipInput({ id, label, hint, values, setValues, max, placeholder, error, onChangeClear }) {
  const [text, setText] = useState('');
  const [localError, setLocalError] = useState('');
  const add = (raw) => {
    const parts = String(raw).split(',').map(t => t.trim()).filter(Boolean);
    const next = [...values];
    let err = '';
    for (const t of parts) {
      if (t.length > MAX_LEN) { err = `"${t.slice(0, 20)}…" is longer than ${MAX_LEN} characters`; continue; }
      if (next.some(x => x.toLowerCase() === t.toLowerCase())) continue;
      if (next.length >= max) { err = `You can add at most ${max}`; break; }
      next.push(t);
    }
    setValues(next);
    setText('');
    setLocalError(err);
  };
  return (
    <div className="form-group">
      <label className="form-label" htmlFor={id}>{label} <span className="jp-hint">{hint}</span></label>
      <div className={`jp-chip-input ${error || localError ? 'has-error' : ''}`}>
        {values.map(v => (
          <span key={v} className="jp-chip">{v}
            <button type="button" aria-label={`Remove ${v}`} onClick={() => setValues(values.filter(x => x !== v))}><X size={12} /></button>
          </span>
        ))}
        <input id={id} type="text" value={text} placeholder={values.length ? 'Add another…' : placeholder}
          onChange={(e) => { setText(e.target.value); if (e.target.value.trim() && onChangeClear) onChangeClear(); }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add(text); }
            else if (e.key === 'Backspace' && !text && values.length) setValues(values.slice(0, -1));
          }}
          onBlur={() => text.trim() && add(text)} />
      </div>
      {(error || localError) && <div className="jp-field-error">{error || localError}</div>}
    </div>
  );
}

export default function CrmSources({ onLeadsSaved }) {
  const [sources, setSources] = useState([]);
  const [states, setStates] = useState([]);
  const [limits, setLimits] = useState({ maxKeywords: 10, maxTitles: 10 });
  const [catalogError, setCatalogError] = useState('');

  const [keywords, setKeywords] = useState([]);
  const [titles, setTitles] = useState([]);
  const [state, setState] = useState('');
  const [city, setCity] = useState('');
  const [selected, setSelected] = useState(new Set());
  const [menuOpen, setMenuOpen] = useState(false);
  const [errors, setErrors] = useState({});
  const menuRef = useRef(null);

  const [searching, setSearching] = useState(false);
  const [result, setResult] = useState(null);
  const [notice, setNotice] = useState(null);
  const [picked, setPicked] = useState(new Set());
  const [filter, setFilter] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchCrmSources()
      .then(res => { setSources(res.sources || []); setStates(res.states || []); setLimits({ maxKeywords: res.maxKeywords, maxTitles: res.maxTitles }); })
      .catch(err => setCatalogError(err.message || 'Could not load sources. Is the Python backend running?'));
  }, []);
  useEffect(() => {
    const close = (e) => { if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const available = useMemo(() => sources.filter(s => s.status === 'available'), [sources]);
  const allSelected = available.length > 0 && available.every(s => selected.has(s.id));
  const clear = (f) => setErrors(prev => (prev[f] ? { ...prev, [f]: '' } : prev));
  const toggle = (id) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelected(next);
    if (next.size) clear('sources');
  };
  const sourceLabel = !selected.size ? 'Select sources'
    : allSelected ? `All available sources (${selected.size})`
      : sources.filter(s => selected.has(s.id)).map(s => s.name).join(', ');

  const submit = async (e) => {
    e.preventDefault();
    const errs = {};
    if (!keywords.length) errs.keywords = 'Enter at least one business category or keyword';
    if (!state) errs.state = 'Select a state';
    if (city && !/^[A-Za-z .'-]{1,60}$/.test(city.trim())) errs.city = 'City must be letters only (max 60 characters)';
    if (!selected.size) errs.sources = 'Select at least one source';
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setSearching(true);
    setResult(null);
    setPicked(new Set());
    setFilter('');
    setNotice(null);
    try {
      const res = await searchCrmSources({ keywords, titles, state, city: city.trim(), sources: [...selected] });
      setResult(res);
      setNotice({ type: 'success', text: `Found ${res.total} businesses/contacts across ${Object.keys(res.sources || {}).length} sources` });
    } catch (err) {
      setNotice({ type: 'error', text: err.message || 'Search failed' });
    } finally {
      setSearching(false);
    }
  };

  const rows = result?.results || [];
  const visible = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(r => `${r.company} ${r.contact_name} ${r.contact_title} ${r.location} ${r.category} ${r.source}`.toLowerCase().includes(q));
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
      const res = await saveCrmResultsToLeads(chosen);
      const parts = [`${res.added} new lead${res.added === 1 ? '' : 's'}`];
      if (res.updated) parts.push(`${res.updated} updated`);
      if (res.duplicate) parts.push(`${res.duplicate} already saved`);
      if (res.skipped_invalid) parts.push(`${res.skipped_invalid} skipped (no contact details)`);
      setNotice({ type: 'success', text: `Saved to Leads: ${parts.join(', ')}` });
      setPicked(new Set());
      onLeadsSaved && onLeadsSaved();
    } catch (err) {
      setNotice({ type: 'error', text: `Could not save: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className="theme-card-panel" style={{ marginBottom: 0 }}>
        <div className="theme-panel-header" style={{ marginBottom: '1rem' }}>
          <div>
            <div className="theme-panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Building2 size={18} /> CRM Sources</div>
            <div className="theme-panel-sub">Find businesses by category and city, and decision makers from B2B contact databases.</div>
          </div>
        </div>
        {catalogError && <div role="alert" className="jp-alert jp-alert-error"><AlertTriangle size={14} /> {catalogError}</div>}

        <form onSubmit={submit} noValidate>
          <div className="jp-form-grid">
            <div className="jp-span-2">
              <ChipInput id="crm-keywords" label="Business category / keywords" hint={`(Enter or comma, up to ${limits.maxKeywords})`}
                values={keywords} setValues={(v) => { setKeywords(v); if (v.length) clear('keywords'); }} max={limits.maxKeywords}
                placeholder="e.g. software, hospital, real estate, manufacturer" error={errors.keywords} onChangeClear={() => clear('keywords')} />
            </div>
            <div className="jp-span-2">
              <ChipInput id="crm-titles" label="Decision-maker titles" hint="(optional — used by contact databases)"
                values={titles} setValues={setTitles} max={limits.maxTitles} placeholder="e.g. CEO, Founder, CTO, Owner" />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="crm-state">State</label>
              <select id="crm-state" className="theme-form-input" value={state}
                onChange={(e) => { setState(e.target.value); if (e.target.value) clear('state'); }} aria-invalid={!!errors.state}>
                <option value="">Select state…</option>
                {states.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
              {errors.state && <div className="jp-field-error">{errors.state}</div>}
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="crm-city">City <span className="jp-hint">(optional — some directories need it; else the state’s main city is used)</span></label>
              <input id="crm-city" className="theme-form-input" value={city} maxLength={60} placeholder="e.g. Ahmedabad"
                onChange={(e) => { setCity(e.target.value); clear('city'); }} aria-invalid={!!errors.city} />
              {errors.city && <div className="jp-field-error">{errors.city}</div>}
            </div>
            <div className="form-group jp-span-2" ref={menuRef} style={{ position: 'relative' }}>
              <label className="form-label" id="crm-src-label">Sources</label>
              <button type="button" className={`theme-form-input jp-multiselect ${errors.sources ? 'has-error' : ''}`}
                onClick={() => setMenuOpen(!menuOpen)} aria-haspopup="listbox" aria-expanded={menuOpen} aria-labelledby="crm-src-label">
                <span className="jp-multiselect-text">{sourceLabel}</span><ChevronDown size={14} />
              </button>
              {errors.sources && <div className="jp-field-error">{errors.sources}</div>}
              {menuOpen && (
                <div className="jp-menu" role="listbox" aria-multiselectable="true">
                  <label className="jp-menu-item jp-menu-all">
                    <input type="checkbox" checked={allSelected}
                      onChange={() => { const n = allSelected ? new Set() : new Set(available.map(s => s.id)); setSelected(n); if (n.size) clear('sources'); }} />
                    <span>Select all available ({available.length})</span>
                  </label>
                  {GROUPS.map(g => {
                    const items = sources.filter(s => s.status === g.status && (!g.kind || s.kind === g.kind));
                    if (!items.length) return null;
                    return (
                      <div key={g.label}>
                        <div className="jp-menu-group">{g.label}</div>
                        {items.map(s => {
                          const disabled = s.status !== 'available';
                          return (
                            <label key={s.id} className={`jp-menu-item ${disabled ? 'disabled' : ''}`} title={disabled ? s.reason : s.note}>
                              <input type="checkbox" disabled={disabled} checked={selected.has(s.id)} onChange={() => toggle(s.id)} />
                              <span className="jp-menu-text"><span>{s.name}</span><span className="jp-menu-sub">{disabled ? s.reason : s.note}</span></span>
                            </label>
                          );
                        })}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <button type="submit" className="theme-pill-btn primary" disabled={searching || !!catalogError}>
              {searching ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />} {searching ? 'Searching…' : 'Search'}
            </button>
            {searching && <span className="jp-hint">Searching {selected.size} source(s) — can take up to a minute.</span>}
          </div>
        </form>
      </div>

      {notice && (
        <div role="status" className={`jp-alert ${notice.type === 'error' ? 'jp-alert-error' : 'jp-alert-success'}`}>
          {notice.type === 'error' && <AlertTriangle size={14} />}<span style={{ flex: 1 }}>{notice.text}</span>
          <button type="button" className="jp-alert-close" aria-label="Dismiss message" onClick={() => setNotice(null)}><X size={14} /></button>
        </div>
      )}

      {result && (
        <div className="jp-status-row" aria-label="Source results">
          {Object.entries(result.sources || {}).map(([id, st]) => (
            <span key={id} className={`jp-status-chip ${st.status === 'ok' && st.count === 0 ? 'empty' : st.status}`}
              title={(st.errors || []).join('\n') || `${st.count} results in ${st.seconds}s`}>
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
              <input type="text" placeholder="Filter results…" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter results" />
            </div>
            <span className="jp-hint">{visible.length} of {rows.length} · {picked.size} selected</span>
            <div style={{ flex: 1 }} />
            <button type="button" className="theme-pill-btn neutral" onClick={() => downloadCsv(visible)} disabled={!visible.length}><Download size={13} /> Export CSV</button>
            <button type="button" className="theme-pill-btn primary" onClick={save} disabled={!picked.size || saving}>
              {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />} Save to Leads{picked.size ? ` (${picked.size})` : ''}
            </button>
          </div>
          <div className="theme-table-scroll">
            <table className="jp-table">
              <thead>
                <tr>
                  <th style={{ width: 36 }}><input type="checkbox" aria-label="Select all visible results" checked={allVisiblePicked} onChange={togglePickAll} disabled={!visible.length} /></th>
                  <th>Company</th><th>Contact</th><th>Email</th><th>Phone</th><th>Website</th><th>Location</th><th>Source</th><th style={{ width: 40 }} aria-label="Open" />
                </tr>
              </thead>
              <tbody>
                {visible.length === 0 ? (
                  <tr><td colSpan={9} className="jp-empty">{rows.length ? 'No results match this filter.' : 'Nothing found. Try another keyword, a city, or more sources.'}</td></tr>
                ) : visible.map(r => {
                  const k = rowKey(r);
                  return (
                    <tr key={k} className={picked.has(k) ? 'selected' : ''}>
                      <td><input type="checkbox" aria-label={`Select ${r.company || r.contact_name}`} checked={picked.has(k)} onChange={() => togglePick(k)} /></td>
                      <td><div className="jp-cell-title">{r.company || '—'}</div>{(r.category || r.details) && <div className="jp-cell-sub" title={r.details}>{[r.category, r.details].filter(Boolean).join(' · ')}</div>}</td>
                      <td>{r.contact_name ? <><div>{r.contact_name}</div><div className="jp-cell-sub">{r.contact_title}</div></> : '—'}</td>
                      <td>{r.email || '—'}</td>
                      <td>{r.phone || '—'}</td>
                      <td>{r.website ? <a href={r.website} target="_blank" rel="noopener noreferrer">{r.website.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '')}</a> : '—'}</td>
                      <td>{r.location || '—'}</td>
                      <td><span className="theme-source-badge">{r.source}</span></td>
                      <td>{r.url && <a href={r.url} target="_blank" rel="noopener noreferrer" aria-label={`Open ${r.company} on ${r.source}`}><ExternalLink size={14} /></a>}</td>
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
