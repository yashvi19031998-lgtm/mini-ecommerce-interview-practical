'use client';

// Lead Care -> Lead Enrichment: pick saved leads that miss e-mail / phone / website / website check, run Deep Search
// on them (5 per request, progress shown), review the proposals, and save only the chosen ones. Saving fills EMPTY
// fields only, after a backup of the leads file, and can be undone from Data Cleanup -> history.
// Backend: lead_enrichment.py via /api/lead-care/enrichment/*.

import React, { useMemo, useState } from 'react';
import { Wand2, Loader2, X, Save, AlertTriangle, ShieldCheck, Search, Square } from 'lucide-react';
import { findEnrichmentCandidates, runLeadEnrichment, saveLeadEnrichment } from '../lib/api';

const NEEDS = [
  { id: 'email', label: 'No e-mail' }, { id: 'mobile_number', label: 'No phone' },
  { id: 'website', label: 'No website' }, { id: 'website_signals', label: 'No website check' }
];
const FIELD_LABEL = { website: 'Website', email: 'E-mail', mobile_number: 'Phone', website_signals: 'Website check' };
const BATCH = 5;
const pKey = (p) => `${p.lead_id}|${p.field}`;

export default function LeadEnrichment({ onLeadsChanged, onOpenCleanup }) {
  const [needs, setNeeds] = useState(['email', 'mobile_number']);
  const [source, setSource] = useState('');
  const [onlySite, setOnlySite] = useState(true);
  const [limit, setLimit] = useState(25);
  const [steps, setSteps] = useState(['deep', 'check']);
  const [list, setList] = useState(null);
  const [picked, setPicked] = useState(new Set());
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(null);
  const [stopReq, setStopReq] = useState(false);
  const [proposals, setProposals] = useState([]);
  const [chosen, setChosen] = useState(new Set());
  const [leadReport, setLeadReport] = useState({});
  const [error, setError] = useState('');
  const [notice, setNotice] = useState(null);
  const [saving, setSaving] = useState(false);
  const stopRef = React.useRef(false);

  const toggle = (set, setter, k) => { const n = new Set(set); if (n.has(k)) n.delete(k); else n.add(k); setter(n); };
  const toggleArr = (arr, setter, k) => setter(arr.includes(k) ? arr.filter(x => x !== k) : [...arr, k]);

  const find = async (e) => {
    e.preventDefault();
    if (!needs.length) { setError('Choose what is missing'); return; }
    setError(''); setBusy(true); setList(null); setProposals([]); setChosen(new Set()); setLeadReport({}); setNotice(null);
    try {
      const res = await findEnrichmentCandidates({ needs, source, only_with_website: onlySite, limit });
      setList(res);
      setPicked(new Set(res.results.map(r => r.lead_id)));
      setNotice({ type: 'info', text: `${res.matching} lead${res.matching === 1 ? '' : 's'} match — showing ${res.results.length}.` });
    } catch (err) {
      setError(err.message || 'Could not load leads');
    } finally {
      setBusy(false);
    }
  };

  const run = async () => {
    const ids = (list?.results || []).filter(r => picked.has(r.lead_id)).map(r => r.lead_id);
    if (!ids.length || !steps.length) return;
    stopRef.current = false; setStopReq(false);
    setProgress({ done: 0, total: ids.length }); setNotice(null); setProposals([]); setChosen(new Set()); setLeadReport({});
    const all = [];
    try {
      for (let i = 0; i < ids.length; i += BATCH) {
        if (stopRef.current) break;
        const res = await runLeadEnrichment(ids.slice(i, i + BATCH), steps);
        all.push(...res.proposals);
        setProposals([...all]);
        setChosen(prev => { const n = new Set(prev); res.proposals.forEach(p => n.add(pKey(p))); return n; });
        setLeadReport(prev => ({ ...prev, ...Object.fromEntries(res.leads.map(l => [l.lead_id, l])) }));
        setProgress({ done: Math.min(i + BATCH, ids.length), total: ids.length });
      }
      setNotice({ type: 'success', text: `${stopRef.current ? 'Stopped — ' : ''}${all.length} value${all.length === 1 ? '' : 's'} found for empty fields. Review and save the ones you want.` });
    } catch (err) {
      setNotice({ type: 'error', text: `Stopped: ${err.message}` });
    } finally {
      setProgress(null);
    }
  };

  const save = async () => {
    const changes = proposals.filter(p => chosen.has(pKey(p)));
    if (!changes.length) return;
    setSaving(true);
    try {
      const res = await saveLeadEnrichment(changes);
      setNotice({ type: 'success', text: `Saved ${res.applied} value${res.applied === 1 ? '' : 's'} into empty fields${res.skipped ? ` (${res.skipped} skipped — already filled or not valid)` : ''}. Backup: ${res.backup || '—'}. Undo from Data Cleanup → history.` });
      setProposals(prev => prev.filter(p => !chosen.has(pKey(p))));
      setChosen(new Set());
      onLeadsChanged && onLeadsChanged();
    } catch (err) {
      setNotice({ type: 'error', text: `Nothing was saved: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const rows = list?.results || [];
  const byLead = useMemo(() => {
    const m = {};
    proposals.forEach(p => { (m[p.lead_id] = m[p.lead_id] || []).push(p); });
    return m;
  }, [proposals]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className="theme-card-panel" style={{ marginBottom: 0 }}>
        <div className="theme-panel-header" style={{ marginBottom: '1rem' }}>
          <div>
            <div className="theme-panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Wand2 size={18} /> Lead Enrichment</div>
            <div className="theme-panel-sub">Find missing e-mails, phones and websites for leads you already saved — then keep only what you approve.</div>
          </div>
        </div>
        <div className="jp-alert se-alert-info" role="note" style={{ marginBottom: '0.75rem' }}>
          <ShieldCheck size={14} />
          <span><strong>Nothing is saved until you click Save, and nothing old is changed:</strong> only empty fields are filled, after a backup of the leads file;
            every save can be undone from <button type="button" className="jp-linklike" onClick={onOpenCleanup} style={{ background: 'none', border: 0, padding: 0, color: 'inherit', textDecoration: 'underline', cursor: 'pointer' }}>Data Cleanup → history</button>.
            Leads without a website need the search engine to find one (DuckDuckGo finds few — a SearXNG / Brave / Serper setup finds more).</span>
        </div>
        {error && <div role="alert" className="jp-alert jp-alert-error" style={{ marginBottom: '0.75rem' }}><AlertTriangle size={14} /> {error}</div>}
        <form onSubmit={find} noValidate>
          <div className="form-group">
            <div className="form-label">Leads that are missing</div>
            <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
              {NEEDS.map(n => (
                <label key={n.id} style={{ display: 'inline-flex', gap: 5, alignItems: 'center', fontSize: 13 }}>
                  <input type="checkbox" checked={needs.includes(n.id)} onChange={() => toggleArr(needs, setNeeds, n.id)} /> {n.label}
                </label>
              ))}
            </div>
          </div>
          <div className="jp-form-grid">
            <div className="form-group">
              <label className="form-label" htmlFor="lc-enrich-source">Source contains <span className="jp-hint">(optional)</span></label>
              <input id="lc-enrich-source" className="theme-form-input" maxLength={60} value={source} onChange={(e) => setSource(e.target.value)} placeholder="e.g. IndiaMART, Corporate, Reddit" />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="lc-enrich-limit">How many leads</label>
              <select id="lc-enrich-limit" className="theme-form-input" value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
                {[10, 25, 50, 100].map(n => <option key={n} value={n}>{n}</option>)}
              </select>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'center', margin: '4px 0 12px' }}>
            <label style={{ display: 'inline-flex', gap: 5, alignItems: 'center', fontSize: 13 }}>
              <input type="checkbox" checked={onlySite} onChange={() => setOnlySite(!onlySite)} /> Only leads that already have a website (fast, best results)
            </label>
            <label style={{ display: 'inline-flex', gap: 5, alignItems: 'center', fontSize: 13 }}>
              <input type="checkbox" checked={steps.includes('deep')} onChange={() => toggleArr(steps, setSteps, 'deep')} /> Deep Search (e-mail / phone / website)
            </label>
            <label style={{ display: 'inline-flex', gap: 5, alignItems: 'center', fontSize: 13 }}>
              <input type="checkbox" checked={steps.includes('check')} onChange={() => toggleArr(steps, setSteps, 'check')} /> Website check (old / not mobile-friendly…)
            </label>
          </div>
          <button type="submit" className="theme-pill-btn primary" disabled={busy || !!progress}>
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />} Find leads
          </button>
        </form>
      </div>

      {notice && (
        <div role="status" className={`jp-alert ${notice.type === 'error' ? 'jp-alert-error' : notice.type === 'info' ? 'se-alert-info' : 'jp-alert-success'}`}>
          {notice.type === 'error' && <AlertTriangle size={14} />}<span style={{ flex: 1 }}>{notice.text}</span>
          <button type="button" className="jp-alert-close" aria-label="Dismiss message" onClick={() => setNotice(null)}><X size={14} /></button>
        </div>
      )}

      {list && (
        <div className="theme-table-container">
          <div className="theme-table-controls" style={{ flexWrap: 'wrap', gap: 10 }}>
            <span className="jp-hint">{picked.size} of {rows.length} selected</span>
            <div style={{ flex: 1 }} />
            {progress && (
              <button type="button" className="theme-pill-btn neutral" onClick={() => { stopRef.current = true; setStopReq(true); }} disabled={stopReq}>
                <Square size={13} /> {stopReq ? 'Stopping after this batch…' : 'Stop'}
              </button>
            )}
            <button type="button" className="theme-pill-btn neutral" onClick={run} disabled={!picked.size || !!progress || !steps.length}>
              {progress ? <Loader2 size={13} className="animate-spin" /> : <Wand2 size={13} />}
              {progress ? ` Enriching ${progress.done}/${progress.total}…` : ` Enrich ${picked.size} lead${picked.size === 1 ? '' : 's'}`}
            </button>
            <button type="button" className="theme-pill-btn primary" onClick={save} disabled={!chosen.size || saving || !!progress}>
              {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />} Save {chosen.size} value{chosen.size === 1 ? '' : 's'}
            </button>
          </div>
          <div className="theme-table-scroll">
            <table className="jp-table">
              <thead>
                <tr>
                  <th style={{ width: 36 }}><input type="checkbox" aria-label="Select all leads" checked={rows.length > 0 && rows.every(r => picked.has(r.lead_id))}
                    onChange={(e) => setPicked(e.target.checked ? new Set(rows.map(r => r.lead_id)) : new Set())} /></th>
                  <th>Lead</th><th>Missing</th><th>Found — tick what to save</th><th>Result</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? <tr><td colSpan={5} className="jp-empty">No lead matches.</td></tr> : rows.map(r => {
                  const props = byLead[r.lead_id] || [];
                  const rep = leadReport[r.lead_id];
                  return (
                    <tr key={r.lead_id}>
                      <td><input type="checkbox" aria-label={`Select ${r.lead_id}`} checked={picked.has(r.lead_id)} onChange={() => toggle(picked, setPicked, r.lead_id)} /></td>
                      <td><div className="jp-cell-title">{r.company || r.lead_id}</div><div className="jp-cell-sub">{r.lead_id} · {r.website || 'no website'}{r.source ? ` · ${r.source}` : ''}</div></td>
                      <td className="se-wrap">{r.missing.map(m => FIELD_LABEL[m]).join(', ')}</td>
                      <td className="se-wrap">
                        {props.length === 0 ? <span className="jp-hint">{rep ? 'nothing new' : '—'}</span> : props.map(p => (
                          <label key={pKey(p)} style={{ display: 'flex', gap: 6, alignItems: 'flex-start', fontSize: 13, marginBottom: 3 }} title={p.from}>
                            <input type="checkbox" checked={chosen.has(pKey(p))} onChange={() => toggle(chosen, setChosen, pKey(p))} aria-label={`Save ${FIELD_LABEL[p.field]} for ${r.lead_id}`} />
                            <span><strong>{FIELD_LABEL[p.field]}:</strong> {p.new}</span>
                          </label>
                        ))}
                      </td>
                      <td>{rep ? <span className={`se-badge deep-${rep.status === 'found' ? 'found' : rep.status === 'partial' ? 'partial' : 'none'}`} title={(rep.steps || []).join(' | ')}>{rep.status}</span> : <span className="jp-hint">—</span>}</td>
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
