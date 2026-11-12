'use client';

// Domain Tools (tool prop):
//   age        Domain Age & Expiry - RDAP dates, registrar, DNS host; flags new / expiring domains
//   dns        Email & DNS Checker - mail provider, SPF, DMARC, DNS host, website address; problems + pitches
//   new        New Domains Finder - newly registered domains containing keywords (WhoisDS daily list, gTLDs)
//   available  Domain Availability - name.tld registered or not, with variants
// Backend: domain_tools.py via /api/domain-tools/<tool>; save via /api/bulk-contacts/save (kind websites).

import React, { useEffect, useMemo, useState } from 'react';
import { CalendarClock, MailSearch, Sparkles, CheckSquare, Loader2, X, Save, Download, AlertTriangle, ShieldCheck, Search, ExternalLink } from 'lucide-react';
import { fetchDomainToolOptions, runDomainTool, bulkSaveContacts } from '../lib/api';
import ChipInput from './ChipInput';

const META = {
  age: { icon: CalendarClock, title: 'Domain Age & Expiry', button: 'Check',
    sub: 'When was a domain registered, when does it expire, who is the registrar and where is its DNS — new and expiring domains are flagged.',
    note: 'Uses RDAP, the domain registries’ official public service. Owner contact details are never read.' },
  dns: { icon: MailSearch, title: 'Email & DNS Checker', button: 'Check',
    sub: 'Who runs a company’s e-mail (Google Workspace, Zoho, Microsoft 365, hosting mail), is SPF / DMARC set, where is the DNS and website.',
    note: 'Reads public DNS records only. Mailboxes are never contacted.' },
  new: { icon: Sparkles, title: 'New Domains Finder', button: 'Find',
    sub: 'Domains registered in the last days that contain your keywords — brand-new businesses that will need a website, e-mail and marketing.',
    note: 'Source: WhoisDS free daily list of newly registered domains (.com, .net, .org, .online, .store… — it has no .in). Each day is downloaded once.' },
  available: { icon: CheckSquare, title: 'Domain Availability', button: 'Check',
    sub: 'Is a name free as .com / .in / .co.in and more? Also suggests close variants.',
    note: '“Available” means the registry has no record right now. Premium or reserved names can still be refused or cost more — confirm at a registrar.' }
};

