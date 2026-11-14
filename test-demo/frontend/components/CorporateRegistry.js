'use client';

// Data Extraction -> Corporate Registries: Company Scraper, PVT LTD Scraper, GST No Scraper (mode prop).
// Backend: corporate_registries.py via /api/corporate-registries/*; Deep Search via /api/search-engine/deep.

import React, { useEffect, useMemo, useState } from 'react';
import {
  Landmark, BadgeCheck, Receipt, Search, Loader2, X, ExternalLink, Save, Download, AlertTriangle, ScanSearch,
  FileText
} from 'lucide-react';
import {
  fetchCorporateRegistryOptions, searchCorporateRegistries, fetchCompanyDetails, saveCorporateRegistryResults, runDeepSearch
} from '../lib/api';
import CacheNote from './CacheNote';
import MiningForm from './MiningForm';

const META = {
  company: { icon: Landmark, title: 'Company Scraper',
    sub: 'Search registered companies from the MCA corporate database by industry, location, and status.' },
  pvtltd: { icon: BadgeCheck, title: 'PVT LTD Scraper',
    sub: 'Search private limited company registrations, filings, and incorporation records.' },
  gst: { icon: Receipt, title: 'GST No Scraper',
    sub: 'Lookup verified GSTIN records and business tax registration details.' }
};
const DEEP_LABELS = { found: 'Found', partial: 'Website only', none: 'Nothing found', error: 'Failed' };
const rowKey = (r) => `${r.source_id}|${r.cin || r.gstin || ''}|${r.url}|${r.company}`;

