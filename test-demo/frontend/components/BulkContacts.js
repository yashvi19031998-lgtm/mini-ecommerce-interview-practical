'use client';

// Bulk Contacts: four tools for lists the user already has (tool prop):
//   websites  many URLs -> email / phone / socials from each site (10 per request, progress shown)
//   emails    verify e-mail addresses (syntax, typos, disposable, role, MX) - no mailbox probing
//   phones    clean / classify phone numbers (+91 format, mobile / landline, fake, duplicates)
//   import    CSV upload -> map columns -> duplicates vs file and Leads -> save the new ones
// Backend: bulk_contacts.py via /api/bulk-contacts/*.

import React, { useEffect, useMemo, useState } from 'react';
import { Globe2, MailCheck, PhoneCall, FileUp, Loader2, X, Save, Download, AlertTriangle, ShieldCheck, Search, Upload } from 'lucide-react';
import {
  fetchBulkContactsOptions, bulkWebsiteContacts, bulkVerifyEmails, bulkCleanPhones, bulkImportPreview, bulkImportCheck, bulkSaveContacts
} from '../lib/api';

const META = {
  websites: { icon: Globe2, title: 'Bulk Website Contacts',
    sub: 'Paste many website addresses — get the email, phone and social links from each site.',
    note: 'Opens each site’s homepage and contact pages (public addresses only, cached, honest User-Agent). Directory and social pages are skipped — use their own menus.' },
  emails: { icon: MailCheck, title: 'Bulk Email Verifier',
    sub: 'Check a list of e-mail addresses before you send: format, typos, disposable, role and whether the domain accepts mail.',
    note: 'Checks the domain’s mail (MX) record in DNS. Mailboxes are not “probed” over SMTP — that is unreliable and gets your sending IP blacklisted. “Valid” means the domain accepts e-mail.' },
  phones: { icon: PhoneCall, title: 'Bulk Phone Cleaner',
    sub: 'Turn a messy list of numbers into clean +91 numbers — mobile / landline, fake and duplicate numbers marked.',
    note: 'Works offline. Paste numbers one per line, or whole text — numbers are found in it.' },
  import: { icon: FileUp, title: 'Contact Import & Dedupe',
    sub: 'Upload a CSV, match its columns, see duplicates (inside the file and against your Leads), then save only the new contacts.',
    note: 'CSV files up to 5 MB / 5,000 rows. Excel: File → Save As → CSV first. Nothing is sent to anyone.' }
};
const STATUS_CLASS = { valid: 'deep-found', found: 'deep-found', new: 'deep-found', risky: 'deep-partial', unknown: 'deep-none',
  invalid: 'deep-error', error: 'deep-error', duplicate: 'deep-none', in_leads: 'inleads', none: 'deep-none', skipped: 'deep-none' };
const FIELD_LABELS = { company_name: 'Company', full_name: 'Contact person', email: 'Email', mobile_number: 'Phone',
  website: 'Website', location: 'City / address', description: 'Notes' };

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

const Badge = ({ status, title }) => <span className={`se-badge ${STATUS_CLASS[status] || 'deep-none'}`} title={title || ''}>{String(status).replace('_', ' ')}</span>;

