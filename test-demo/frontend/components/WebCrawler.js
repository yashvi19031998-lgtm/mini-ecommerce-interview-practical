'use client';

// Web Crawler: four tools (tool prop) that read websites the user names.
//   site      crawl sites -> contacts per page + per site (save sites as leads)
//   links     list pages -> outside company websites -> "Get contacts" (Bulk Website Contacts) -> save
//   keywords  pages of a site that mention given words, with snippets
//   sitemap   every page listed in a site's sitemap, with last-modified dates and sections
// Backend: web_crawler.py via /api/web-crawler/<tool>; contacts + save via /api/bulk-contacts/*.

import React, { useEffect, useMemo, useState } from 'react';
import { Bug, Link2, TextSearch, ListTree, Loader2, X, Save, Download, AlertTriangle, ShieldCheck, Search, ScanSearch, ExternalLink } from 'lucide-react';
import { fetchWebCrawlerOptions, runWebCrawler, bulkWebsiteContacts, bulkSaveContacts } from '../lib/api';
import ChipInput from './ChipInput';

const META = {
  site: { icon: Bug, title: 'Site Crawler', button: 'Crawl',
    sub: 'Crawl one or more websites page by page and collect every email, phone and social link they show.' },
  links: { icon: Link2, title: 'Link Harvester', button: 'Harvest links',
    sub: 'Give list pages — association members, expo exhibitors, “top companies” articles — and get the company websites they link to, then their contacts.' },
  keywords: { icon: TextSearch, title: 'Keyword Page Finder', button: 'Find pages',
    sub: 'Find the pages of a website that mention words like “careers”, “tender”, “franchise” or “distributor wanted”.' },
  sitemap: { icon: ListTree, title: 'Sitemap Explorer', button: 'Read sitemap',
    sub: 'List every page a website publishes in its sitemap, with last-updated dates — see how big a site is and what is new.' }
};
const RULES = 'Obeys each site’s robots.txt and crawl-delay (at least 1 s between pages of a site), opens public addresses only, uses the page cache and an honest User-Agent. Each run stops after 90 s — run again to continue (pages already read come from the cache).';
const KEYWORD_SUGGESTIONS = ['careers', 'tender', 'franchise', 'distributor', 'dealer', 'vendor registration', 'contact', 'pricing', 'hiring', 'partner'];