function downloadCsv(rows, name, isGst) {
  const cols = isGst
    ? ['company', 'gstin', 'gst_valid', 'gst_problem', 'gst_state', 'entity', 'pan', 'phone', 'location', 'category', 'details', 'url', 'in_leads']
    : ['company', 'cin', 'status', 'company_kind', 'listed', 'year', 'incorporated', 'capital', 'nic_code', 'activity', 'roc',
      'address', 'website', 'email', 'phone', 'url', 'in_leads'];
  const cell = (v) => {
    let s = String(v ?? '');
    if (/^[=+\-@]/.test(s)) s = `'${s}`;
    return `"${s.replace(/"/g, '""')}"`;
  };
  const csv = [cols.join(','), ...rows.map(r => cols.map(c => cell(r[c])).join(','))].join('\n');
  const url = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = `${name}_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function Select({ id, label, value, onChange, options }) {
  return (
    <div className="form-group">
      <label className="form-label" htmlFor={id}>{label}</label>
      <select id={id} className="theme-form-input" value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map(o => <option key={String(o.id)} value={o.id}>{o.name}</option>)}
      </select>
    </div>
  );
}

export default function CorporateRegistry({ mode, onLeadsSaved }) {
  const meta = META[mode] || META.company;
  const Icon = meta.icon;
  const isGst = mode === 'gst';
  const [opts, setOpts] = useState(null);
  const [optsError, setOptsError] = useState('');
  const [keywords, setKeywords] = useState([]);
  const [audience, setAudience] = useState([]);
  const [state, setState] = useState(isGst ? 'All India' : 'Gujarat');
  const [city, setCity] = useState('');
  const [companyType, setCompanyType] = useState('');
  const [status, setStatus] = useState('Active');
  const [age, setAge] = useState(mode === 'pvtltd' ? 'A' : '');
  const [industry, setIndustry] = useState('');
  const [pages, setPages] = useState(1);
  const [sellers, setSellers] = useState(10);
  const [gstTab, setGstTab] = useState('find');
  const [gstText, setGstText] = useState('');
  const [errors, setErrors] = useState({});
  const [searching, setSearching] = useState(false);
  const [result, setResult] = useState(null);
  const [notice, setNotice] = useState(null);
  const [picked, setPicked] = useState(new Set());
  const [filter, setFilter] = useState('');
  const [extra, setExtra] = useState({});      // company details by row key
  const [deep, setDeep] = useState({});
  const [run, setRun] = useState(null);        // { kind: 'details' | 'deep', done, total }
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchCorporateRegistryOptions()
      .then(setOpts)
      .catch(err => setOptsError(err.message || 'Could not load options. Is the Python backend running?'));
  }, []);

  const clear = (f) => setErrors(prev => (prev[f] ? { ...prev, [f]: '' } : prev));
  const place = city.trim() || (state && state !== 'All India' ? state : '');
  const checkMode = isGst && gstTab === 'check';

  const runSearch = async (params) => {
    setSearching(true); setResult(null); setPicked(new Set()); setExtra({}); setDeep({}); setFilter(''); setNotice(null);
    try {
      const res = await searchCorporateRegistries(params);
      setResult(res);
      const st = Object.values(res.sources || {});
      if (!res.total && st.length && st.every(x => x.status !== 'ok')) {
        setNotice({ type: 'error', text: 'Nothing found — see the reason below.' });
        return;
      }
      const what = params.mode === 'gst_check' ? 'GST number' : isGst ? 'seller' : 'compan';
      const plural = params.mode === 'gst_check' || isGst ? (res.total === 1 ? '' : 's') : (res.total === 1 ? 'y' : 'ies');
      setNotice({ type: res.total ? 'success' : 'info', text: `Found ${res.total} ${what}${plural}${res.cache?.hit ? ' (saved results)' : ''}` });
    } catch (err) {
      setNotice({ type: 'error', text: err.message || 'Search failed' });
    } finally {
      setSearching(false);
    }
  };

  const submit = (e, final = null, refresh = false) => {
    e?.preventDefault();
    const kws = final?.keywords || keywords;
    const aud = final?.audience || audience;
    const errs = {};
    if (city && !/^[A-Za-z .'-]{1,60}$/.test(city.trim())) errs.city = 'City must be letters only (max 60 characters)';
    if (isGst) {
      if (!kws.length) errs.keywords = 'Enter at least one product or category';
    } else if (!kws.length && state === 'All India' && !city.trim() && !industry) {
      errs.city = 'Choose a state, city or industry — or search by company name';
    } else if (!kws.length && industry && state !== 'All India' && !city.trim()) {
      errs.city = 'The register lists industries per city — enter a city, or choose All India';
    }
    setErrors(errs);
    if (Object.keys(errs).length) return;
    const params = isGst
      ? { mode: 'gst_find', keywords: kws, audience: aud, state, city: city.trim(), max_sellers: sellers, refresh }
      : { mode, keywords: kws, audience: aud, state, city: city.trim(), company_type: mode === 'pvtltd' ? 'PTC' : companyType,
        status, age, industry, pages, refresh };
    runSearch(params);
  };

  const submitCheck = (e) => {
    e.preventDefault();
    const list = gstText.split(/[\s,;]+/).map(s => s.trim()).filter(Boolean);
    if (!list.length) { setErrors({ gstins: 'Paste at least one GST number' }); return; }
    if (list.length > (opts?.maxGstins || 100)) { setErrors({ gstins: `Check at most ${opts?.maxGstins || 100} GST numbers at a time` }); return; }
    setErrors({});
    runSearch({ mode: 'gst_check', gstins: list });
  };

  const rows = useMemo(() => (result?.results || []).map(r => {
    const k = rowKey(r);
    const x = extra[k];
    const d = deep[k];
    let out = r;
    if (x && x.status === 'ok') {
      out = { ...out, incorporated: x.incorporated, roc: x.roc, activity: x.activity, company_class: x.class,
        website: out.website || x.website || '', details_status: 'ok' };
    } else if (x) out = { ...out, details_status: 'error', details_error: x.error };
    if (d) {
      out = { ...out, email: out.email || (d.emails || []).join(', '), phone: out.phone || (d.phones || [])[0] || '',
        website: out.website || d.website || '', email_guess: d.email_guess || '', deep_status: d.status, deep_steps: d.steps || [] };
    }
    return out;
  }), [result, extra, deep]);
  const visible = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return rows.filter(r => !q || `${r.company} ${r.cin} ${r.gstin} ${r.address} ${r.location} ${r.activity || ''}`.toLowerCase().includes(q));
  }, [rows, filter]);
  const allVisiblePicked = visible.length > 0 && visible.every(r => picked.has(rowKey(r)));
  const togglePick = (k) => { const n = new Set(picked); if (n.has(k)) n.delete(k); else n.add(k); setPicked(n); };
  const togglePickAll = () => {
    const n = new Set(picked);
    if (allVisiblePicked) visible.forEach(r => n.delete(rowKey(r))); else visible.forEach(r => n.add(rowKey(r)));
    setPicked(n);
  };
  const base = picked.size ? rows.filter(r => picked.has(rowKey(r))) : rows;
  const detailTargets = useMemo(() => (isGst ? [] : base.filter(r => !extra[rowKey(r)])), [base, extra, isGst]);
  const deepTargets = useMemo(() => (checkMode ? [] : base.filter(r => r.company && !r.email && !deep[rowKey(r)])), [base, deep, checkMode]);

  const runBatches = async (kind, targets, batch, call, store, label) => {
    if (!targets.length) return;
    setRun({ kind, done: 0, total: targets.length }); setNotice(null);
    let ok = 0, failed = false;
    for (let i = 0; i < targets.length; i += batch) {
      const chunk = targets.slice(i, i + batch);
      try {
        const res = await call(chunk);
        const add = {};
        (res.results || []).forEach(d => { add[d.key] = d; if (d.status === 'ok' || d.status === 'found') ok += 1; });
        store(prev => ({ ...prev, ...add }));
      } catch (err) {
        failed = true;
        setNotice({ type: 'error', text: `${label} stopped: ${err.message}` });
        break;
      }
      setRun({ kind, done: Math.min(i + batch, targets.length), total: targets.length });
    }
    setRun(null);
    if (!failed) setNotice({ type: 'success', text: `${label} finished: ${ok} of ${targets.length}` });
  };

  const runDetails = () => runBatches('details', detailTargets, opts?.detailsBatch || 10,
    (chunk) => fetchCompanyDetails(chunk.map(r => ({ key: rowKey(r), url: r.url }))), setExtra, 'Company details');
  const runDeep = () => runBatches('deep', deepTargets, opts?.deepBatch || 10,
    (chunk) => runDeepSearch({ items: chunk.map(r => ({ key: rowKey(r), url: r.url, website: r.website || '', company: r.company, kind: 'listing' })), engine: 'auto', place }),
    setDeep, 'Deep Search (contact details found)');

  const save = async () => {
    const chosen = rows.filter(r => picked.has(rowKey(r)) && r.company && r.url);
    if (!chosen.length) return;
    setSaving(true);
    try {
      const res = await saveCorporateRegistryResults(chosen);
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

  const busy = searching || !!run;
  const resultIsGst = isGst;
  const resultIsCheck = result?.query?.mode === 'gst_check';

  const companyFilters = !isGst && opts && (
    <>
      {mode === 'company' && <Select id={`cr-${mode}-type`} label="Company type" value={companyType} onChange={setCompanyType} options={opts.companyTypes} />}
      <Select id={`cr-${mode}-status`} label="Status" value={status} onChange={setStatus} options={opts.statuses} />
      <Select id={`cr-${mode}-age`} label="Company age" value={age} onChange={setAge} options={opts.ages} />
      <Select id={`cr-${mode}-industry`} label="Industry" value={industry} onChange={setIndustry} options={opts.industries} />
      <Select id={`cr-${mode}-pages`} label="Pages (30 companies each)" value={pages} onChange={(v) => setPages(Number(v))}
        options={(opts.pageChoices || [1]).map(n => ({ id: n, name: `${n} page${n === 1 ? '' : 's'} (up to ${n * 30})` }))} />
    </>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className="theme-card-panel" style={{ marginBottom: 0 }}>
        <div className="theme-panel-header" style={{ marginBottom: '1rem' }}>
          <div>
            <div className="theme-panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Icon size={18} /> {meta.title}</div>
            <div className="theme-panel-sub">{meta.sub}</div>
          </div>
        </div>
        {optsError && <div role="alert" className="jp-alert jp-alert-error"><AlertTriangle size={14} /> {optsError}</div>}

        {isGst && (
          <div className="jp-status-row" role="tablist" aria-label="GST mode" style={{ marginBottom: '0.75rem' }}>
            {[['find', 'Find GST numbers'], ['check', 'Check GST numbers']].map(([id, label]) => (
              <button key={id} type="button" role="tab" aria-selected={gstTab === id}
                className={`theme-pill-btn ${gstTab === id ? 'primary' : 'neutral'}`} onClick={() => { setGstTab(id); setErrors({}); }}>{label}</button>
            ))}
          </div>
        )}

        {checkMode ? (
          <form onSubmit={submitCheck} noValidate>
            <div className="form-group">
              <label className="form-label" htmlFor="cr-gstins">GST numbers <span className="jp-hint">(one per line or comma separated, up to {opts?.maxGstins || 100})</span></label>
              <textarea id="cr-gstins" className="theme-form-input" rows={5} value={gstText} onChange={(e) => { setGstText(e.target.value); setErrors({}); }}
                placeholder="24ACHPG0469J1ZO&#10;27AAACR5055K1Z7" style={{ fontFamily: 'monospace', height: 'auto' }} aria-invalid={!!errors.gstins} />
              {errors.gstins && <div className="jp-field-error">{errors.gstins}</div>}
            </div>
            <button type="submit" className="theme-pill-btn primary" disabled={busy || !opts}>
              {searching ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />} {searching ? 'Checking…' : 'Check'}
            </button>
          </form>
        ) : (
          <MiningForm
            idPrefix={`cr-${mode}`} onSubmit={submit} busy={searching} disabled={!!run || !!optsError || !opts}
            busyHint={isGst ? 'Reads the IndiaMART category page, then each seller page (2 s apart).' : 'Reading the register pages (2 s apart).'}
            keywords={isGst
              ? { label: 'Product / category', hint: '(IndiaMART category name, up to 5)', values: keywords, setValues: setKeywords,
                max: opts?.maxNames || 5, error: errors.keywords, onClear: () => clear('keywords'), placeholder: 'e.g. bakery products',
                suggestions: ['bakery products', 'packaging material', 'industrial machinery'] }
              : { label: 'Company name', hint: '(optional — search by name instead of the lists)', values: keywords, setValues: setKeywords,
                max: opts?.maxNames || 5, onClear: () => clear('keywords'), placeholder: 'e.g. Infosys, SJ Polycraft' }}
            audience={{ values: audience, setValues: setAudience, max: 5 }}
            extra={isGst ? (opts && <Select id="cr-gst-sellers" label="Sellers to check" value={sellers} onChange={(v) => setSellers(Number(v))}
              options={(opts.sellerChoices || [10]).map(n => ({ id: n, name: `${n} sellers` }))} />) : companyFilters}
            location={{ mode: 'india', state, setState, states: opts?.states || [], stateRequired: false,
              city, setCity, cityError: errors.city, onClear: clear, cityHint: '(optional)' }}
          />
        )}
      </div>

      {notice && (
        <div role="status" className={`jp-alert ${notice.type === 'error' ? 'jp-alert-error' : notice.type === 'info' ? 'se-alert-info' : 'jp-alert-success'}`}>
          {notice.type === 'error' && <AlertTriangle size={14} />}<span style={{ flex: 1 }}>{notice.text}</span>
          <button type="button" className="jp-alert-close" aria-label="Dismiss message" onClick={() => setNotice(null)}><X size={14} /></button>
        </div>
      )}
      {result && !resultIsCheck && <CacheNote cache={result.cache} busy={busy} onRefresh={() => submit(null, null, true)} />}
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
            {!resultIsGst && (
              <button type="button" className="theme-pill-btn neutral" onClick={runDetails} disabled={busy || !detailTargets.length}
                title="Opens each company page: incorporation date, ROC, activity, website">
                {run?.kind === 'details' ? <Loader2 size={13} className="animate-spin" /> : <FileText size={13} />}
                {run?.kind === 'details' ? ` Details ${run.done}/${run.total}…` : ` Company details ${picked.size ? 'selected' : ''} (${detailTargets.length})`}
              </button>
            )}
            {!resultIsCheck && (
              <button type="button" className="theme-pill-btn neutral" onClick={runDeep} disabled={busy || !deepTargets.length}
                title="Looks for each company's own website by name, then reads it for email / phone">
                {run?.kind === 'deep' ? <Loader2 size={13} className="animate-spin" /> : <ScanSearch size={13} />}
                {run?.kind === 'deep' ? ` Deep Search ${run.done}/${run.total}…` : ` Deep Search ${picked.size ? 'selected' : 'missing'} (${deepTargets.length})`}
              </button>
            )}
            <button type="button" className="theme-pill-btn neutral" onClick={() => downloadCsv(visible, isGst ? 'gst_numbers' : mode === 'pvtltd' ? 'pvt_ltd_companies' : 'companies', resultIsGst)} disabled={!visible.length}><Download size={13} /> Export CSV</button>
            {!resultIsCheck && (
              <button type="button" className="theme-pill-btn primary" onClick={save} disabled={!picked.size || saving || busy}>
                {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />} Save to Leads{picked.size ? ` (${picked.size})` : ''}
              </button>
            )}
          </div>
          <div className="theme-table-scroll">
            <table className="jp-table">
              <thead>
                {resultIsGst ? (
                  <tr>
                    <th style={{ width: 36 }}><input type="checkbox" aria-label="Select all visible results" checked={allVisiblePicked} onChange={togglePickAll} disabled={!visible.length} /></th>
                    {!resultIsCheck && <th>Business</th>}<th>GSTIN</th><th>Check</th><th>State</th><th>Entity</th>{!resultIsCheck && <><th>Phone</th><th>Email / Website</th><th>Status</th><th style={{ width: 40 }} aria-label="Open" /></>}
                  </tr>
                ) : (
                  <tr>
                    <th style={{ width: 36 }}><input type="checkbox" aria-label="Select all visible results" checked={allVisiblePicked} onChange={togglePickAll} disabled={!visible.length} /></th>
                    <th>Company</th><th>CIN</th><th>Status</th><th>Type · Year</th><th>Capital</th><th>Activity</th><th>Email / Website</th><th>Lead</th><th style={{ width: 40 }} aria-label="Open" />
                  </tr>
                )}
              </thead>
              <tbody>
                {visible.length === 0 ? (
                  <tr><td colSpan={10} className="jp-empty">{rows.length ? 'No results match this filter.' : 'Nothing found. Try another city, remove a filter, or search by name.'}</td></tr>
                ) : visible.map(r => {
                  const k = rowKey(r);
                  const contact = (
                    <td className="se-wrap">
                      {r.email || (r.email_guess ? <span className="se-guess" title="Guessed - not found on the website. Not saved as the email.">{r.email_guess} (guess)</span> : '')}
                      {r.website ? <div><a href={r.website} target="_blank" rel="noopener noreferrer">{r.website.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '')}</a></div> : (!r.email && !r.email_guess ? '—' : null)}
                    </td>
                  );
                  const badges = (
                    <td>
                      {r.in_leads && <span className="se-badge inleads" title={r.match ? `Matches ${r.match}` : ''}>In leads</span>}
                      {r.deep_status && <span className={`se-badge deep-${r.deep_status}`} title={(r.deep_steps || []).join(' | ')}>{DEEP_LABELS[r.deep_status] || r.deep_status}</span>}
                      {!r.in_leads && !r.deep_status && <span className="jp-hint">New</span>}
                    </td>
                  );
                  const check = <td><input type="checkbox" aria-label={`Select ${r.company || r.gstin}`} checked={picked.has(k)} onChange={() => togglePick(k)} /></td>;
                  if (resultIsGst) {
                    return (
                      <tr key={k} className={picked.has(k) ? 'selected' : ''}>
                        {check}
                        {!resultIsCheck && <td><div className="jp-cell-title">{r.company}</div><div className="jp-cell-sub se-snippet">{[r.details, r.location].filter(Boolean).join(' · ')}</div></td>}
                        <td style={{ fontFamily: 'monospace', whiteSpace: 'nowrap' }}>{r.gstin || '—'}</td>
                        <td>{r.gst_valid ? <span className={`se-badge ${r.gst_valid === 'Valid' ? 'deep-found' : 'deep-error'}`} title={r.gst_problem}>{r.gst_valid}</span> : <span className="jp-hint" title={r.gst_problem}>{r.gst_problem ? 'Not shown' : '—'}</span>}</td>
                        <td>{r.gst_state || '—'}</td>
                        <td className="se-wrap">{r.entity || '—'}{r.pan ? <div className="jp-cell-sub">PAN {r.pan}</div> : null}</td>
                        {!resultIsCheck && (
                          <>
                            <td style={{ whiteSpace: 'nowrap' }}>{r.phone || '—'}</td>
                            {contact}{badges}
                            <td><a href={r.url} target="_blank" rel="noopener noreferrer" aria-label={`Open ${r.company} seller page`}><ExternalLink size={14} /></a></td>
                          </>
                        )}
                      </tr>
                    );
                  }
                  return (
                    <tr key={k} className={picked.has(k) ? 'selected' : ''}>
                      {check}
                      <td><div className="jp-cell-title">{r.company}</div><div className="jp-cell-sub se-snippet" title={r.address}>{r.address}</div></td>
                      <td style={{ fontFamily: 'monospace', whiteSpace: 'nowrap', fontSize: 12 }}>{r.cin || '—'}</td>
                      <td>{r.status ? <span className={`se-badge ${r.status === 'Active' ? 'deep-found' : 'deep-none'}`}>{r.status}</span> : <span className="jp-hint">—</span>}</td>
                      <td className="se-wrap">{r.company_kind || '—'}<div className="jp-cell-sub">{r.incorporated ? `Inc. ${r.incorporated}` : r.year ? `Since ${r.year}` : ''}{r.listed ? ` · ${r.listed}` : ''}</div></td>
                      <td style={{ whiteSpace: 'nowrap' }}>{r.capital || '—'}</td>
                      <td className="se-wrap">{r.activity || (r.details_status === 'error' ? <span className="jp-hint" title={r.details_error}>Details failed</span> : <span className="jp-hint">NIC {r.nic_code || '—'}</span>)}{r.roc ? <div className="jp-cell-sub">{r.roc}</div> : null}</td>
                      {contact}{badges}
                      <td><a href={r.url} target="_blank" rel="noopener noreferrer" aria-label={`Open ${r.company} on ZaubaCorp`}><ExternalLink size={14} /></a></td>
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
