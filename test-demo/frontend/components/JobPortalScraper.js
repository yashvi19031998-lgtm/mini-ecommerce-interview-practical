'use client';

// Job Portal Scraper: search job portals for companies hiring for given job titles in a state,
// then save the chosen postings as leads (backend: job_portals.py via /api/job-portals/*).

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Briefcase, Search, Loader2, X, ChevronDown, ExternalLink, Save, Download, AlertTriangle } from 'lucide-react';
import { fetchJobPortals, searchJobPortals, saveJobsToLeads } from '../lib/api';

const MAX_TITLE_LENGTH = 80;

const STATUS_LABELS = {
  available: 'Available',
  needs_key: 'Needs API key',
  unavailable: 'Not available'
};

// CSV export of the visible results (no server round-trip)
function downloadCsv(rows) {
  const cols = ['title', 'company', 'location', 'experience', 'salary', 'portal', 'posted_at', 'url', 'skills', 'searched_title'];
  const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const csv = [cols.join(','), ...rows.map(r => cols.map(c => esc(r[c])).join(','))].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `job_portal_results_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function postedLabel(stamp) {
  if (!stamp) return '—';
  const d = new Date(String(stamp).replace(' ', 'T'));
  if (Number.isNaN(d.getTime())) return '—';
  const days = Math.floor((Date.now() - d.getTime()) / 86400000);
  if (days <= 0) return 'Today';
  if (days === 1) return '1 day ago';
  if (days < 60) return `${days} days ago`;
  return d.toLocaleDateString();
}

export default function JobPortalScraper({ showToast, onLeadsSaved }) {
  // Catalog from the backend
  const [portals, setPortals] = useState([]);
  const [states, setStates] = useState([]);
  const [maxTitles, setMaxTitles] = useState(10);
  const [catalogError, setCatalogError] = useState('');

  // Form
  const [titles, setTitles] = useState([]);
  const [titleInput, setTitleInput] = useState('');
  const [state, setState] = useState('');
  const [selectedPortals, setSelectedPortals] = useState(new Set());
  const [portalMenuOpen, setPortalMenuOpen] = useState(false);
  const [formErrors, setFormErrors] = useState({});
  const portalMenuRef = useRef(null);

  // Results
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [result, setResult] = useState(null);
  const [selectedJobs, setSelectedJobs] = useState(new Set());
  const [resultFilter, setResultFilter] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  // Inline feedback (does not depend on the global toast)
  const [notice, setNotice] = useState(null); // { type: 'success' | 'error', text }

  useEffect(() => {
    fetchJobPortals()
      .then(res => {
        setPortals(res.portals || []);
        setStates(res.states || []);
        setMaxTitles(res.maxTitles || 10);
      })
      .catch(err => setCatalogError(err.message || 'Could not load job portals. Is the Python backend running?'));
  }, []);

  // Close the portal dropdown when clicking outside it
  useEffect(() => {
    const onClick = (e) => {
      if (portalMenuRef.current && !portalMenuRef.current.contains(e.target)) setPortalMenuOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const availablePortals = useMemo(() => portals.filter(p => p.status === 'available'), [portals]);
  const allAvailableSelected = availablePortals.length > 0 && availablePortals.every(p => selectedPortals.has(p.id));

  // ---- Job titles (chips) ----
  const addTitles = (raw) => {
    const parts = String(raw).split(',').map(t => t.trim()).filter(Boolean);
    if (!parts.length) return;
    const errors = [];
    const next = [...titles];
    for (const t of parts) {
      if (t.length > MAX_TITLE_LENGTH) { errors.push(`"${t.slice(0, 20)}…" is longer than ${MAX_TITLE_LENGTH} characters`); continue; }
      if (next.some(x => x.toLowerCase() === t.toLowerCase())) continue;
      if (next.length >= maxTitles) { errors.push(`You can add at most ${maxTitles} job titles`); break; }
      next.push(t);
    }
    setTitles(next);
    setTitleInput('');
    setFormErrors(prev => ({ ...prev, titles: errors.join('. ') }));
  };

  const onTitleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addTitles(titleInput);
    } else if (e.key === 'Backspace' && !titleInput && titles.length) {
      setTitles(titles.slice(0, -1));
    }
  };

  // ---- Portals (multi-select) ----
  const clearError = (field) => setFormErrors(prev => (prev[field] ? { ...prev, [field]: '' } : prev));

  const togglePortal = (id) => {
    const next = new Set(selectedPortals);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelectedPortals(next);
    if (next.size) clearError('portals');
  };
  const toggleAllPortals = () => {
    const next = allAvailableSelected ? new Set() : new Set(availablePortals.map(p => p.id));
    setSelectedPortals(next);
    if (next.size) clearError('portals');
  };

  const portalButtonLabel = selectedPortals.size === 0
    ? 'Select job portals'
    : allAvailableSelected
      ? `All available portals (${selectedPortals.size})`
      : portals.filter(p => selectedPortals.has(p.id)).map(p => p.name).join(', ');

  // ---- Search ----
  const validate = () => {
    const pendingTitles = titleInput.trim() ? [...titles, titleInput.trim()] : titles;
    const errors = {};
    if (!pendingTitles.length) errors.titles = 'Enter at least one job title';
    if (!state) errors.state = 'Select a state';
    if (!selectedPortals.size) errors.portals = 'Select at least one job portal';
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    if (titleInput.trim()) addTitles(titleInput);
    if (!validate()) return;
    const searchTitles = titleInput.trim()
      ? [...titles, ...titleInput.split(',').map(t => t.trim()).filter(Boolean)].slice(0, maxTitles)
      : titles;

    setIsSearching(true);
    setSearchError('');
    setResult(null);
    setSelectedJobs(new Set());
    setResultFilter('');
    setNotice(null);
    try {
      const res = await searchJobPortals({ titles: searchTitles, state, portals: [...selectedPortals] });
      setResult(res);
      const msg = `Found ${res.total} jobs across ${Object.keys(res.portals || {}).length} portals`;
      setNotice({ type: 'success', text: msg });
    } catch (err) {
      setSearchError(err.message || 'Search failed');
    } finally {
      setIsSearching(false);
    }
  };

  // ---- Results ----
  const jobs = result?.jobs || [];
  const visibleJobs = useMemo(() => {
    const q = resultFilter.trim().toLowerCase();
    if (!q) return jobs;
    return jobs.filter(j => `${j.title} ${j.company} ${j.location} ${j.portal} ${j.skills}`.toLowerCase().includes(q));
  }, [jobs, resultFilter]);

  const allVisibleSelected = visibleJobs.length > 0 && visibleJobs.every(j => selectedJobs.has(j.url));
  const toggleJob = (url) => {
    const next = new Set(selectedJobs);
    if (next.has(url)) next.delete(url); else next.add(url);
    setSelectedJobs(next);
  };
  const toggleAllJobs = () => {
    const next = new Set(selectedJobs);
    if (allVisibleSelected) visibleJobs.forEach(j => next.delete(j.url));
    else visibleJobs.forEach(j => next.add(j.url));
    setSelectedJobs(next);
  };

  const handleSave = async () => {
    const chosen = jobs.filter(j => selectedJobs.has(j.url));
    if (!chosen.length) return;
    setIsSaving(true);
    try {
      const res = await saveJobsToLeads(chosen);
      const parts = [`${res.added} new lead${res.added === 1 ? '' : 's'}`];
      if (res.updated) parts.push(`${res.updated} updated`);
      if (res.duplicate) parts.push(`${res.duplicate} already saved`);
      if (res.skipped_invalid) parts.push(`${res.skipped_invalid} skipped (no link)`);
      const msg = `Saved to Leads: ${parts.join(', ')}`;
      setNotice({ type: 'success', text: msg });
      setSelectedJobs(new Set());
      onLeadsSaved && onLeadsSaved();
    } catch (err) {
      setNotice({ type: 'error', text: `Could not save: ${err.message}` });
    } finally {
      setIsSaving(false);
    }
  };

  const portalStatusList = Object.entries(result?.portals || {});

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* ---------- Search form ---------- */}
      <div className="theme-card-panel">
        <div className="theme-panel-header" style={{ marginBottom: '1rem' }}>
          <div>
            <div className="theme-panel-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Briefcase size={18} /> Job Portal Scraper
            </div>
            <div className="theme-panel-sub">
              Find companies hiring for these roles in a state. A company that is hiring is a sales lead.
            </div>
          </div>
        </div>

        {catalogError && (
          <div role="alert" className="jp-alert jp-alert-error">
            <AlertTriangle size={14} /> {catalogError}
          </div>
        )}

        <form onSubmit={handleSearch} noValidate>
          <div className="jp-form-grid">
            {/* 1. Job titles */}
            <div className="form-group jp-span-2">
              <label className="form-label" htmlFor="jp-title-input">
                Job Titles <span className="jp-hint">(press Enter or comma to add, up to {maxTitles})</span>
              </label>
              <div className={`jp-chip-input ${formErrors.titles ? 'has-error' : ''}`}>
                {titles.map(t => (
                  <span key={t} className="jp-chip">
                    {t}
                    <button type="button" aria-label={`Remove ${t}`} onClick={() => setTitles(titles.filter(x => x !== t))}>
                      <X size={12} />
                    </button>
                  </span>
                ))}
                <input
                  id="jp-title-input"
                  type="text"
                  value={titleInput}
                  maxLength={MAX_TITLE_LENGTH * 3}
                  placeholder={titles.length ? 'Add another title…' : 'e.g. React Developer, Python Developer'}
                  onChange={(e) => { setTitleInput(e.target.value); if (e.target.value.trim()) clearError('titles'); }}
                  onKeyDown={onTitleKeyDown}
                  onBlur={() => titleInput.trim() && addTitles(titleInput)}
                  aria-invalid={!!formErrors.titles}
                />
              </div>
              {formErrors.titles && <div className="jp-field-error">{formErrors.titles}</div>}
            </div>

            {/* 2. State */}
            <div className="form-group">
              <label className="form-label" htmlFor="jp-state">State</label>
              <select
                id="jp-state"
                className="theme-form-input"
                value={state}
                onChange={(e) => { setState(e.target.value); if (e.target.value) clearError('state'); }}
                aria-invalid={!!formErrors.state}
              >
                <option value="">Select state…</option>
                {states.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
              {formErrors.state && <div className="jp-field-error">{formErrors.state}</div>}
            </div>

            {/* 3. Job portals (multi-select) */}
            <div className="form-group" ref={portalMenuRef} style={{ position: 'relative' }}>
              <label className="form-label" id="jp-portal-label">Job Portals</label>
              <button
                type="button"
                className={`theme-form-input jp-multiselect ${formErrors.portals ? 'has-error' : ''}`}
                onClick={() => setPortalMenuOpen(!portalMenuOpen)}
                aria-haspopup="listbox"
                aria-expanded={portalMenuOpen}
                aria-labelledby="jp-portal-label"
              >
                <span className="jp-multiselect-text">{portalButtonLabel}</span>
                <ChevronDown size={14} />
              </button>
              {formErrors.portals && <div className="jp-field-error">{formErrors.portals}</div>}

              {portalMenuOpen && (
                <div className="jp-menu" role="listbox" aria-multiselectable="true">
                  <label className="jp-menu-item jp-menu-all">
                    <input type="checkbox" checked={allAvailableSelected} onChange={toggleAllPortals} />
                    <span>Select all available ({availablePortals.length})</span>
                  </label>
                  {['available', 'needs_key', 'unavailable'].map(group => {
                    const items = portals.filter(p => p.status === group);
                    if (!items.length) return null;
                    return (
                      <div key={group}>
                        <div className="jp-menu-group">{STATUS_LABELS[group]}</div>
                        {items.map(p => {
                          const disabled = p.status !== 'available';
                          return (
                            <label
                              key={p.id}
                              className={`jp-menu-item ${disabled ? 'disabled' : ''}`}
                              title={disabled ? p.reason : p.note || p.region}
                            >
                              <input
                                type="checkbox"
                                disabled={disabled}
                                checked={selectedPortals.has(p.id)}
                                onChange={() => togglePortal(p.id)}
                              />
                              <span className="jp-menu-text">
                                <span>{p.name}</span>
                                <span className="jp-menu-sub">{disabled ? p.reason : (p.note || p.region)}</span>
                              </span>
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

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '0.5rem' }}>
            <button type="submit" className="theme-pill-btn primary" disabled={isSearching || !!catalogError}>
              {isSearching ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
              {isSearching ? 'Searching…' : 'Search Jobs'}
            </button>
            {isSearching && (
              <span className="jp-hint">Searching {selectedPortals.size} portal(s) — this can take up to a minute.</span>
            )}
          </div>
        </form>
      </div>

      {searchError && (
        <div role="alert" className="jp-alert jp-alert-error"><AlertTriangle size={14} /> {searchError}</div>
      )}

      {notice && (
        <div role="status" className={`jp-alert ${notice.type === 'error' ? 'jp-alert-error' : 'jp-alert-success'}`}>
          {notice.type === 'error' && <AlertTriangle size={14} />}
          <span style={{ flex: 1 }}>{notice.text}</span>
          <button type="button" className="jp-alert-close" aria-label="Dismiss message" onClick={() => setNotice(null)}>
            <X size={14} />
          </button>
        </div>
      )}

      {/* ---------- Per-portal status ---------- */}
      {portalStatusList.length > 0 && (
        <div className="jp-status-row" aria-label="Portal results">
          {portalStatusList.map(([id, st]) => (
            <span
              key={id}
              className={`jp-status-chip ${st.status === 'ok' && st.count === 0 ? 'empty' : st.status}`}
              title={(st.errors || []).join('\n') || `${st.count} jobs in ${st.seconds}s`}
            >
              {st.name}: {st.status === 'skipped' ? 'skipped' : st.status === 'error' ? 'failed' : `${st.count} jobs`}
            </span>
          ))}
        </div>
      )}

      {/* ---------- Results ---------- */}
      {result && (
        <div className="theme-table-container">
          <div className="theme-table-controls">
            <div className="theme-control-search">
              <Search size={14} color="#a3a7ae" />
              <input
                type="text"
                placeholder="Filter results…"
                value={resultFilter}
                onChange={(e) => setResultFilter(e.target.value)}
                aria-label="Filter results"
              />
            </div>
            <span className="jp-hint">{visibleJobs.length} of {jobs.length} jobs · {selectedJobs.size} selected</span>
            <div style={{ flex: 1 }} />
            <button type="button" className="theme-pill-btn neutral" onClick={() => downloadCsv(visibleJobs)} disabled={!visibleJobs.length}>
              <Download size={13} /> Export CSV
            </button>
            <button type="button" className="theme-pill-btn primary" onClick={handleSave} disabled={!selectedJobs.size || isSaving}>
              {isSaving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
              Save to Leads{selectedJobs.size ? ` (${selectedJobs.size})` : ''}
            </button>
          </div>

          <div className="theme-table-scroll">
            <table className="jp-table">
              <thead>
                <tr>
                  <th style={{ width: 36 }}>
                    <input type="checkbox" aria-label="Select all visible jobs" checked={allVisibleSelected} onChange={toggleAllJobs} disabled={!visibleJobs.length} />
                  </th>
                  <th>Job Title</th>
                  <th>Company</th>
                  <th>Location</th>
                  <th>Experience</th>
                  <th>Salary</th>
                  <th>Portal</th>
                  <th>Posted</th>
                  <th style={{ width: 40 }} aria-label="Open job" />
                </tr>
              </thead>
              <tbody>
                {visibleJobs.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="jp-empty">
                      {jobs.length ? 'No jobs match this filter.' : 'No matching jobs found on the selected portals. Try another title, state or more portals.'}
                    </td>
                  </tr>
                ) : visibleJobs.map(j => (
                  <tr key={j.url} className={selectedJobs.has(j.url) ? 'selected' : ''}>
                    <td>
                      <input type="checkbox" aria-label={`Select ${j.title} at ${j.company}`} checked={selectedJobs.has(j.url)} onChange={() => toggleJob(j.url)} />
                    </td>
                    <td>
                      <div className="jp-cell-title">{j.title}</div>
                      {j.skills && <div className="jp-cell-sub" title={j.skills}>{j.skills}</div>}
                    </td>
                    <td>{j.company || '—'}</td>
                    <td>{j.location || '—'}</td>
                    <td>{j.experience || '—'}</td>
                    <td>{j.salary || '—'}</td>
                    <td><span className="theme-source-badge">{j.portal}</span></td>
                    <td>{postedLabel(j.posted_at)}</td>
                    <td>
                      {j.url && (
                        <a href={j.url} target="_blank" rel="noopener noreferrer" aria-label={`Open ${j.title} on ${j.portal}`}>
                          <ExternalLink size={14} />
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