function csvDownload(rows, cols, name) {
  const cell = (v) => {
    let s = Array.isArray(v) ? v.join('; ') : String(v ?? '');
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

const Badge = ({ cls, children, title }) => <span className={`se-badge ${cls}`} title={title || ''}>{children}</span>;

export default function DomainTools({ tool, onLeadsSaved }) {
  const meta = META[tool] || META.age;
  const Icon = meta.icon;
  const [opts, setOpts] = useState(null);
  const [text, setText] = useState('');
  const [keywords, setKeywords] = useState([]);
  const [days, setDays] = useState(3);
  const [tlds, setTlds] = useState(tool === 'available' ? ['com', 'in', 'co.in'] : []);
  const [variants, setVariants] = useState(true);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [notice, setNotice] = useState(null);
  const [filter, setFilter] = useState('');
  const [picked, setPicked] = useState(new Set());
  const [saving, setSaving] = useState(false);

  useEffect(() => { fetchDomainToolOptions().then(setOpts).catch(err => setError(err.message || 'Could not load. Is the Python backend running?')); }, []);

  const toggleTld = (t) => setTlds(prev => (prev.includes(t) ? prev.filter(x => x !== t) : [...prev, t]));

  const run = async (e) => {
    e.preventDefault();
    let params;
    if (tool === 'age' || tool === 'dns') {
      const list = text.split(/[\s,;]+/).map(s => s.trim()).filter(Boolean);
      if (!list.length) { setError('Enter at least one domain, website or e-mail address'); return; }
      params = { domains: list };
    } else if (tool === 'new') {
      const kws = [...keywords, ...(document.getElementById('dt-new-keywords')?.value || '').split(',').map(s => s.trim()).filter(Boolean)];
      if (!kws.length) { setError('Enter at least one keyword'); return; }
      params = { keywords: [...new Set(kws)], days, tlds };
    } else {
      if (!text.trim()) { setError('Enter a business or brand name'); return; }
      if (!tlds.length) { setError('Choose at least one ending'); return; }
      params = { name: text.trim(), tlds, variants };
    }
    setError(''); setBusy(true); setResult(null); setNotice(null); setPicked(new Set()); setFilter('');
    try {
      const res = await runDomainTool(tool, params);
      setResult(res);
      const n = res.results.length;
      const text2 = tool === 'available' ? `${res.results.filter(r => r.available === 'available').length} of ${n} names available`
        : tool === 'new' ? `${n} new domain${n === 1 ? '' : 's'} found in ${res.days_read.length} day${res.days_read.length === 1 ? '' : 's'}`
          : `Checked ${n} domain${n === 1 ? '' : 's'}`;
      setNotice({ type: 'success', text: text2 + (res.invalid?.length ? ` — skipped (not a domain): ${res.invalid.join(', ')}` : '') });
    } catch (err) {
      setError(err.message || 'Failed');
    } finally {
      setBusy(false);
    }
  };

  const rows = useMemo(() => {
    const list = result?.results || [];
    const q = filter.trim().toLowerCase();
    if (!q) return list;
    return list.filter(r => JSON.stringify(r).toLowerCase().includes(q));
  }, [result, filter]);
  const canSave = tool === 'age' || tool === 'dns' || tool === 'new';
  const savable = (r) => (tool === 'new' ? true : tool === 'age' ? r.registered : r.status === 'ok' && r.web_ip?.length);
  const togglePick = (k) => { const n = new Set(picked); if (n.has(k)) n.delete(k); else n.add(k); setPicked(n); };

  const signalOf = (r) => {
    if (tool === 'age') return `Domain registered ${r.created || '?'} (${r.age || '?'}), expires ${r.expires || '?'}, registrar ${r.registrar || '?'}, DNS ${r.dns_host || '?'}${r.flags?.length ? ` — ${r.flags.join(', ')}` : ''}`;
    if (tool === 'dns') return `E-mail: ${r.mail || 'none'}; SPF ${r.spf ? 'yes' : 'no'}; DMARC ${r.dmarc_policy || 'none'}${r.problems?.length ? ` — ${r.problems.join('; ')}` : ''}`;
    return `New domain registered ${r.registered_on} (keyword: ${r.keyword})`;
  };

  const save = async () => {
    const chosen = rows.filter(r => picked.has(r.domain) && savable(r)).map(r => ({
      company: r.domain, domain: r.domain, website: `https://${r.domain}`, emails: [], phones: [], socials: {}, address: '',
      lead_source: 'Domain Tools', website_signals: signalOf(r)
    }));
    if (!chosen.length) return;
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
    const cols = {
      age: ['domain', 'registered', 'created', 'age', 'expires', 'days_left', 'registrar', 'dns_host', 'nameservers', 'status', 'flags', 'note'],
      dns: ['domain', 'status', 'mail', 'mx', 'spf', 'dmarc', 'dmarc_policy', 'dns_host', 'nameservers', 'web_ip', 'problems', 'pitches'],
      new: ['domain', 'registered_on', 'tld', 'keyword'],
      available: ['domain', 'available', 'created', 'expires', 'registrar', 'note']
    }[tool];
    csvDownload(rows, cols, `domains_${tool}`);
  };

  const head = {
    age: ['Domain', 'Registered', 'Expires', 'Registrar · DNS', 'Flags'],
    dns: ['Domain', 'E-mail', 'SPF · DMARC', 'DNS · Website', 'Problems → pitch'],
    new: ['Domain', 'Registered on', 'Keyword', 'Ending'],
    available: ['Domain', 'Status', 'Registered', 'Expires · Registrar']
  }[tool];

  const cells = (r) => {
    if (tool === 'age') {
      return (<>
        <td className="jp-cell-title">{r.domain}</td>
        <td style={{ whiteSpace: 'nowrap' }}>{r.registered === false ? '—' : r.created || '?'}{r.age && <div className="jp-cell-sub">{r.age} old</div>}</td>
        <td style={{ whiteSpace: 'nowrap' }}>{r.expires || '—'}{r.days_left != null && <div className="jp-cell-sub">{r.days_left} days left</div>}</td>
        <td className="se-wrap">{r.registrar || '—'}<div className="jp-cell-sub">{r.dns_host}</div></td>
        <td>{(r.flags || []).map(f => <Badge key={f} cls={/Expire|hold/.test(f) ? 'deep-error' : /New/.test(f) ? 'deep-found' : 'deep-none'}>{f}</Badge>)}
          {r.note && <div className="jp-cell-sub">{r.note}</div>}</td>
      </>);
    }
    if (tool === 'dns') {
      return (<>
        <td className="jp-cell-title">{r.domain}</td>
        <td className="se-wrap">{r.status !== 'ok' ? <Badge cls="deep-error">{r.status}</Badge> : (r.mail || <Badge cls="deep-error">no e-mail</Badge>)}
          {r.mx?.length > 0 && <div className="jp-cell-sub">{r.mx[0]}</div>}</td>
        <td>{r.status === 'ok' ? <>SPF {r.spf ? '✓' : '✗'} · DMARC {r.dmarc_policy ? <strong>{r.dmarc_policy}</strong> : '✗'}</> : '—'}</td>
        <td className="se-wrap">{r.dns_host || '—'}<div className="jp-cell-sub">{(r.web_ip || []).join(', ') || 'no website address'}</div></td>
        <td className="se-wrap">{(r.problems || []).map((p, i) => <div key={i} className="jp-cell-sub">• {p}</div>)}
          {(r.pitches || []).map((p, i) => <div key={`p${i}`}><strong>→ {p}</strong></div>)}{!r.problems?.length && !r.pitches?.length && '✓ looks fine'}</td>
      </>);
    }
    if (tool === 'new') {
      return (<>
        <td className="jp-cell-title">{r.domain}</td><td>{r.registered_on}</td><td><Badge cls="deep-found">{r.keyword}</Badge></td><td>.{r.tld}</td>
      </>);
    }
    return (<>
      <td className="jp-cell-title">{r.domain}{r.requested && <span className="jp-hint"> · your name</span>}</td>
      <td><Badge cls={r.available === 'available' ? 'deep-found' : r.available === 'taken' ? 'deep-error' : 'deep-none'} title={r.note}>{r.available}</Badge></td>
      <td>{r.created || '—'}</td>
      <td className="se-wrap">{r.expires || '—'}{r.registrar && <div className="jp-cell-sub">{r.registrar}</div>}{r.note && <div className="jp-cell-sub">{r.note}</div>}</td>
    </>);
  };

  const tldChoices = tool === 'new' ? (opts?.newTlds || []) : (opts?.availTlds || []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className="theme-card-panel" style={{ marginBottom: 0 }}>
        <div className="theme-panel-header" style={{ marginBottom: '1rem' }}>
          <div>
            <div className="theme-panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Icon size={18} /> {meta.title}</div>
            <div className="theme-panel-sub">{meta.sub}</div>
          </div>
        </div>
        <div className="jp-alert se-alert-info" role="note" style={{ marginBottom: '0.75rem' }}><ShieldCheck size={14} /><span>{meta.note}</span></div>
        {error && <div role="alert" className="jp-alert jp-alert-error" style={{ marginBottom: '0.75rem' }}><AlertTriangle size={14} /> {error}</div>}
        <form onSubmit={run} noValidate>
          {(tool === 'age' || tool === 'dns') && (
            <div className="form-group">
              <label className="form-label" htmlFor={`dt-${tool}-input`}>Domains <span className="jp-hint">(domains, websites or e-mail addresses — one per line, up to {opts?.maxDomains || 50})</span></label>
              <textarea id={`dt-${tool}-input`} className="theme-form-input" rows={5} style={{ height: 'auto', fontFamily: 'monospace' }} value={text}
                onChange={(e) => { setText(e.target.value); setError(''); }} placeholder={'acmefoods.in\nhttps://www.example.co.in\nravi@acme.com'} />
            </div>
          )}
          {tool === 'available' && (
            <div className="form-group">
              <label className="form-label" htmlFor="dt-available-name">Business / brand name</label>
              <input id="dt-available-name" className="theme-form-input" maxLength={40} value={text} onChange={(e) => { setText(e.target.value); setError(''); }} placeholder="e.g. Acme Bakes" />
            </div>
          )}
          {tool === 'new' && (
            <div className="jp-form-grid">
              <div className="jp-span-2">
                <ChipInput id="dt-new-keywords" label="Keywords in the domain name" hint={`(at least 3 letters, up to ${opts?.maxNewKeywords || 5})`}
                  values={keywords} setValues={setKeywords} max={opts?.maxNewKeywords || 5} placeholder="e.g. bakery, realty, infra, clinic" />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="dt-new-days">Registered in the last</label>
                <select id="dt-new-days" className="theme-form-input" value={days} onChange={(e) => setDays(Number(e.target.value))}>
                  {(opts?.dayChoices || [1, 3, 7]).map(d => <option key={d} value={d}>{d} day{d === 1 ? '' : 's'}</option>)}
                </select>
              </div>
            </div>
          )}
          {(tool === 'new' || tool === 'available') && (
            <div className="form-group">
              <div className="form-label">Endings {tool === 'new' && <span className="jp-hint">(none selected = all)</span>}</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
                {tldChoices.map(t => (
                  <label key={t} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 13 }}>
                    <input type="checkbox" checked={tlds.includes(t)} onChange={() => toggleTld(t)} aria-label={`.${t}`} />.{t}
                  </label>
                ))}
                {tool === 'available' && (
                  <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 13, marginLeft: 12 }}>
                    <input type="checkbox" checked={variants} onChange={() => setVariants(!variants)} /> Suggest variants (get…, my…, …india, …online)
                  </label>
                )}
              </div>
            </div>
          )}
          <button type="submit" className="theme-pill-btn primary" disabled={busy || !opts}>
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />} {busy ? 'Working…' : meta.button}
          </button>
        </form>
      </div>

      {notice && (
        <div role="status" className={`jp-alert ${notice.type === 'error' ? 'jp-alert-error' : 'jp-alert-success'}`}>
          {notice.type === 'error' && <AlertTriangle size={14} />}<span style={{ flex: 1 }}>{notice.text}</span>
          <button type="button" className="jp-alert-close" aria-label="Dismiss message" onClick={() => setNotice(null)}><X size={14} /></button>
        </div>
      )}
      {result?.notes?.length > 0 && <ul className="se-errors">{result.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}

      {result && (
        <div className="theme-table-container">
          <div className="theme-table-controls" style={{ flexWrap: 'wrap', gap: 10 }}>
            <div className="theme-control-search">
              <Search size={14} color="#a3a7ae" />
              <input type="text" placeholder="Filter…" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter results" />
            </div>
            <span className="jp-hint">{rows.length} of {result.results.length}{canSave ? ` · ${picked.size} selected` : ''}</span>
            <div style={{ flex: 1 }} />
            <button type="button" className="theme-pill-btn neutral" onClick={exportIt} disabled={!rows.length}><Download size={13} /> Export CSV</button>
            {canSave && (
              <button type="button" className="theme-pill-btn primary" onClick={save} disabled={!picked.size || saving}>
                {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />} Save to Leads{picked.size ? ` (${picked.size})` : ''}
              </button>
            )}
          </div>
          <div className="theme-table-scroll">
            <table className="jp-table">
              <thead>
                <tr>
                  {canSave && <th style={{ width: 36 }}><input type="checkbox" aria-label="Select all"
                    checked={rows.filter(savable).length > 0 && rows.filter(savable).every(r => picked.has(r.domain))}
                    onChange={(e) => setPicked(e.target.checked ? new Set(rows.filter(savable).map(r => r.domain)) : new Set())} /></th>}
                  {head.map(h => <th key={h}>{h}</th>)}
                  <th style={{ width: 36 }} aria-label="Open" />
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr><td colSpan={head.length + 2} className="jp-empty">{result.results.length ? 'Nothing matches this filter.' : 'Nothing found.'}</td></tr>
                ) : rows.map(r => (
                  <tr key={r.domain} className={picked.has(r.domain) ? 'selected' : ''}>
                    {canSave && <td><input type="checkbox" aria-label={`Select ${r.domain}`} disabled={!savable(r)} checked={picked.has(r.domain)} onChange={() => togglePick(r.domain)} /></td>}
                    {cells(r)}
                    <td>{(tool !== 'available' || r.available === 'taken') && <a href={`https://${r.domain}`} target="_blank" rel="noopener noreferrer" aria-label={`Open ${r.domain}`}><ExternalLink size={14} /></a>}</td>
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
