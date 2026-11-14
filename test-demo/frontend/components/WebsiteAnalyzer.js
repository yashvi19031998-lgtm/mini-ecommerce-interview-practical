'use client';

// Utilities -> Website Analyzer: health score, technology, SEO, security, mobile, contacts and "what to pitch" for
// up to 25 websites (5 per request). Save sites as leads: the problems found go to the lead's website_signals.
// Backend: website_analyzer.py via /api/utilities/website-analyzer; save via /api/bulk-contacts/save (kind websites).

import React, { useMemo, useState } from 'react';
import { Gauge, Loader2, X, Save, Download, AlertTriangle, Search, ChevronDown, ChevronRight, Lightbulb, ExternalLink } from 'lucide-react';
import { analyzeWebsites, bulkSaveContacts } from '../lib/api';

const BATCH = 5;
const MAX_SITES = 25;
const GRADE_CLASS = { Good: 'deep-found', 'Needs work': 'deep-partial', Poor: 'deep-error' };
const yes = (v) => (v ? '✓' : '✗');

function csvDownload(rows) {
  const cols = ['domain', 'score', 'grade', 'platform', 'seconds', 'kb', 'https', 'ssl_days_left', 'mobile', 'title', 'description',
    'analytics', 'ads', 'emails', 'phones', 'problems', 'opportunities'];
  const flat = rows.map(r => ({
    domain: r.domain, score: r.score, grade: r.grade, platform: platform(r), seconds: r.overview.seconds, kb: r.overview.kb,
    https: r.security.https, ssl_days_left: r.security.ssl?.days_left ?? '', mobile: r.mobile.viewport, title: r.seo.title,
    description: r.seo.description, analytics: (r.technology.analytics || []).join('; '), ads: (r.technology.ads || []).join('; '),
    emails: r.contacts.emails.join('; '), phones: r.contacts.phones.join('; '), problems: r.problems.join('; '),
    opportunities: r.opportunities.map(o => o.pitch).join('; ')
  }));
  const cell = (v) => {
    let s = String(v ?? '');
    if (/^[=+\-@]/.test(s)) s = `'${s}`;
    return `"${s.replace(/"/g, '""')}"`;
  };
  const csv = [cols.join(','), ...flat.map(r => cols.map(c => cell(r[c])).join(','))].join('\n');
  const url = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = `website_analysis_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function platform(r) {
  const t = r.technology || {};
  return [...(t.shop || []), ...(t.builder || []), ...(t.cms || [])].join(', ') || (t.framework || []).filter(f => !/jQuery|Bootstrap|Tailwind/.test(f)).join(', ') || 'Custom / unknown';
}

function Section({ title, children }) {
  return (
    <div style={{ minWidth: 0 }}>
      <div className="jp-cell-title" style={{ marginBottom: 4 }}>{title}</div>
      <div className="jp-cell-sub" style={{ lineHeight: 1.6 }}>{children}</div>
    </div>
  );
}

function Details({ r }) {
  const t = r.technology, s = r.seo, sec = r.security;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', gap: 16, padding: '12px 8px' }}>
      <Section title="Overview">
        {r.overview.final_url}<br />HTTP {r.overview.status} · {r.overview.seconds} s (first byte {r.overview.ttfb} s) · {r.overview.kb} KB
        {r.overview.redirects.length > 0 && <><br />Redirects: {r.overview.redirects.length}</>}{r.overview.server && <><br />Server: {r.overview.server}</>}
      </Section>
      <Section title="Technology">
        {Object.keys(t).length === 0 ? 'Nothing recognised' : Object.entries(t).map(([k, v]) => <div key={k}><strong>{k}:</strong> {v.join(', ')}</div>)}
      </Section>
      <Section title="SEO">
        Title ({s.title_length}): {s.title || '—'}<br />Description ({s.description_length}): {s.description ? `${s.description.slice(0, 90)}…` : '—'}<br />
        H1: {s.h1.length ? s.h1.slice(0, 2).join(' | ') : '—'}<br />
        Open Graph {yes(s.open_graph)} · Sitemap {yes(r.seo_files.sitemap)} · robots.txt {yes(r.seo_files.robots_txt)} · noindex {s.noindex ? '⚠ yes' : 'no'}<br />
        Images without alt: {s.images_without_alt}/{s.images}{s.structured_data.length > 0 && <><br />Structured data: {s.structured_data.join(', ')}</>}
      </Section>
      <Section title="Security & mobile">
        HTTPS {yes(sec.https)} · http→https {yes(sec.redirects_http)} · Mobile viewport {yes(r.mobile.viewport)}<br />
        SSL: {sec.ssl?.valid ? `valid until ${sec.ssl.expires} (${sec.ssl.days_left} days, ${sec.ssl.issuer})` : (sec.ssl?.error || '—')}<br />
        {Object.entries(sec.headers).map(([h, ok]) => `${h} ${yes(ok)}`).join(' · ')}{sec.mixed_content > 0 && <><br />⚠ {sec.mixed_content} insecure resources</>}
      </Section>
      <Section title="Contacts on the home page">
        {r.contacts.emails.join(', ') || 'No e-mail'}<br />{r.contacts.phones.join(', ') || 'No phone'}<br />
        Social: {Object.keys(r.contacts.socials).join(', ') || '—'} · WhatsApp link {yes(r.contacts.whatsapp)} · Contact page link {yes(r.contacts.contact_page)}
      </Section>
      <Section title="Problems found">{r.problems.length ? r.problems.map((p, i) => <div key={i}>• {p}</div>) : 'None 🎉'}</Section>
      <Section title="What to pitch">
        {r.opportunities.length ? r.opportunities.map((o, i) => <div key={i}><Lightbulb size={11} style={{ verticalAlign: '-1px' }} /> <strong>{o.pitch}</strong> — {o.why}</div>) : '—'}
      </Section>
    </div>
  );
}

export default function WebsiteAnalyzer({ onLeadsSaved }) {
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  const [progress, setProgress] = useState(null);
  const [results, setResults] = useState(null);
  const [notice, setNotice] = useState(null);
  const [open, setOpen] = useState(new Set());
  const [picked, setPicked] = useState(new Set());
  const [saving, setSaving] = useState(false);
  const [sort, setSort] = useState('score');

  const urls = [...new Set(text.split(/[\s,]+/).map(s => s.trim()).filter(Boolean))];

  const run = async (e) => {
    e.preventDefault();
    if (!urls.length) { setError('Enter at least one website'); return; }
    if (urls.length > MAX_SITES) { setError(`At most ${MAX_SITES} websites at a time`); return; }
    setError(''); setResults([]); setNotice(null); setOpen(new Set()); setPicked(new Set());
    setProgress({ done: 0, total: urls.length });
    const all = [];
    try {
      for (let i = 0; i < urls.length; i += BATCH) {
        const res = await analyzeWebsites(urls.slice(i, i + BATCH));
        all.push(...res.results);
        setResults([...all]);
        setProgress({ done: Math.min(i + BATCH, urls.length), total: urls.length });
      }
      const ok = all.filter(r => r.status === 'ok');
      setNotice({ type: 'success', text: `Analysed ${ok.length} of ${all.length} website${all.length === 1 ? '' : 's'}${ok.length ? ` — average score ${Math.round(ok.reduce((a, r) => a + r.score, 0) / ok.length)}/100` : ''}` });
      if (ok.length === 1) setOpen(new Set([ok[0].domain]));
    } catch (err) {
      setNotice({ type: 'error', text: `Stopped: ${err.message}` });
    } finally {
      setProgress(null);
    }
  };

  const rows = useMemo(() => {
    const list = [...(results || [])];
    if (sort === 'score') list.sort((a, b) => (a.status !== 'ok') - (b.status !== 'ok') || (a.score ?? 999) - (b.score ?? 999));
    else list.sort((a, b) => String(a.domain).localeCompare(String(b.domain)));
    return list;
  }, [results, sort]);
  const okRows = rows.filter(r => r.status === 'ok');
  const toggle = (set, setter, k) => { const n = new Set(set); if (n.has(k)) n.delete(k); else n.add(k); setter(n); };

  const save = async () => {
    const chosen = okRows.filter(r => picked.has(r.domain)).map(r => ({
      company: r.company || r.domain, domain: r.domain, website: r.website, emails: r.contacts.emails, phones: r.contacts.phones,
      socials: r.contacts.socials, address: '', lead_source: 'Utilities (Website Analyzer)',
      website_signals: `Score ${r.score}/100 (${r.grade}): ${r.problems.slice(0, 8).join('; ')}`
    }));
    if (!chosen.length) return;
    setSaving(true);
    try {
      const res = await bulkSaveContacts('websites', chosen);
      const parts = [`${res.added} new lead${res.added === 1 ? '' : 's'}`];
      if (res.updated) parts.push(`${res.updated} updated`);
      if (res.duplicate) parts.push(`${res.duplicate} already saved`);
      setNotice({ type: 'success', text: `Saved to Leads: ${parts.join(', ')} (problems saved in “Website check”)` });
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
            <div className="theme-panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Gauge size={18} /> Website Analyzer</div>
            <div className="theme-panel-sub">Audit client websites for technology stack, SEO, SSL security, performance, and contact details.</div>
          </div>
        </div>
        {error && <div role="alert" className="jp-alert jp-alert-error" style={{ marginBottom: '0.75rem' }}><AlertTriangle size={14} /> {error}</div>}
        <form onSubmit={run} noValidate>
          <div className="form-group">
            <label className="form-label" htmlFor="ut-analyzer-urls">Websites <span className="jp-hint">(one per line, up to {MAX_SITES})</span></label>
            <textarea id="ut-analyzer-urls" className="theme-form-input" rows={4} style={{ height: 'auto', fontFamily: 'monospace' }} value={text}
              onChange={(e) => { setText(e.target.value); setError(''); }} placeholder={'acmefoods.in\nhttps://www.example.co.in'} />
            <div className="jp-hint" style={{ marginTop: 4 }}>{urls.length} website{urls.length === 1 ? '' : 's'}</div>
          </div>
          <button type="submit" className="theme-pill-btn primary" disabled={!!progress}>
            {progress ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
            {progress ? ` Analysing ${progress.done}/${progress.total}…` : ' Analyse'}
          </button>
        </form>
      </div>

      {notice && (
        <div role="status" className={`jp-alert ${notice.type === 'error' ? 'jp-alert-error' : 'jp-alert-success'}`}>
          {notice.type === 'error' && <AlertTriangle size={14} />}<span style={{ flex: 1 }}>{notice.text}</span>
          <button type="button" className="jp-alert-close" aria-label="Dismiss message" onClick={() => setNotice(null)}><X size={14} /></button>
        </div>
      )}

      {results && results.length > 0 && (
        <div className="theme-table-container">
          <div className="theme-table-controls" style={{ flexWrap: 'wrap', gap: 10 }}>
            <select className="theme-form-input" style={{ width: 'auto', height: 34, padding: '0 10px' }} value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort">
              <option value="score">Sort: lowest score first (best prospects)</option>
              <option value="domain">Sort: website A–Z</option>
            </select>
            <span className="jp-hint">{okRows.length} analysed · {picked.size} selected</span>
            <div style={{ flex: 1 }} />
            <button type="button" className="theme-pill-btn neutral" onClick={() => csvDownload(okRows)} disabled={!okRows.length}><Download size={13} /> Export CSV</button>
            <button type="button" className="theme-pill-btn primary" onClick={save} disabled={!picked.size || saving || !!progress}>
              {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />} Save to Leads{picked.size ? ` (${picked.size})` : ''}
            </button>
          </div>
          <div className="theme-table-scroll">
            <table className="jp-table">
              <thead>
                <tr>
                  <th style={{ width: 36 }}><input type="checkbox" aria-label="Select all" checked={okRows.length > 0 && okRows.every(r => picked.has(r.domain))}
                    onChange={(e) => setPicked(e.target.checked ? new Set(okRows.map(r => r.domain)) : new Set())} /></th>
                  <th style={{ width: 28 }} aria-label="Details" /><th>Website</th><th>Score</th><th>Platform</th><th>Speed</th><th>HTTPS · Mobile</th><th>Top problems</th><th>Pitch</th><th style={{ width: 36 }} aria-label="Open" />
                </tr>
              </thead>
              <tbody>
                {rows.map(r => {
                  if (r.status !== 'ok') {
                    return (
                      <tr key={r.input}>
                        <td /><td /><td><div className="jp-cell-title">{r.domain}</div></td>
                        <td colSpan={6}><span className="se-badge deep-error">failed</span> <span className="jp-hint">{r.error}</span></td><td />
                      </tr>
                    );
                  }
                  const isOpen = open.has(r.domain);
                  return (
                    <React.Fragment key={r.domain}>
                      <tr className={picked.has(r.domain) ? 'selected' : ''}>
                        <td><input type="checkbox" aria-label={`Select ${r.domain}`} checked={picked.has(r.domain)} onChange={() => toggle(picked, setPicked, r.domain)} /></td>
                        <td><button type="button" className="jp-alert-close" aria-expanded={isOpen} aria-label={`${isOpen ? 'Hide' : 'Show'} details for ${r.domain}`}
                          onClick={() => toggle(open, setOpen, r.domain)}>{isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}</button></td>
                        <td><div className="jp-cell-title">{r.company || r.domain}</div><div className="jp-cell-sub">{r.domain}</div></td>
                        <td style={{ whiteSpace: 'nowrap' }}><strong>{r.score}</strong>/100 <span className={`se-badge ${GRADE_CLASS[r.grade]}`}>{r.grade}</span></td>
                        <td className="se-wrap">{platform(r)}</td>
                        <td style={{ whiteSpace: 'nowrap' }}>{r.overview.seconds} s</td>
                        <td>{yes(r.security.https)} · {yes(r.mobile.viewport)}</td>
                        <td className="se-wrap">{r.problems.slice(0, 2).join(' · ') || '—'}{r.problems.length > 2 ? ` (+${r.problems.length - 2})` : ''}</td>
                        <td className="se-wrap">{r.opportunities.slice(0, 2).map(o => o.pitch).join(', ') || '—'}</td>
                        <td><a href={r.overview.final_url} target="_blank" rel="noopener noreferrer" aria-label={`Open ${r.domain}`}><ExternalLink size={14} /></a></td>
                      </tr>
                      {isOpen && <tr><td colSpan={10} style={{ background: 'var(--bg-subtle, rgba(0,0,0,0.02))' }}><Details r={r} /></td></tr>}
                    </React.Fragment>
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