function csvDownload(rows, cols, name) {
  const cell = (v) => {
    let s = Array.isArray(v) ? v.join('; ') : (v && typeof v === 'object' ? Object.entries(v).map(([k, x]) => `${k}: ${x}`).join('; ') : String(v ?? ''));
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

const short = (u) => String(u || '').replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '');

export default function WebCrawler({ tool, onLeadsSaved }) {
  const meta = META[tool] || META.site;
  const Icon = meta.icon;
  const [opts, setOpts] = useState(null);
  const [urls, setUrls] = useState('');
  const [keywords, setKeywords] = useState([]);
  const [maxPages, setMaxPages] = useState(25);
  const [depth, setDepth] = useState(2);
  const [follow, setFollow] = useState(1);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [notice, setNotice] = useState(null);
  const [view, setView] = useState('sites');
  const [filter, setFilter] = useState('');
  const [picked, setPicked] = useState(new Set());
  const [contacts, setContacts] = useState({});      // link harvester: domain -> contact result
  const [progress, setProgress] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => { fetchWebCrawlerOptions().then(setOpts).catch(err => setError(err.message || 'Could not load. Is the Python backend running?')); }, []);

  const urlList = urls.split(/[\s,]+/).map(s => s.trim()).filter(Boolean);
  const maxUrls = tool === 'sitemap' ? 1 : tool === 'keywords' ? 3 : (opts?.maxSeeds || 5);

  const run = async (e) => {
    e.preventDefault();
    if (!urlList.length) { setError(tool === 'links' ? 'Paste at least one list page' : 'Enter a website'); return; }
    if (urlList.length > maxUrls) { setError(`At most ${maxUrls} address${maxUrls === 1 ? '' : 'es'} per run`); return; }
    const kws = tool === 'keywords' ? [...keywords, ...(document.getElementById('wc-keywords')?.value || '').split(',').map(s => s.trim()).filter(Boolean)] : [];
    if (tool === 'keywords' && !kws.length) { setError('Enter at least one keyword'); return; }
    setError(''); setBusy(true); setResult(null); setNotice(null); setPicked(new Set()); setContacts({}); setFilter('');
    const params = { urls: urlList };
    if (tool === 'site' || tool === 'keywords') Object.assign(params, { max_pages: maxPages, depth });
    if (tool === 'keywords') params.keywords = [...new Set(kws)];
    if (tool === 'links') params.follow_pages = follow;
    try {
      const res = await runWebCrawler(tool, params);
      setResult(res);
      setView(tool === 'site' ? 'sites' : 'rows');
      const n = res.results.length;
      const text = tool === 'site' ? `Crawled ${n} page${n === 1 ? '' : 's'} on ${res.sites.length} site${res.sites.length === 1 ? '' : 's'}`
        : tool === 'links' ? `Found ${n} company website${n === 1 ? '' : 's'} on ${res.pages} page${res.pages === 1 ? '' : 's'}`
          : tool === 'keywords' ? `${res.matched_pages} of ${res.pages} pages mention a keyword`
            : `${n} page${n === 1 ? '' : 's'} in ${res.sitemaps.length} sitemap${res.sitemaps.length === 1 ? '' : 's'}`;
      setNotice({ type: n ? 'success' : 'info', text });
    } catch (err) {
      setError(err.message || 'Failed');
    } finally {
      setBusy(false);
    }
  };

  // Link harvester: contacts for the chosen (or all) websites, 10 per request
  const getContacts = async () => {
    const targets = (result?.results || []).filter(r => (picked.size ? picked.has(r.domain) : true) && !contacts[r.domain]);
    if (!targets.length) return;
    const batch = opts?.bulkBatch || 10;
    setProgress({ done: 0, total: targets.length }); setNotice(null);
    let found = 0;
    try {
      for (let i = 0; i < targets.length; i += batch) {
        const res = await bulkWebsiteContacts(targets.slice(i, i + batch).map(r => r.website));
        const add = {};
        res.results.forEach(c => { add[c.domain] = c; if (c.status === 'found') found += 1; });
        setContacts(prev => ({ ...prev, ...add }));
        setProgress({ done: Math.min(i + batch, targets.length), total: targets.length });
      }
      setNotice({ type: 'success', text: `Contacts found on ${found} of ${targets.length} websites` });
    } catch (err) {
      setNotice({ type: 'error', text: `Stopped: ${err.message}` });
    } finally {
      setProgress(null);
    }
  };

  const linkRows = useMemo(() => (result?.results || []).map(r => {
    const c = contacts[r.domain];
    return c ? { ...r, emails: c.emails, phones: c.phones, socials: c.socials, address: c.address, contact_status: c.status,
      company: r.company !== r.domain ? r.company : (c.company || r.company), contact_error: c.error } : r;
  }), [result, contacts]);

  const rows = tool === 'links' ? linkRows : tool === 'site' && view === 'sites' ? (result?.sites || []) : (result?.results || []);
  const visible = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(r => JSON.stringify([r.url, r.domain, r.company, r.title, r.keyword, r.section, r.anchors]).toLowerCase().includes(q));
  }, [rows, filter]);

  const savableKey = (r) => r.domain || r.site;
  const canSave = tool === 'site' ? view === 'sites' : tool === 'links';
  const isSavable = (r) => (tool === 'site' ? (r.emails?.length || r.phones?.length) : r.contact_status === 'found');
  const togglePick = (k) => { const n = new Set(picked); if (n.has(k)) n.delete(k); else n.add(k); setPicked(n); };

  const save = async () => {
    const leadSource = tool === 'site' ? 'Web Crawler (Site Crawler)' : 'Web Crawler (Link Harvester)';
    const chosen = rows.filter(r => picked.has(savableKey(r)) && isSavable(r)).map(r => ({ ...r, domain: savableKey(r), lead_source: leadSource }));
    if (!chosen.length) { setNotice({ type: 'error', text: tool === 'links' ? 'Select websites that have contacts (run “Get contacts” first)' : 'Select sites that have contacts' }); return; }
    setSaving(true);
    try {
      const res = await bulkSaveContacts('websites', chosen);
      const parts = [`${res.added} new lead${res.added === 1 ? '' : 's'}`];
      if (res.updated) parts.push(`${res.updated} updated`);
      if (res.duplicate) parts.push(`${res.duplicate} already saved`);
      setNotice({ type: 'success', text: `Saved to Leads: ${parts.join(', ')}` });
      setPicked(new Set());
      onLeadsSaved && onLeadsSaved();
    } catch (err) {
      setNotice({ type: 'error', text: `Could not save: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const exportIt = () => {
    const cols = tool === 'site' ? (view === 'sites' ? ['site', 'website', 'company', 'emails', 'phones', 'socials', 'pages'] : ['url', 'depth', 'status', 'title', 'emails', 'phones', 'socials'])
      : tool === 'links' ? ['company', 'domain', 'website', 'anchors', 'found_on', 'links', 'emails', 'phones', 'socials', 'contact_status']
        : tool === 'keywords' ? ['keyword', 'count', 'url', 'title', 'snippets'] : ['url', 'section', 'lastmod', 'changefreq', 'priority'];
    csvDownload(visible, cols, `crawler_${tool}`);
  };

  const select = (id, label, value, set, choices, fmt) => (
    <div className="form-group">
      <label className="form-label" htmlFor={id}>{label}</label>
      <select id={id} className="theme-form-input" value={value} onChange={(e) => set(Number(e.target.value))}>
        {choices.map(c => <option key={c} value={c}>{fmt ? fmt(c) : c}</option>)}
      </select>
    </div>
  );

  const head = {
    site: view === 'sites' ? ['Site', 'Emails', 'Phones', 'Social', 'Pages'] : ['Page', 'Depth', 'Emails', 'Phones', 'Result'],
    links: ['Company website', 'Found as', 'Emails', 'Phones', 'Contacts'],
    keywords: ['Keyword', 'Page', 'Mentions', 'Where'],
    sitemap: ['Page', 'Section', 'Last updated', 'Priority']
  }[tool];

  const cells = (r) => {
    if (tool === 'site' && view === 'sites') {
      return (<>
        <td><div className="jp-cell-title">{r.company || r.site}</div><div className="jp-cell-sub"><a href={r.website} target="_blank" rel="noopener noreferrer">{r.site}</a></div></td>
        <td className="se-wrap">{(r.emails || []).join(', ') || '—'}</td>
        <td className="se-wrap">{(r.phones || []).join(', ') || '—'}</td>
        <td className="se-wrap">{Object.keys(r.socials || {}).join(', ') || '—'}</td>
        <td>{r.pages}</td>
      </>);
    }
    if (tool === 'site') {
      return (<>
        <td className="se-wrap"><a href={r.url} target="_blank" rel="noopener noreferrer">{short(r.url)}</a>{r.title && <div className="jp-cell-sub">{r.title}</div>}</td>
        <td>{r.depth}</td>
        <td className="se-wrap">{(r.emails || []).join(', ') || '—'}</td>
        <td className="se-wrap">{(r.phones || []).join(', ') || '—'}</td>
        <td><span className={`se-badge ${r.status === 'ok' ? 'deep-found' : 'deep-none'}`}>{r.status === 'robots' ? 'robots.txt / blocked' : r.status}</span></td>
      </>);
    }
    if (tool === 'links') {
      return (<>
        <td><div className="jp-cell-title">{r.company}</div><div className="jp-cell-sub"><a href={r.website} target="_blank" rel="noopener noreferrer">{r.domain}</a>{r.government ? ' · government' : ''}</div></td>
        <td className="se-wrap">{(r.anchors || []).join(' · ') || '—'}<div className="jp-cell-sub">on {short(r.found_on)}</div></td>
        <td className="se-wrap">{(r.emails || []).join(', ') || '—'}</td>
        <td className="se-wrap">{(r.phones || []).join(', ') || '—'}</td>
        <td>{r.contact_status ? <span className={`se-badge ${r.contact_status === 'found' ? 'deep-found' : 'deep-none'}`} title={r.contact_error || ''}>{r.contact_status}</span> : <span className="jp-hint">not checked</span>}</td>
      </>);
    }
    if (tool === 'keywords') {
      return (<>
        <td><span className="se-badge deep-found">{r.keyword}</span></td>
        <td className="se-wrap"><a href={r.url} target="_blank" rel="noopener noreferrer">{short(r.url)}</a>{r.title && <div className="jp-cell-sub">{r.title}</div>}</td>
        <td>{r.count}{r.in_url ? ' · in URL' : ''}</td>
        <td className="se-wrap">{(r.snippets || []).map((s, i) => <div key={i} className="jp-cell-sub">{s}</div>)}</td>
      </>);
    }
    return (<>
      <td className="se-wrap"><a href={r.url} target="_blank" rel="noopener noreferrer">{short(r.url)}</a></td>
      <td>{r.section}</td>
      <td style={{ whiteSpace: 'nowrap' }}>{(r.lastmod || '—').slice(0, 10)}</td>
      <td>{r.priority || '—'}</td>
    </>);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className="theme-card-panel" style={{ marginBottom: 0 }}>
        <div className="theme-panel-header" style={{ marginBottom: '1rem' }}>
          <div>
            <div className="theme-panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Icon size={18} /> {meta.title}</div>
            <div className="theme-panel-sub">{meta.sub}</div>
          </div>
        </div>
        <div className="jp-alert se-alert-info" role="note" style={{ marginBottom: '0.75rem' }}><ShieldCheck size={14} /><span>{RULES}</span></div>
        {error && <div role="alert" className="jp-alert jp-alert-error" style={{ marginBottom: '0.75rem' }}><AlertTriangle size={14} /> {error}</div>}
        <form onSubmit={run} noValidate>
          <div className="jp-form-grid">
            <div className="form-group jp-span-2">
              <label className="form-label" htmlFor={`wc-${tool}-urls`}>
                {tool === 'links' ? 'List pages' : tool === 'sitemap' ? 'Website' : 'Websites'}{' '}
                <span className="jp-hint">({maxUrls === 1 ? 'one address' : `one per line, up to ${maxUrls}`})</span>
              </label>
              {maxUrls === 1 ? (
                <input id={`wc-${tool}-urls`} className="theme-form-input" value={urls} onChange={(e) => { setUrls(e.target.value); setError(''); }} placeholder="e.g. mokobara.com" />
              ) : (
                <textarea id={`wc-${tool}-urls`} className="theme-form-input" rows={4} style={{ height: 'auto', fontFamily: 'monospace' }} value={urls}
                  onChange={(e) => { setUrls(e.target.value); setError(''); }}
                  placeholder={tool === 'links' ? 'https://www.example-association.in/members\nhttps://www.expo-site.in/exhibitors' : 'acmefoods.in\nhttps://www.example.co.in'} />
              )}
            </div>
            {tool === 'keywords' && (
              <div className="jp-span-2">
                <ChipInput id="wc-keywords" label="Keywords" hint={`(Enter or comma, up to ${opts?.maxKeywords || 10})`} values={keywords} setValues={setKeywords}
                  max={opts?.maxKeywords || 10} placeholder="e.g. careers, tender, franchise" suggestions={KEYWORD_SUGGESTIONS} />
              </div>
            )}
            {(tool === 'site' || tool === 'keywords') && opts && (<>
              {select(`wc-${tool}-pages`, 'Pages to read (all sites together)', maxPages, setMaxPages, opts.pageChoices)}
              {select(`wc-${tool}-depth`, 'Depth (clicks from the start page)', depth, setDepth, opts.depthChoices)}
            </>)}
            {tool === 'links' && select('wc-links-follow', 'Follow “Next” pages', follow, setFollow, [1, 2, 3, 5], (n) => (n === 1 ? 'Only the given page' : `Up to ${n} pages`))}
          </div>
          <button type="submit" className="theme-pill-btn primary" disabled={busy || !opts || !!progress}>
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />} {busy ? 'Working… (up to 90 s)' : meta.button}
          </button>
        </form>
      </div>

      {notice && (
        <div role="status" className={`jp-alert ${notice.type === 'error' ? 'jp-alert-error' : notice.type === 'info' ? 'se-alert-info' : 'jp-alert-success'}`}>
          {notice.type === 'error' && <AlertTriangle size={14} />}<span style={{ flex: 1 }}>{notice.text}</span>
          <button type="button" className="jp-alert-close" aria-label="Dismiss message" onClick={() => setNotice(null)}><X size={14} /></button>
        </div>
      )}
      {result?.notes?.length > 0 && <ul className="se-errors">{result.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}
      {tool === 'sitemap' && result?.sections?.length > 0 && (
        <div className="jp-status-row" aria-label="Sections">
          {result.sections.map(s => <span key={s.section} className="jp-status-chip ok">{s.section}: {s.pages}</span>)}
          {result.newest && <span className="jp-hint">Newest update {result.newest.slice(0, 10)} · oldest {result.oldest.slice(0, 10)}</span>}
        </div>
      )}
      {tool === 'keywords' && result?.keywords && (
        <div className="jp-status-row" aria-label="Keywords">
          {Object.entries(result.keywords).map(([k, n]) => <span key={k} className={`jp-status-chip ${n ? 'ok' : 'empty'}`}>{k}: {n} page{n === 1 ? '' : 's'}</span>)}
        </div>
      )}

      {result && (
        <div className="theme-table-container">
          <div className="theme-table-controls" style={{ flexWrap: 'wrap', gap: 10 }}>
            <div className="theme-control-search">
              <Search size={14} color="#a3a7ae" />
              <input type="text" placeholder="Filter…" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter results" />
            </div>
            {tool === 'site' && (
              <select className="theme-form-input" style={{ width: 'auto', height: 32 }} value={view} onChange={(e) => { setView(e.target.value); setPicked(new Set()); }} aria-label="View">
                <option value="sites">By site ({result.sites.length})</option>
                <option value="pages">By page ({result.results.length})</option>
              </select>
            )}
            <span className="jp-hint">{visible.length} of {rows.length}{canSave ? ` · ${picked.size} selected` : ''}</span>
            <div style={{ flex: 1 }} />
            {tool === 'links' && (
              <button type="button" className="theme-pill-btn neutral" onClick={getContacts} disabled={busy || !!progress || !rows.length}>
                {progress ? <Loader2 size={13} className="animate-spin" /> : <ScanSearch size={13} />}
                {progress ? ` Contacts ${progress.done}/${progress.total}…` : ` Get contacts ${picked.size ? 'selected' : 'all'} (${(picked.size ? rows.filter(r => picked.has(r.domain)) : rows).filter(r => !contacts[r.domain]).length})`}
              </button>
            )}
            <button type="button" className="theme-pill-btn neutral" onClick={exportIt} disabled={!visible.length}><Download size={13} /> Export CSV</button>
            {canSave && (
              <button type="button" className="theme-pill-btn primary" onClick={save} disabled={!picked.size || saving || !!progress}>
                {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />} Save to Leads{picked.size ? ` (${picked.size})` : ''}
              </button>
            )}
          </div>
          <div className="theme-table-scroll">
            <table className="jp-table">
              <thead>
                <tr>
                  {canSave && <th style={{ width: 36 }}><input type="checkbox" aria-label="Select all"
                    checked={visible.length > 0 && visible.every(r => picked.has(savableKey(r)))}
                    onChange={(e) => setPicked(e.target.checked ? new Set(visible.map(savableKey)) : new Set())} /></th>}
                  {head.map(h => <th key={h}>{h}</th>)}
                  <th style={{ width: 36 }} aria-label="Open" />
                </tr>
              </thead>
              <tbody>
                {visible.length === 0 ? (
                  <tr><td colSpan={head.length + 2} className="jp-empty">{rows.length ? 'Nothing matches this filter.' : 'Nothing found.'}</td></tr>
                ) : visible.slice(0, 1000).map((r, i) => {
                  const k = savableKey(r) || r.url;
                  return (
                    <tr key={`${k}-${r.url || ''}-${r.keyword || ''}-${i}`} className={canSave && picked.has(k) ? 'selected' : ''}>
                      {canSave && <td><input type="checkbox" aria-label={`Select ${r.company || k}`} checked={picked.has(k)} onChange={() => togglePick(k)} /></td>}
                      {cells(r)}
                      <td><a href={r.url || r.website} target="_blank" rel="noopener noreferrer" aria-label="Open"><ExternalLink size={14} /></a></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {visible.length > 1000 && <div className="jp-hint" style={{ padding: 8 }}>Showing the first 1,000 — use Filter or Export CSV for all {visible.length}.</div>}
          </div>
        </div>
      )}
    </div>
  );
}
