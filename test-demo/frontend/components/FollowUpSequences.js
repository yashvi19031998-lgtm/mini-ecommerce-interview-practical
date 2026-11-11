'use client';

// FollowUp Phase 2 UI: "Sequences" tab (due follow-up emails + Gmail reply check) and "Report" tab.
// Backend: followup_sequence.py, reply_checker.py, followup_store.report() via /api/followups/*.

import React, { useCallback, useEffect, useState } from 'react';
import { Send, Loader2, MailCheck, ChevronDown, ChevronRight, Ban, AlertTriangle, Info, PencilLine, X, RotateCcw, Check } from 'lucide-react';
import {
  fetchFollowupSequence, sendSequenceFollowups, stopSequence, checkGmailReplies, fetchFollowupReport,
  fetchFollowupTemplates, saveFollowupTemplates, resetFollowupTemplates
} from '../lib/api';

function when(stamp) {
  if (!stamp) return '—';
  const d = new Date(String(stamp).replace(' ', 'T'));
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString(undefined, { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

const TEMPLATE_LABELS = ['Follow-up 1', 'Follow-up 2', 'Final follow-up'];

function TemplatesModal({ onClose, onSaved }) {
  const [data, setData] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchFollowupTemplates()
      .then(res => { setData(res); setTemplates(res.templates.map(t => ({ ...t }))); })
      .catch(err => setError(err.message));
  }, []);

  const update = (i, field, value) => setTemplates(prev => prev.map((t, j) => (j === i ? { ...t, [field]: value } : t)));

  const save = async () => {
    setSaving(true);
    setError('');
    try {
      await saveFollowupTemplates(templates);
      onSaved('Follow-up templates saved');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const reset = async () => {
    if (!window.confirm('Replace your templates with the default ones?')) return;
    setSaving(true);
    try {
      await resetFollowupTemplates();
      onSaved('Follow-up templates reset to default');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fu-overlay" role="dialog" aria-modal="true" aria-labelledby="fu-tpl-title" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="fu-modal" style={{ maxWidth: 720 }}>
        <div className="fu-modal-head">
          <div>
            <div className="theme-panel-title" id="fu-tpl-title">Follow-up email templates</div>
            <div className="theme-panel-sub">
              Placeholders: {(data?.placeholders || []).map(p => `{${p}}`).join(' ')} · Your signature and the
              opt-out line are added automatically.
            </div>
          </div>
          <button type="button" className="jp-alert-close" aria-label="Close" onClick={onClose}><X size={16} /></button>
        </div>
        {error && <div role="alert" className="jp-alert jp-alert-error"><AlertTriangle size={14} /> {error}</div>}
        {!data && !error && <div className="jp-hint"><Loader2 size={14} className="animate-spin" /> Loading…</div>}
        {templates.map((t, i) => (
          <fieldset key={i} className="fu-tpl-block">
            <legend>{TEMPLATE_LABELS[i] || `Template ${i + 1}`}</legend>
            <label className="form-label" htmlFor={`fu-tpl-sub-${i}`}>Subject</label>
            <input id={`fu-tpl-sub-${i}`} className="theme-form-input" maxLength={200} value={t.subject}
              onChange={(e) => update(i, 'subject', e.target.value)} />
            <label className="form-label" htmlFor={`fu-tpl-body-${i}`}>Message</label>
            <textarea id={`fu-tpl-body-${i}`} className="theme-form-textarea" rows={6} maxLength={3000} value={t.body}
              onChange={(e) => update(i, 'body', e.target.value)} />
          </fieldset>
        ))}
        {data && <div className="jp-hint">Every follow-up ends with: “{data.opt_out_line}”</div>}
        <div className="fu-modal-foot">
          <button type="button" className="theme-pill-btn" onClick={reset} disabled={saving || !data?.customized}
            title={data?.customized ? 'Use the default templates again' : 'Already using the default templates'}>
            <RotateCcw size={13} /> Reset to default
          </button>
          <div style={{ flex: 1 }} />
          <button type="button" className="theme-pill-btn" onClick={onClose}>Cancel</button>
          <button type="button" className="theme-pill-btn primary" onClick={save} disabled={saving || !data}>
            {saving ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />} Save templates
          </button>
        </div>
      </div>
    </div>
  );
}

export function SequencesPanel({ onNotice, onChanged }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState(new Set());
  const [open, setOpen] = useState('');
  const [sending, setSending] = useState(false);
  const [checking, setChecking] = useState(false);
  const [busyLead, setBusyLead] = useState('');
  const [editingTemplates, setEditingTemplates] = useState(false);

  const load = useCallback(() => {
    setError('');
    fetchFollowupSequence()
      .then(res => { setData(res); setSelected(new Set()); })
      .catch(err => setError(err.message));
  }, []);
  useEffect(() => { load(); }, [load]);

  const due = data?.due || [];
  const allSelected = due.length > 0 && due.every(d => selected.has(d.lead_id));
  const toggle = (id) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelected(next);
  };

  const send = async () => {
    if (!selected.size) return;
    const n = selected.size;
    if (!window.confirm(`Send ${n} follow-up email${n === 1 ? '' : 's'} now? They go to real people.`)) return;
    setSending(true);
    try {
      const res = await sendSequenceFollowups([...selected]);
      const failed = res.results.filter(r => !r.success);
      onNotice(failed.length ? 'error' : 'success',
        `Sent ${res.sent} follow-up${res.sent === 1 ? '' : 's'}` +
        (failed.length ? `, ${failed.length} failed: ${failed[0].error}` : '') +
        (res.not_due ? ` · ${res.not_due} no longer due` : ''));
      load();
      onChanged && onChanged();
    } catch (err) {
      onNotice('error', `Could not send: ${err.message}`);
    } finally {
      setSending(false);
    }
  };

  const stop = async (item) => {
    const reason = window.prompt(`Stop follow-ups for ${item.lead_name}? Optional reason:`, '');
    if (reason === null) return;
    setBusyLead(item.lead_id);
    try {
      await stopSequence(item.lead_id, reason);
      onNotice('success', `Follow-ups stopped for ${item.lead_name}`);
      load();
      onChanged && onChanged();
    } catch (err) {
      onNotice('error', err.message);
    } finally {
      setBusyLead('');
    }
  };

  const checkReplies = async () => {
    setChecking(true);
    try {
      const r = await checkGmailReplies();
      onNotice('success', `Gmail checked: ${r.reply} replies, ${r.opted_out} opt-outs, ${r.bounce} bounces ` +
        `(${r.new_events} new, ${r.leads_updated} leads updated)`);
      load();
      onChanged && onChanged();
    } catch (err) {
      onNotice('error', err.message);
    } finally {
      setChecking(false);
    }
  };

  if (error) return <div role="alert" className="jp-alert jp-alert-error"><AlertTriangle size={14} /> {error}</div>;
  if (!data) return <div className="jp-hint"><Loader2 size={14} className="animate-spin" /> Loading…</div>;
  const cfg = data.config;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="fu-info-row">
        <span className="fu-info"><Info size={13} /> Follow-ups on day {cfg.days.join(', ')} after the first email (max {cfg.days.length})</span>
        <span className={`fu-info ${cfg.auto_send ? 'on' : ''}`}>
          Auto-send: <strong>{cfg.auto_send ? `ON (up to ${cfg.max_per_run} per hourly run)` : 'OFF — send from this list'}</strong>
        </span>
        <span className={`fu-info ${data.imap_configured ? 'on' : ''}`}>
          Gmail reply check: <strong>{data.imap_configured ? 'set up' : 'not set up'}</strong>
          {data.last_checked_at ? ` · last ${when(data.last_checked_at)}` : ''}
        </span>
        <div style={{ flex: 1 }} />
        <button type="button" className="theme-pill-btn neutral" onClick={() => setEditingTemplates(true)}>
          <PencilLine size={13} /> Edit templates
        </button>
        <button type="button" className="theme-pill-btn neutral" onClick={checkReplies}
          disabled={checking || !data.imap_configured}
          title={data.imap_configured ? 'Read Gmail now' : 'Add IMAP_USER and IMAP_PASSWORD (Gmail App Password) to .env'}>
          {checking ? <Loader2 size={13} className="animate-spin" /> : <MailCheck size={13} />} Check replies now
        </button>
        <button type="button" className="theme-pill-btn primary" onClick={send} disabled={!selected.size || sending}>
          {sending ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
          Send selected{selected.size ? ` (${selected.size})` : ''}
        </button>
      </div>

      <div className="theme-table-scroll">
        <table className="jp-table">
          <thead>
            <tr>
              <th style={{ width: 36 }}>
                <input type="checkbox" aria-label="Select all due follow-ups" checked={allSelected} disabled={!due.length}
                  onChange={() => setSelected(allSelected ? new Set() : new Set(due.map(d => d.lead_id)))} />
              </th>
              <th>Lead</th><th>Step</th><th>Due</th><th>First email</th><th>Email preview</th><th style={{ width: 90 }} />
            </tr>
          </thead>
          <tbody>
            {due.length === 0 ? (
              <tr><td colSpan={7} className="jp-empty">No follow-ups are due right now.</td></tr>
            ) : due.map(item => (
              <React.Fragment key={item.lead_id}>
                <tr className={selected.has(item.lead_id) ? 'selected' : ''}>
                  <td><input type="checkbox" aria-label={`Select follow-up for ${item.lead_name}`}
                    checked={selected.has(item.lead_id)} onChange={() => toggle(item.lead_id)} /></td>
                  <td>
                    <div className="jp-cell-title">{item.lead_name || item.email}</div>
                    <div className="jp-cell-sub">{item.email}</div>
                  </td>
                  <td>#{item.step} of {item.total_steps}</td>
                  <td>{when(item.due_at)}</td>
                  <td>{when(item.first_sent_at)}</td>
                  <td>
                    <button type="button" className="fu-link" aria-expanded={open === item.lead_id}
                      onClick={() => setOpen(open === item.lead_id ? '' : item.lead_id)}>
                      {open === item.lead_id ? <ChevronDown size={13} /> : <ChevronRight size={13} />} {item.preview.subject}
                    </button>
                  </td>
                  <td>
                    <button type="button" className="theme-pill-btn" disabled={busyLead === item.lead_id}
                      onClick={() => stop(item)} aria-label={`Stop follow-ups for ${item.lead_name}`}>
                      <Ban size={13} /> Stop
                    </button>
                  </td>
                </tr>
                {open === item.lead_id && (
                  <tr><td colSpan={7}><pre className="fu-preview">{item.preview.body}</pre></td></tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {editingTemplates && (
        <TemplatesModal
          onClose={() => setEditingTemplates(false)}
          onSaved={(msg) => { setEditingTemplates(false); onNotice('success', msg); load(); }}
        />
      )}

      <div className="jp-hint">
        {data.waiting_total} lead(s) waiting for a later step · {data.stopped_total} sequence(s) stopped
        (replied, bounced, asked to stop, status moved on, or stopped by hand).
      </div>
    </div>
  );
}

export function ReportPanel() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => { fetchFollowupReport().then(setData).catch(err => setError(err.message)); }, []);

  if (error) return <div role="alert" className="jp-alert jp-alert-error"><AlertTriangle size={14} /> {error}</div>;
  if (!data) return <div className="jp-hint"><Loader2 size={14} className="animate-spin" /> Loading…</div>;
  const o = data.overall;
  const cards = [
    ['Leads contacted', o.contacted], ['Replied', o.replied], ['Reply rate', `${o.reply_rate_pct}%`],
    ['Follow-ups sent', o.followups_sent], ['Replied after a follow-up', o.replied_after_followup],
    ['Bounced', o.bounced], ['Asked to stop', o.opted_out]
  ];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div className="fu-report-cards">
        {cards.map(([label, value]) => (
          <div key={label} className="fu-card"><span className="fu-card-value">{value}</span><span className="fu-card-label">{label}</span></div>
        ))}
      </div>
      <div className="theme-table-scroll">
        <table className="jp-table">
          <thead><tr><th>Lead source</th><th>Contacted</th><th>Replied</th><th>Reply rate</th><th>Bounced</th><th>Asked to stop</th></tr></thead>
          <tbody>
            {data.by_source.length === 0 ? (
              <tr><td colSpan={6} className="jp-empty">No emails logged yet.</td></tr>
            ) : data.by_source.map(r => (
              <tr key={r.source}>
                <td>{r.source}</td><td>{r.contacted}</td><td>{r.replied}</td><td>{r.reply_rate_pct}%</td>
                <td>{r.bounced}</td><td>{r.opted_out}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="jp-hint">Replies are counted only after the Gmail reply check runs (button in the Sequences tab, or every hourly run).</div>
    </div>
  );
}
