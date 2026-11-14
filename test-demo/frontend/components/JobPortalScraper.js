'use client';

// Job Portal Scraper: search job portals for companies hiring for given job titles in a state,
// then save the chosen postings as leads (backend: job_portals.py via /api/job-portals/*).

import React, { useEffect, useMemo, useState } from 'react';
import { Briefcase, Search, Loader2, X, ExternalLink, Save, Download, AlertTriangle } from 'lucide-react';
import { fetchJobPortals, searchJobPortals, saveJobsToLeads } from '../lib/api';
import CacheNote from './CacheNote';
import MiningForm from './MiningForm';


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
  const [state, setState] = useState('');
  const [selectedPortals, setSelectedPortals] = useState(new Set());
  const [formErrors, setFormErrors] = useState({});

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

  const clearError = (field) => setFormErrors(prev => (prev[field] ? { ...prev, [field]: '' } : prev));

  // ---- Search ----
  const validate = (searchTitles) => {
    const errors = {};
    if (!searchTitles.length) errors.titles = 'Enter at least one job title';
    if (!state) errors.state = 'Select a state';
    if (!selectedPortals.size) errors.portals = 'Select at least one job portal';
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSearch = async (e, final = null, refresh = false) => {
    e?.preventDefault();
    const searchTitles = (final?.keywords || titles).slice(0, maxTitles);
    if (!validate(searchTitles)) return;

    setIsSearching(true);
    setSearchError('');
    setResult(null);
    setSelectedJobs(new Set());
    setResultFilter('');
    setNotice(null);
    try {
      const res = await searchJobPortals({ titles: searchTitles, state, portals: [...selectedPortals], refresh });
      setResult(res);
      const msg = `Found ${res.total} jobs across ${Object.keys(res.portals || {}).length} portals${res.cache?.hit ? ' (saved results)' : ''}`;
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
              Search job portals for hiring companies by role and location.
            </div>
          </div>
        </div>

        {catalogError && (
          <div role="alert" className="jp-alert jp-alert-error">
            <AlertTriangle size={14} /> {catalogError}
          </div>
        )}

        <MiningForm
          idPrefix="jp" onSubmit={handleSearch} busy={isSearching} disabled={!!catalogError}
          submitLabel="Search Jobs" busyHint={`Searching ${selectedPortals.size} portal(s)...`}
          keywords={{ id: 'jp-title-input', label: 'Job Titles', hint: `(press Enter or comma to add, up to ${maxTitles})`,
            values: titles, setValues: setTitles, max: maxTitles, error: formErrors.titles, onClear: () => clearError('titles'),
            placeholder: 'e.g. React Developer, Python Developer' }}
          location={{ mode: 'india', state, setState, states, stateRequired: true, stateError: formErrors.state,
            showCity: false, onClear: clearError }}
          sources={{ label: 'Job Portals', items: portals, selected: selectedPortals, setSelected: setSelectedPortals,
            error: formErrors.portals, onClear: () => clearError('portals'), placeholder: 'Select job portals',
            allLabel: 'All available portals',
            groups: ['available', 'needs_key', 'unavailable'].map(st => ({ status: st, label: STATUS_LABELS[st] })) }}
        />
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
      {result && <CacheNote cache={result.cache} busy={isSearching} onRefresh={() => handleSearch(null, null, true)} />}

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
