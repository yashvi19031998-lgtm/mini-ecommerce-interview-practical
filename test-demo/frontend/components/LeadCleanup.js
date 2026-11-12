'use client';

// Lead Care -> Data Cleanup. Dry run first (scan); "Apply" only fills EMPTY fields from the lead's own data, after a
// full backup of the leads file, with a change log; any cleanup can be undone. Nothing is ever deleted.
// Backend: lead_cleanup.py via /api/lead-care/cleanup*.

import React, { useEffect, useState } from 'react';
import { Eraser, Loader2, X, AlertTriangle, ShieldCheck, RefreshCw, Undo2, History, ChevronDown, ChevronRight } from 'lucide-react';
import { scanLeadCleanup, applyLeadCleanup, undoLeadCleanup } from '../lib/api';

const FIELD_LABEL = { website: 'Website', email: 'E-mail', mobile_number: 'Phone' };

export default function LeadCleanup({ onLeadsChanged }) {
  const [scan, setScan] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState(null);
  const [chosen, setChosen] = useState(new Set());
  const [open, setOpen] = useState(new Set());
  const [confirming, setConfirming] = useState(false);

  const load = async (keepNotice = false) => {
    setBusy(true); setError(''); if (!keepNotice) setNotice(null);
    try {
      const res = await scanLeadCleanup();
      setScan(res);
      setChosen(new Set(res.fixes.filter(f => f.count > 0).map(f => f.id)));
    } catch (err) {
      setError(err.message || 'Could not check the leads. Is the Python backend running?');
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => { load(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  const total = (scan?.fixes || []).filter(f => chosen.has(f.id)).reduce((a, f) => a + f.count, 0);
  const toggle = (set, setter, k) => { const n = new Set(set); if (n.has(k)) n.delete(k); else n.add(k); setter(n); };

  const apply = async () => {
    setConfirming(false); setBusy(true); setNotice(null);
    try {
      const res = await applyLeadCleanup([...chosen]);
      setNotice({ type: 'success', text: res.applied
        ? `Filled ${res.applied} empty field${res.applied === 1 ? '' : 's'}. Backup saved as ${res.backup} — you can undo below.`
        : 'Nothing to change.' });
      onLeadsChanged && onLeadsChanged();
      await load(true);
    } catch (err) {
      setNotice({ type: 'error', text: `Nothing was changed: ${err.message}` });
      setBusy(false);
    }
  };

  const undo = async (id) => {
    setBusy(true); setNotice(null);
    try {
      const res = await undoLeadCleanup(id);
      setNotice({ type: 'success', text: `Undone: ${res.reverted} field${res.reverted === 1 ? '' : 's'} emptied again${res.kept_newer ? ` (${res.kept_newer} left alone because they were changed later)` : ''}.` });
      onLeadsChanged && onLeadsChanged();
      await load(true);
    } catch (err) {
      setNotice({ type: 'error', text: err.message });
      setBusy(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className="theme-card-panel" style={{ marginBottom: 0 }}>
        <div className="theme-panel-header" style={{ marginBottom: '1rem' }}>
          <div>
            <div className="theme-panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Eraser size={18} /> Data Cleanup</div>
            <div className="theme-panel-sub">Fill gaps in your saved leads from information they already contain — safely.</div>
          </div>
          <button type="button" className="theme-pill-btn neutral" onClick={() => load()} disabled={busy}>
            {busy ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />} Check again
          </button>
        </div>
        <div className="jp-alert se-alert-info" role="note" style={{ marginBottom: '0.75rem' }}>
          <ShieldCheck size={14} />
          <span><strong>Nothing is ever deleted.</strong> No lead is removed and no filled value is changed — only empty fields are filled.
            The whole leads file is backed up before each run, every change is logged, and any run can be undone.</span>
        </div>
        {error && <div role="alert" className="jp-alert jp-alert-error"><AlertTriangle size={14} /> {error}</div>}
        {scan && (
          <div className="jp-status-row">
            <span className="jp-status-chip ok">{scan.leads} leads checked</span>
            {Object.entries(scan.missing || {}).map(([k, v]) => <span key={k} className="jp-status-chip empty">{v} {k}</span>)}
            <span className="jp-hint">Missing contacts are filled by Lead Enrichment (Deep Search), not by cleanup.</span>
          </div>
        )}
      </div>

      {notice && (
        <div role="status" className={`jp-alert ${notice.type === 'error' ? 'jp-alert-error' : 'jp-alert-success'}`}>
          {notice.type === 'error' && <AlertTriangle size={14} />}<span style={{ flex: 1 }}>{notice.text}</span>
          <button type="button" className="jp-alert-close" aria-label="Dismiss message" onClick={() => setNotice(null)}><X size={14} /></button>
        </div>
      )}

      {scan && (
        <div className="theme-card-panel" style={{ marginBottom: 0 }}>
          <div className="theme-panel-title" style={{ marginBottom: 8 }}>Safe fixes (dry run — nothing changed yet)</div>
          {scan.fixes.map(f => (
            <div key={f.id} style={{ borderTop: '1px solid var(--border-light, #e5e7eb)', padding: '10px 0' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <input type="checkbox" aria-label={`Use fix: ${f.title}`} checked={chosen.has(f.id)} disabled={!f.count || busy}
                  onChange={() => toggle(chosen, setChosen, f.id)} />
                <button type="button" className="jp-alert-close" aria-expanded={open.has(f.id)} aria-label={`Show changes for ${f.title}`}
                  onClick={() => toggle(open, setOpen, f.id)} disabled={!f.count}>{open.has(f.id) ? <ChevronDown size={14} /> : <ChevronRight size={14} />}</button>
                <strong>{f.title}</strong>
                <span className={`se-badge ${f.count ? 'deep-found' : 'deep-none'}`}>{f.count} lead{f.count === 1 ? '' : 's'}</span>
                <span className="jp-hint">{f.why}</span>
              </div>
              {open.has(f.id) && f.count > 0 && (
                <div className="theme-table-scroll" style={{ marginTop: 8 }}>
                  <table className="jp-table">
                    <thead><tr><th>Lead</th><th>Field</th><th>Will be filled with</th><th>Taken from</th></tr></thead>
                    <tbody>
                      {f.changes.map(c => (
                        <tr key={`${c.lead_id}-${c.field}`}>
                          <td><div className="jp-cell-title">{c.lead_id}</div><div className="jp-cell-sub">{c.company}</div></td>
                          <td>{FIELD_LABEL[c.field] || c.field} <span className="jp-hint">(now empty)</span></td>
                          <td className="se-wrap">{c.new}</td><td className="se-wrap">{c.from}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {f.count > f.changes.length && <div className="jp-hint" style={{ padding: 6 }}>Showing {f.changes.length} of {f.count}.</div>}
                </div>
              )}
            </div>
          ))}
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginTop: 12, flexWrap: 'wrap' }}>
            {!confirming ? (
              <button type="button" className="theme-pill-btn primary" disabled={!total || busy} onClick={() => setConfirming(true)}>
                <Eraser size={13} /> Fill {total} empty field{total === 1 ? '' : 's'}…
              </button>
            ) : (
              <>
                <span>Back up the leads file and fill {total} empty field{total === 1 ? '' : 's'}?</span>
                <button type="button" className="theme-pill-btn primary" onClick={apply} disabled={busy}>
                  {busy ? <Loader2 size={13} className="animate-spin" /> : null} Yes, fill them
                </button>
                <button type="button" className="theme-pill-btn neutral" onClick={() => setConfirming(false)}>Cancel</button>
              </>
            )}
          </div>
        </div>
      )}

      {scan && (
        <div className="theme-card-panel" style={{ marginBottom: 0 }}>
          <div className="theme-panel-title" style={{ marginBottom: 4 }}>Reports — nothing is changed</div>
          <div className="theme-panel-sub" style={{ marginBottom: 8 }}>Shared contacts: the same e-mail / phone / domain on different leads — usually a job portal’s or platform’s contact, not the client’s. Check these leads by hand.</div>
          {scan.shared_contacts.length === 0 ? <div className="jp-hint">None found.</div> : (
            <div className="theme-table-scroll">
              <table className="jp-table">
                <thead><tr><th>Type</th><th>Value</th><th>Leads</th><th>Examples</th></tr></thead>
                <tbody>{scan.shared_contacts.slice(0, 30).map((s, i) => (
                  <tr key={i}><td>{s.kind}</td><td className="se-wrap">{s.value}</td><td>{s.leads}</td><td className="se-wrap">{s.examples.join(' · ')}</td></tr>
                ))}</tbody>
              </table>
            </div>
          )}
          {scan.format_issues.length > 0 && (
            <>
              <div className="theme-panel-sub" style={{ margin: '12px 0 8px' }}>Values the current rules would write differently (kept as they are):</div>
              <div className="theme-table-scroll">
                <table className="jp-table">
                  <thead><tr><th>Lead</th><th>Field</th><th>Saved value</th><th>Rules would write</th></tr></thead>
                  <tbody>{scan.format_issues.map((f, i) => (
                    <tr key={i}><td>{f.lead_id}<div className="jp-cell-sub">{f.company}</div></td><td>{FIELD_LABEL[f.field] || f.field}</td>
                      <td className="se-wrap">{f.value}</td><td className="se-wrap">{f.rules_would_write}</td></tr>
                  ))}</tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {scan?.history?.length > 0 && (
        <div className="theme-card-panel" style={{ marginBottom: 0 }}>
          <div className="theme-panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}><History size={16} /> Cleanup history</div>
          <table className="jp-table">
            <thead><tr><th>When</th><th>Fields filled</th><th>Fixes</th><th>Backup</th><th /></tr></thead>
            <tbody>{scan.history.map(h => (
              <tr key={h.id}>
                <td>{h.at}</td><td>{h.changes}</td><td className="se-wrap">{h.fixes.join(', ')}</td><td className="se-wrap jp-hint">{h.backup}</td>
                <td>{h.undone ? <span className="jp-hint">undone</span> : (
                  <button type="button" className="theme-pill-btn neutral" onClick={() => undo(h.id)} disabled={busy}><Undo2 size={13} /> Undo</button>
                )}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}