export default function BulkContacts({ tool, onLeadsSaved }) {
  const meta = META[tool] || META.websites;
  const Icon = meta.icon;
  const [opts, setOpts] = useState(null);
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(null);
  const [rows, setRows] = useState(null);
  const [counts, setCounts] = useState(null);
  const [notice, setNotice] = useState(null);
  const [filter, setFilter] = useState('All');
  const [picked, setPicked] = useState(new Set());
  const [saving, setSaving] = useState(false);
  // import
  const [csvText, setCsvText] = useState('');
  const [fileName, setFileName] = useState('');
  const [preview, setPreview] = useState(null);
  const [mapping, setMapping] = useState({});
  const [sourceLabel, setSourceLabel] = useState('');

  useEffect(() => { fetchBulkContactsOptions().then(setOpts).catch(err => setError(err.message || 'Could not load. Is the Python backend running?')); }, []);

  const reset = () => { setRows(null); setCounts(null); setNotice(null); setFilter('All'); setPicked(new Set()); };
  const lines = text.split(/\n/).map(s => s.trim()).filter(Boolean);

  const runWebsites = async () => {
    const urls = [...new Set(text.split(/[\s,;]+/).map(s => s.trim()).filter(Boolean))];
    if (!urls.length) { setError('Paste at least one website'); return; }
    if (urls.length > 200) { setError('At most 200 websites at a time'); return; }
    const batch = opts?.maxUrlsPerCall || 10;
    setError(''); reset(); setBusy(true); setProgress({ done: 0, total: urls.length });
    const all = [];
    try {
      for (let i = 0; i < urls.length; i += batch) {
        const res = await bulkWebsiteContacts(urls.slice(i, i + batch));
        all.push(...res.results);
        setRows([...all]);
        setProgress({ done: Math.min(i + batch, urls.length), total: urls.length });
      }
      const found = all.filter(r => r.status === 'found').length;
      setNotice({ type: 'success', text: `Checked ${all.length} website${all.length === 1 ? '' : 's'}: contacts found on ${found}` });
    } catch (err) {
      setNotice({ type: 'error', text: `Stopped: ${err.message}` });
    } finally {
      setBusy(false); setProgress(null);
    }
  };

  const runSimple = async (call, what) => {
    if (!lines.length) { setError(`Paste at least one ${what}`); return; }
    setError(''); reset(); setBusy(true);
    try {
      const res = await call();
      setRows(res.results); setCounts(res.counts);
      setNotice({ type: 'success', text: `Checked ${res.results.length} ${what}${res.results.length === 1 ? '' : 's'}` });
    } catch (err) {
      setError(err.message || 'Failed');
    } finally {
      setBusy(false);
    }
  };

  const onFile = (e) => {
    const f = e.target.files?.[0];
    e.target.value = '';
    if (!f) return;
    setError(''); setPreview(null); reset();
    if (!/\.(csv|txt)$/i.test(f.name)) { setError('Choose a .csv file (Excel: File → Save As → CSV)'); return; }
    if (f.size > (opts?.maxCsvBytes || 5242880)) { setError('The file is larger than 5 MB — split it into smaller files'); return; }
    const reader = new FileReader();
    reader.onload = async () => {
      const content = String(reader.result || '');
      setCsvText(content); setFileName(f.name); setSourceLabel(f.name.replace(/\.[^.]+$/, '').slice(0, 60));
      setBusy(true);
      try {
        const p = await bulkImportPreview(content);
        setPreview(p); setMapping(p.mapping);
      } catch (err) {
        setError(err.message || 'Could not read the file');
      } finally {
        setBusy(false);
      }
    };
    reader.onerror = () => setError('Could not read the file');
    reader.readAsText(f);
  };

  const runCheck = async () => {
    setError(''); reset(); setBusy(true);
    try {
      const res = await bulkImportCheck(csvText, mapping, sourceLabel);
      setRows(res.results); setCounts(res.counts);
      setPicked(new Set(res.results.filter(r => r.status === 'new').map(r => r.line)));
      setNotice({ type: 'success', text: `${res.counts.new} new contact${res.counts.new === 1 ? '' : 's'} ready to save — ${res.counts.in_leads} already in Leads, ${res.counts.duplicate} repeated in the file, ${res.counts.invalid} unusable` });
    } catch (err) {
      setError(err.message || 'Check failed');
    } finally {
      setBusy(false);
    }
  };

  const keyOf = (r) => (tool === 'import' ? r.line : tool === 'websites' ? r.domain : r.input);
  const statuses = useMemo(() => ['All', ...new Set((rows || []).map(r => (r.in_leads && tool !== 'import' ? 'in leads' : r.status)))], [rows, tool]);
  const visible = useMemo(() => (rows || []).filter(r => filter === 'All' || (filter === 'in leads' ? r.in_leads : r.status === filter && !(r.in_leads && tool !== 'import'))), [rows, filter, tool]);
  const canSave = tool === 'import' || tool === 'websites';
  const savable = (r) => (tool === 'import' ? r.status === 'new' : r.status === 'found');
  const allPicked = visible.filter(savable).length > 0 && visible.filter(savable).every(r => picked.has(keyOf(r)));
  const togglePick = (k) => { const n = new Set(picked); if (n.has(k)) n.delete(k); else n.add(k); setPicked(n); };
  const togglePickAll = () => {
    const n = new Set(picked);
    visible.filter(savable).forEach(r => (allPicked ? n.delete(keyOf(r)) : n.add(keyOf(r))));
    setPicked(n);
  };

  const save = async () => {
    const chosen = (rows || []).filter(r => picked.has(keyOf(r)) && savable(r));
    if (!chosen.length) return;
    setSaving(true);
    try {
      const res = await bulkSaveContacts(tool === 'import' ? 'import' : 'websites', chosen);
      const parts = [`${res.added} new lead${res.added === 1 ? '' : 's'}`];
      if (res.updated) parts.push(`${res.updated} updated`);
      if (res.duplicate) parts.push(`${res.duplicate} already saved`);
      if (res.skipped_invalid) parts.push(`${res.skipped_invalid} skipped`);
      setNotice({ type: 'success', text: `Saved to Leads: ${parts.join(', ')}` });
      setRows(prev => prev.map(r => (picked.has(keyOf(r)) && savable(r) ? { ...r, status: tool === 'import' ? 'in_leads' : r.status, in_leads: true, reason: tool === 'import' ? 'Saved now' : r.reason } : r)));
      setPicked(new Set());
      onLeadsSaved && onLeadsSaved();
    } catch (err) {
      setNotice({ type: 'error', text: `Could not save: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const exportCols = {
    websites: ['input', 'website', 'company', 'emails', 'phones', 'address', 'socials', 'status', 'error'],
    emails: ['input', 'email', 'status', 'reason', 'suggestion', 'role', 'free', 'disposable', 'mx', 'in_leads'],
    phones: ['input', 'display', 'e164', 'type', 'status', 'reason', 'in_leads'],
    import: ['line', 'status', 'reason', 'company_name', 'full_name', 'email', 'mobile_number', 'website', 'location', 'description']
  }[tool];

  const textInput = tool !== 'import' && (
    <form onSubmit={(e) => {
      e.preventDefault();
      if (tool === 'websites') runWebsites();
      else if (tool === 'emails') runSimple(() => bulkVerifyEmails(text), 'e-mail address');
      else runSimple(() => bulkCleanPhones(text), 'number');
    }} noValidate>
      <div className="form-group">
        <label className="form-label" htmlFor={`bc-${tool}-input`}>
          {tool === 'websites' ? 'Websites' : tool === 'emails' ? 'E-mail addresses' : 'Phone numbers'}{' '}
          <span className="jp-hint">({tool === 'websites' ? 'one per line, up to 200' : tool === 'emails' ? `one per line or comma separated, up to ${opts?.maxEmails || 500}` : `one per line or any text, up to ${opts?.maxPhones || 1000}`})</span>
        </label>
        <textarea id={`bc-${tool}-input`} className="theme-form-input" rows={7} value={text} style={{ height: 'auto', fontFamily: 'monospace' }}
          onChange={(e) => { setText(e.target.value); setError(''); }} aria-invalid={!!error}
          placeholder={tool === 'websites' ? 'acmefoods.in\nhttps://www.example.co.in' : tool === 'emails' ? 'ravi@acmefoods.in\ninfo@example.co.in' : '98250 12345\n079-2654 3210\n+91 99999 88888'} />
        <div className="jp-hint" style={{ marginTop: 4 }}>{lines.length} line{lines.length === 1 ? '' : 's'}</div>
      </div>
      <button type="submit" className="theme-pill-btn primary" disabled={busy || !opts}>
        {busy ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
        {busy ? (progress ? ` Checking ${progress.done}/${progress.total}…` : ' Checking…') : (tool === 'websites' ? ' Find contacts' : tool === 'emails' ? ' Verify' : ' Clean')}
      </button>
    </form>
  );

  const importInput = tool === 'import' && (
    <div>
      <label className="theme-pill-btn neutral" style={{ cursor: 'pointer', display: 'inline-flex' }}>
        <Upload size={14} /> {fileName ? `Change file (${fileName})` : 'Choose CSV file'}
        <input type="file" accept=".csv,.txt,text/csv" onChange={onFile} style={{ display: 'none' }} aria-label="Choose CSV file" />
      </label>
      {preview && (
        <div style={{ marginTop: '1rem' }}>
          <div className="jp-hint" style={{ marginBottom: 8 }}>{preview.rows} data rows. Check which column is which (guessed from the headers):</div>
          <div className="jp-form-grid">
            {preview.headers.map((h, i) => (
              <div className="form-group" key={h + i}>
                <label className="form-label" htmlFor={`bc-map-${i}`}>{h} <span className="jp-hint">e.g. {String(preview.sample[0]?.[i] ?? '').slice(0, 30) || '—'}</span></label>
                <select id={`bc-map-${i}`} className="theme-form-input" value={mapping[h] || ''} onChange={(e) => setMapping({ ...mapping, [h]: e.target.value })}>
                  <option value="">— skip this column —</option>
                  {(preview.fields || []).map(f => <option key={f} value={f}>{FIELD_LABELS[f] || f}</option>)}
                </select>
              </div>
            ))}
            <div className="form-group">
              <label className="form-label" htmlFor="bc-source">Source name <span className="jp-hint">(saved with each lead)</span></label>
              <input id="bc-source" className="theme-form-input" value={sourceLabel} maxLength={60} onChange={(e) => setSourceLabel(e.target.value)} placeholder="e.g. Expo 2026 list" />
            </div>
          </div>
          <button type="button" className="theme-pill-btn primary" onClick={runCheck} disabled={busy}>
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />} Check contacts
          </button>
        </div>
      )}
    </div>
  );

  const renderCells = (r) => {
    if (tool === 'websites') {
      return (
        <>
          <td><div className="jp-cell-title">{r.company || r.domain}</div><div className="jp-cell-sub"><a href={r.website} target="_blank" rel="noopener noreferrer">{r.domain}</a></div></td>
          <td className="se-wrap">{(r.emails || []).join(', ') || '—'}</td>
          <td className="se-wrap">{(r.phones || []).join(', ') || '—'}</td>
          <td className="se-wrap">{Object.keys(r.socials || {}).join(', ') || '—'}</td>
          <td><Badge status={r.status} title={r.error} />{r.error && <div className="jp-cell-sub">{r.error}</div>}</td>
        </>
      );
    }
    if (tool === 'emails') {
      const tags = [r.role && 'role', r.free && 'free mail', r.disposable && 'disposable'].filter(Boolean).join(' · ');
      return (
        <>
          <td style={{ fontFamily: 'monospace' }}>{r.email}{tags && <div className="jp-cell-sub">{tags}</div>}</td>
          <td><Badge status={r.in_leads ? 'in_leads' : r.status} title={r.mx} />{r.in_leads && <div className="jp-cell-sub">{r.match}</div>}</td>
          <td className="se-wrap">{r.reason}{r.suggestion && <div className="jp-cell-sub">Did you mean <strong>{r.suggestion}</strong>?</div>}</td>
        </>
      );
    }
    if (tool === 'phones') {
      return (
        <>
          <td style={{ fontFamily: 'monospace' }}>{r.input}</td>
          <td style={{ fontFamily: 'monospace', whiteSpace: 'nowrap' }}>{r.display || '—'}</td>
          <td>{r.type || '—'}</td>
          <td><Badge status={r.in_leads ? 'in_leads' : r.status} />{r.in_leads && <div className="jp-cell-sub">{r.match}</div>}</td>
          <td className="se-wrap">{r.reason}</td>
        </>
      );
    }
    return (
      <>
        <td>{r.line}</td>
        <td><div className="jp-cell-title">{r.company_name || r.full_name || '—'}</div>{r.company_name && r.full_name && <div className="jp-cell-sub">{r.full_name}</div>}</td>
        <td className="se-wrap">{r.email || '—'}</td>
        <td style={{ whiteSpace: 'nowrap' }}>{r.mobile_number || '—'}</td>
        <td className="se-wrap">{r.website || '—'}</td>
        <td><Badge status={r.status} /><div className="jp-cell-sub">{r.reason}</div></td>
      </>
    );
  };
  const headers = {
    websites: ['Website', 'Emails', 'Phones', 'Social', 'Result'],
    emails: ['E-mail', 'Result', 'Why'],
    phones: ['Input', 'Clean number', 'Type', 'Result', 'Why'],
    import: ['Line', 'Contact', 'Email', 'Phone', 'Website', 'Result']
  }[tool];

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
        {textInput}{importInput}
      </div>

      {notice && (
        <div role="status" className={`jp-alert ${notice.type === 'error' ? 'jp-alert-error' : 'jp-alert-success'}`}>
          {notice.type === 'error' && <AlertTriangle size={14} />}<span style={{ flex: 1 }}>{notice.text}</span>
          <button type="button" className="jp-alert-close" aria-label="Dismiss message" onClick={() => setNotice(null)}><X size={14} /></button>
        </div>
      )}

      {rows && (
        <div className="theme-table-container">
          <div className="theme-table-controls" style={{ flexWrap: 'wrap', gap: 10 }}>
            <select className="theme-form-input" style={{ width: 'auto', height: 32 }} value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Show">
              {statuses.map(s => <option key={s} value={s}>{s === 'All' ? `Show: all (${rows.length})` : `${s.replace('_', ' ')} (${rows.filter(r => (s === 'in leads' ? r.in_leads : r.status === s && !(r.in_leads && tool !== 'import'))).length})`}</option>)}
            </select>
            {counts && <span className="jp-hint">{Object.entries(counts).filter(([, v]) => v).map(([k, v]) => `${v} ${k.replace('_', ' ')}`).join(' · ')}</span>}
            <div style={{ flex: 1 }} />
            <button type="button" className="theme-pill-btn neutral" onClick={() => csvDownload(visible, exportCols, `bulk_${tool}`)} disabled={!visible.length}><Download size={13} /> Export CSV</button>
            {canSave && (
              <button type="button" className="theme-pill-btn primary" onClick={save} disabled={!picked.size || saving || busy}>
                {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />} Save to Leads{picked.size ? ` (${picked.size})` : ''}
              </button>
            )}
          </div>
          <div className="theme-table-scroll">
            <table className="jp-table">
              <thead>
                <tr>
                  {canSave && <th style={{ width: 36 }}><input type="checkbox" aria-label="Select all savable rows" checked={allPicked} onChange={togglePickAll} /></th>}
                  {headers.map(h => <th key={h}>{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {visible.length === 0 ? (
                  <tr><td colSpan={headers.length + 1} className="jp-empty">Nothing to show for this filter.</td></tr>
                ) : visible.map((r, i) => {
                  const k = keyOf(r);
                  return (
                    <tr key={`${k}-${i}`} className={picked.has(k) ? 'selected' : ''}>
                      {canSave && <td><input type="checkbox" aria-label={`Select ${r.company_name || r.domain || k}`} disabled={!savable(r)} checked={picked.has(k)} onChange={() => togglePick(k)} /></td>}
                      {renderCells(r)}
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
