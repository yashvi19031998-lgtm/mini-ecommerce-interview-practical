'use client';

// FollowUp History: follow-up queue, activity history, per-lead timeline, manual logging (Phase 1)
// + follow-up sequences and reply-rate report (Phase 2, see FollowUpSequences.js).
// Backend: followup_store.py via /api/followups/* and /api/leads/<id>/timeline.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  History, Plus, Download, Loader2, X, Check, Mail, Phone, Users, StickyNote,
  MessageSquare, ArrowRightLeft, CalendarClock, AlertTriangle, Search,
  Reply, MailX, Ban, OctagonX
} from 'lucide-react';
import { SequencesPanel, ReportPanel } from './FollowUpSequences';
import {
  fetchFollowupSummary, fetchFollowupQueue, fetchFollowupHistory, fetchLeadTimeline,
  logFollowupActivity, updateFollowup, importSentEmailsHistory
} from '../lib/api';

const TYPE_META = {
  email_sent: { label: 'Email sent', icon: Mail },
  email: { label: 'Email (manual)', icon: Mail },
  call: { label: 'Call', icon: Phone },
  meeting: { label: 'Meeting', icon: Users },
  whatsapp: { label: 'WhatsApp', icon: MessageSquare },
  note: { label: 'Note', icon: StickyNote },
  status_change: { label: 'Status change', icon: ArrowRightLeft },
  followup: { label: 'Follow-up', icon: CalendarClock },
  reply: { label: 'Reply', icon: Reply },
  opted_out: { label: 'Asked to stop', icon: Ban },
  bounce: { label: 'Bounced', icon: MailX },
  sequence_stopped: { label: 'Sequence stopped', icon: OctagonX }
};
const MANUAL_TYPES = ['call', 'meeting', 'whatsapp', 'email', 'note'];
const BUCKETS = [
  { id: 'all', label: 'All pending' },
  { id: 'overdue', label: 'Overdue' },
  { id: 'today', label: 'Today' },
  { id: 'upcoming', label: 'Next 7 days' },
  { id: 'later', label: 'Later' }
];
const PAGE_SIZE = 50;

// ---------- date helpers ----------
const pad = (n) => String(n).padStart(2, '0');
const toLocalInput = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
const dateOnly = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const addDays = (n) => { const d = new Date(); d.setDate(d.getDate() + n); return dateOnly(d); };
const parseTs = (s) => (s ? new Date(String(s).replace(' ', 'T')) : null);

function relative(stamp) {
  const d = parseTs(stamp);
  if (!d || Number.isNaN(d.getTime())) return '';
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const day = new Date(d); day.setHours(0, 0, 0, 0);
  const diff = Math.round((day - today) / 86400000);
  if (diff === 0) return 'today';
  if (diff === 1) return 'tomorrow';
  if (diff === -1) return 'yesterday';
  return diff > 0 ? `in ${diff} days` : `${-diff} days ago`;
}

function formatTs(stamp) {
  const d = parseTs(stamp);
  if (!d || Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString(undefined, { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function TypeIcon({ type, size = 14 }) {
  const Icon = (TYPE_META[type] || TYPE_META.note).icon;
  return <span className={`fu-type-icon t-${type}`}><Icon size={size} /></span>;
}

// ---------- Reschedule control ----------
function RescheduleControl({ onPick, disabled }) {
  const [custom, setCustom] = useState(false);
  if (custom) {
    return (
      <input
        type="date"
        className="theme-form-input fu-date-input"
        min={dateOnly(new Date())}
        aria-label="New follow-up date"
        autoFocus
        onChange={(e) => { if (e.target.value) { onPick(e.target.value); setCustom(false); } }}
        onBlur={() => setCustom(false)}
      />
    );
  }
  return (
    <select
      className="theme-form-input fu-select-sm"
      value=""
      disabled={disabled}
      aria-label="Reschedule follow-up"
      onChange={(e) => {
        const v = e.target.value;
        if (v === 'custom') setCustom(true);
        else if (v) onPick(addDays(Number(v)));
      }}
    >
      <option value="">Reschedule…</option>
      <option value="1">+1 day</option>
      <option value="3">+3 days</option>
      <option value="7">+7 days</option>
      <option value="custom">Pick date…</option>
    </select>
  );
}

// ---------- Log activity modal ----------
function LogActivityModal({ leads, initialLead, onClose, onSaved }) {
  const [leadQuery, setLeadQuery] = useState(initialLead ? initialLead.name : '');
  const [lead, setLead] = useState(initialLead || null);
  const [type, setType] = useState('call');
  const [summary, setSummary] = useState('');
  const [details, setDetails] = useState('');
  const [occurredAt, setOccurredAt] = useState(toLocalInput(new Date()));
  const [nextChoice, setNextChoice] = useState('3');
  const [nextDate, setNextDate] = useState('');
  const [nextNote, setNextNote] = useState('');
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState('');
  const [saving, setSaving] = useState(false);

  const matches = useMemo(() => {
    const q = leadQuery.trim().toLowerCase();
    if (!q || (lead && lead.name === leadQuery)) return [];
    return leads
      .filter(l => `${l['Company Name'] || ''} ${l.Email || ''}`.toLowerCase().includes(q))
      .slice(0, 8);
  }, [leadQuery, leads, lead]);

  const nextDue = nextChoice === 'none' ? '' : nextChoice === 'custom' ? nextDate : addDays(Number(nextChoice));

  const submit = async (e) => {
    e.preventDefault();
    const errs = {};
    if (!lead) errs.lead = 'Select a lead from the list';
    if (!summary.trim()) errs.summary = 'Summary is required';
    if (summary.length > 300) errs.summary = 'Summary must be 300 characters or less';
    if (!occurredAt) errs.occurredAt = 'Date and time are required';
    else if (new Date(occurredAt) > new Date(Date.now() + 5 * 60000)) errs.occurredAt = 'Cannot be in the future';
    if (nextChoice === 'custom' && !nextDate) errs.next = 'Pick a follow-up date';
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setSaving(true);
    setServerError('');
    try {
      await logFollowupActivity({
        lead_id: lead.id, type, summary: summary.trim(), details: details.trim(),
        occurred_at: occurredAt, next_followup_at: nextDue, next_followup_note: nextNote.trim()
      });
      onSaved(`Logged ${TYPE_META[type].label.toLowerCase()} for ${lead.name}${nextDue ? ` · next follow-up ${relative(nextDue)}` : ''}`);
    } catch (err) {
      setServerError(err.message || 'Could not save');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fu-overlay" role="dialog" aria-modal="true" aria-labelledby="fu-log-title" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="fu-modal" onSubmit={submit} noValidate>
        <div className="fu-modal-head">
          <div className="theme-panel-title" id="fu-log-title">Log activity</div>
          <button type="button" className="jp-alert-close" aria-label="Close" onClick={onClose}><X size={16} /></button>
        </div>

        {serverError && <div role="alert" className="jp-alert jp-alert-error"><AlertTriangle size={14} /> {serverError}</div>}

        <div className="form-group" style={{ position: 'relative' }}>
          <label className="form-label" htmlFor="fu-lead">Lead</label>
          <input
            id="fu-lead"
            className="theme-form-input"
            placeholder="Search company or email…"
            value={leadQuery}
            autoComplete="off"
            onChange={(e) => { setLeadQuery(e.target.value); setLead(null); }}
            aria-invalid={!!errors.lead}
          />
          {matches.length > 0 && (
            <div className="jp-menu" role="listbox">
              {matches.map(l => (
                <div
                  key={l.id}
                  role="option"
                  aria-selected="false"
                  className="jp-menu-item"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    setLead({ id: l.id, name: l['Company Name'] || l.Email || l.id });
                    setLeadQuery(l['Company Name'] || l.Email || l.id);
                    setErrors(prev => ({ ...prev, lead: '' }));
                  }}
                >
                  <span className="jp-menu-text">
                    <span>{l['Company Name'] || '(no name)'}</span>
                    <span className="jp-menu-sub">{[l.Email, l.Source].filter(Boolean).join(' · ')}</span>
                  </span>
                </div>
              ))}
            </div>
          )}
          {errors.lead && <div className="jp-field-error">{errors.lead}</div>}
        </div>

        <div className="fu-two-col">
          <div className="form-group">
            <label className="form-label" htmlFor="fu-type">Type</label>
            <select id="fu-type" className="theme-form-input" value={type} onChange={(e) => setType(e.target.value)}>
              {MANUAL_TYPES.map(t => <option key={t} value={t}>{TYPE_META[t].label}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="fu-when">When</label>
            <input id="fu-when" type="datetime-local" className="theme-form-input" value={occurredAt}
              max={toLocalInput(new Date())} onChange={(e) => setOccurredAt(e.target.value)} aria-invalid={!!errors.occurredAt} />
            {errors.occurredAt && <div className="jp-field-error">{errors.occurredAt}</div>}
          </div>
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="fu-summary">Summary <span className="jp-hint">({summary.length}/300)</span></label>
          <input id="fu-summary" className="theme-form-input" value={summary} maxLength={300}
            placeholder="e.g. Called CTO — interested, wants a quote"
            onChange={(e) => { setSummary(e.target.value); if (e.target.value.trim()) setErrors(prev => ({ ...prev, summary: '' })); }}
            aria-invalid={!!errors.summary} />
          {errors.summary && <div className="jp-field-error">{errors.summary}</div>}
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="fu-details">Details (optional)</label>
          <textarea id="fu-details" className="theme-form-textarea" rows={3} maxLength={2000} value={details}
            onChange={(e) => setDetails(e.target.value)} />
        </div>

        <div className="form-group">
          <span className="form-label" id="fu-next-label">Next follow-up</span>
          <div className="fu-chip-group" role="radiogroup" aria-labelledby="fu-next-label">
            {[['none', 'None'], ['3', '+3 days'], ['7', '+7 days'], ['14', '+14 days'], ['custom', 'Pick date']].map(([v, label]) => (
              <button type="button" key={v} role="radio" aria-checked={nextChoice === v}
                className={`fu-chip ${nextChoice === v ? 'active' : ''}`} onClick={() => setNextChoice(v)}>
                {label}
              </button>
            ))}
          </div>
          {nextChoice === 'custom' && (
            <input type="date" className="theme-form-input" min={dateOnly(new Date())} value={nextDate}
              aria-label="Follow-up date" onChange={(e) => { setNextDate(e.target.value); setErrors(prev => ({ ...prev, next: '' })); }} />
          )}
          {errors.next && <div className="jp-field-error">{errors.next}</div>}
          {nextChoice !== 'none' && (
            <input className="theme-form-input" placeholder="Follow-up note (e.g. Send proposal)" maxLength={300}
              value={nextNote} aria-label="Follow-up note" onChange={(e) => setNextNote(e.target.value)} />
          )}
        </div>

        <div className="fu-modal-foot">
          <button type="button" className="theme-pill-btn" onClick={onClose}>Cancel</button>
          <button type="submit" className="theme-pill-btn primary" disabled={saving}>
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />} Save
          </button>
        </div>
      </form>
    </div>
  );
}

// ---------- Timeline drawer ----------
function TimelineDrawer({ leadId, onClose, onLog, onChanged }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    fetchLeadTimeline(leadId).then(setData).catch(err => setError(err.message));
  }, [leadId]);
  useEffect(() => { load(); }, [load]);

  const act = async (action, due = '') => {
    setBusy(true);
    try {
      await updateFollowup(data.pending_followup.activity_id, action, due);
      load();
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const lead = data?.lead || {};
  return (
    <div className="fu-overlay" role="dialog" aria-modal="true" aria-labelledby="fu-tl-title" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside className="fu-drawer">
        <div className="fu-modal-head">
          <div>
            <div className="theme-panel-title" id="fu-tl-title">{lead.name || 'Lead timeline'}</div>
            <div className="theme-panel-sub fu-clamp" title={[lead.status, lead.source, lead.email, lead.phone].filter(Boolean).join(' · ')}>
              {[lead.status, lead.source, lead.email, lead.phone].filter(Boolean).join(' · ')}
            </div>
          </div>
          <button type="button" className="jp-alert-close" aria-label="Close timeline" onClick={onClose}><X size={16} /></button>
        </div>

        {error && <div role="alert" className="jp-alert jp-alert-error"><AlertTriangle size={14} /> {error}</div>}
        {!data && !error && <div className="jp-hint"><Loader2 size={14} className="animate-spin" /> Loading…</div>}

        {data && (
          <>
            <div className="fu-pending-box">
              {data.pending_followup ? (
                <>
                  <div>
                    <div className="fu-pending-title"><CalendarClock size={14} /> Next follow-up {relative(data.pending_followup.due_at)}</div>
                    <div className="jp-hint">{formatTs(data.pending_followup.due_at)} · {data.pending_followup.summary}</div>
                  </div>
                  <div className="fu-row-actions">
                    <button type="button" className="theme-pill-btn" disabled={busy} onClick={() => act('done')}><Check size={13} /> Done</button>
                    <RescheduleControl disabled={busy} onPick={(d) => act('reschedule', d)} />
                  </div>
                </>
              ) : (
                <div className="jp-hint">No follow-up planned.</div>
              )}
            </div>

            <button type="button" className="theme-pill-btn primary" style={{ alignSelf: 'flex-start' }}
              onClick={() => onLog({ id: lead.id, name: lead.name })} disabled={!lead.name}>
              <Plus size={13} /> Log activity
            </button>

            <ol className="fu-timeline">
              {data.items.length === 0 && <li className="jp-hint">No activity yet.</li>}
              {data.items.map(item => (
                <li key={item.activity_id} className="fu-tl-item">
                  <TypeIcon type={item.type} />
                  <div className="fu-tl-body">
                    <div className="fu-tl-summary">
                      {item.summary}
                      {item.type === 'followup' && <span className={`fu-badge s-${item.followup_status}`}>{item.followup_status}</span>}
                    </div>
                    {item.details && <div className="fu-tl-details">{item.details}</div>}
                    <div className="jp-hint">
                      {item.type === 'followup' ? `Due ${formatTs(item.due_at)}` : formatTs(item.occurred_at)}
                      {' · '}{(TYPE_META[item.type] || {}).label}{item.source && item.source !== 'manual' ? ` · ${item.source}` : ''}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          </>
        )}
      </aside>
    </div>
  );
}

// ---------- Main view ----------
export default function FollowUpHistory({ leads = [], showToast }) {
  const [tab, setTab] = useState('queue');
  const [summary, setSummary] = useState(null);
  const [bucket, setBucket] = useState('all');
  const [queueItems, setQueueItems] = useState([]);
  const [queueLoading, setQueueLoading] = useState(false);
  const [history, setHistory] = useState({ items: [], total: 0 });
  const [historyType, setHistoryType] = useState('');
  const [historyQuery, setHistoryQuery] = useState('');
  const [historyLoading, setHistoryLoading] = useState(false);
  const [notice, setNotice] = useState(null);
  const [busyId, setBusyId] = useState('');
  const [importing, setImporting] = useState(false);
  const [logFor, setLogFor] = useState(undefined); // undefined = closed, null = no preselected lead
  const [timelineLead, setTimelineLead] = useState('');

  const say = (type, text) => setNotice({ type, text }); // inline message (no duplicate global toast)

  const loadSummary = useCallback(() => fetchFollowupSummary().then(setSummary).catch(() => {}), []);
  const loadQueue = useCallback(() => {
    setQueueLoading(true);
    fetchFollowupQueue(bucket)
      .then(res => setQueueItems(res.items || []))
      .catch(err => say('error', err.message))
      .finally(() => setQueueLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bucket]);
  const loadHistory = useCallback((offset = 0) => {
    setHistoryLoading(true);
    fetchFollowupHistory({ types: historyType ? [historyType] : [], q: historyQuery.trim(), limit: PAGE_SIZE, offset })
      .then(res => setHistory(prev => ({
        items: offset ? [...prev.items, ...(res.items || [])] : (res.items || []),
        total: res.total || 0
      })))
      .catch(err => say('error', err.message))
      .finally(() => setHistoryLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [historyType, historyQuery]);

  const refreshAll = useCallback(() => { loadSummary(); loadQueue(); loadHistory(0); }, [loadSummary, loadQueue, loadHistory]);

  useEffect(() => { loadSummary(); }, [loadSummary]);
  useEffect(() => { if (tab === 'queue') loadQueue(); }, [tab, loadQueue]);
  useEffect(() => {
    if (tab !== 'history') return undefined;
    const t = setTimeout(() => loadHistory(0), 250); // debounce typing in the search box
    return () => clearTimeout(t);
  }, [tab, loadHistory]);

  const actOnFollowup = async (item, action, due = '') => {
    setBusyId(item.activity_id);
    try {
      await updateFollowup(item.activity_id, action, due);
      say('success', action === 'done'
        ? `Marked done: ${item.lead_name || 'follow-up'}`
        : `Rescheduled ${item.lead_name || 'follow-up'} to ${due}`);
      loadQueue();
      loadSummary();
    } catch (err) {
      say('error', err.message);
    } finally {
      setBusyId('');
    }
  };

  const handleImport = async () => {
    setImporting(true);
    try {
      const r = await importSentEmailsHistory();
      say('success', `Imported ${r.imported} past emails (${r.matched_to_lead} linked to leads, ${r.unmatched} unmatched)` +
        (r.already_imported ? ` · ${r.already_imported} were already imported` : ''));
      refreshAll();
    } catch (err) {
      say('error', `Import failed: ${err.message}`);
    } finally {
      setImporting(false);
    }
  };

  const cards = [
    { id: 'overdue', label: 'Overdue', value: summary?.overdue, cls: 'red' },
    { id: 'today', label: 'Due today', value: summary?.today, cls: 'amber' },
    { id: 'upcoming', label: 'Next 7 days', value: summary?.upcoming, cls: 'blue' },
    { id: 'activity', label: 'Activities (last 7 days)', value: summary?.activities_7d, cls: 'green' }
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className="theme-card-panel" style={{ marginBottom: 0 }}>
        <div className="theme-panel-header">
          <div>
            <div className="theme-panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <History size={18} /> FollowUp History
            </div>
            <div className="theme-panel-sub">Every contact with a lead, and who to follow up with next.</div>
          </div>
          <div className="fu-row-actions">
            <button type="button" className="theme-pill-btn neutral" onClick={handleImport} disabled={importing}
              title="Copy emails sent before FollowUp History existed (logs/sent_emails.csv). Safe to run again.">
              {importing ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />} Import past emails
            </button>
            <button type="button" className="theme-pill-btn primary" onClick={() => setLogFor(null)}>
              <Plus size={13} /> Log activity
            </button>
          </div>
        </div>

        <div className="fu-cards">
          {cards.map(c => (
            <button
              type="button"
              key={c.id}
              className={`fu-card ${c.cls}`}
              onClick={() => { if (c.id !== 'activity') { setTab('queue'); setBucket(c.id); } else setTab('history'); }}
            >
              <span className="fu-card-value">{c.value ?? '—'}</span>
              <span className="fu-card-label">{c.label}</span>
            </button>
          ))}
        </div>
      </div>

      {notice && (
        <div role="status" className={`jp-alert ${notice.type === 'error' ? 'jp-alert-error' : 'jp-alert-success'}`}>
          {notice.type === 'error' && <AlertTriangle size={14} />}
          <span style={{ flex: 1 }}>{notice.text}</span>
          <button type="button" className="jp-alert-close" aria-label="Dismiss message" onClick={() => setNotice(null)}><X size={14} /></button>
        </div>
      )}

      <div className="fu-tabs" role="tablist">
        <button type="button" role="tab" aria-selected={tab === 'queue'} className={`fu-tab ${tab === 'queue' ? 'active' : ''}`} onClick={() => setTab('queue')}>
          Follow-up Queue {summary ? `(${summary.pending})` : ''}
        </button>
        <button type="button" role="tab" aria-selected={tab === 'history'} className={`fu-tab ${tab === 'history' ? 'active' : ''}`} onClick={() => setTab('history')}>
          Activity History {summary ? `(${summary.activities_total})` : ''}
        </button>
        <button type="button" role="tab" aria-selected={tab === 'sequences'} className={`fu-tab ${tab === 'sequences' ? 'active' : ''}`} onClick={() => setTab('sequences')}>
          Sequences
        </button>
        <button type="button" role="tab" aria-selected={tab === 'report'} className={`fu-tab ${tab === 'report' ? 'active' : ''}`} onClick={() => setTab('report')}>
          Report
        </button>
      </div>

      {tab === 'sequences' && <SequencesPanel onNotice={say} onChanged={() => { loadSummary(); }} />}
      {tab === 'report' && <ReportPanel />}

      {/* ---------- Queue ---------- */}
      {tab === 'queue' && (
        <div className="theme-table-container">
          <div className="fu-chip-group" style={{ paddingBottom: 12 }}>
            {BUCKETS.map(b => (
              <button key={b.id} type="button" className={`fu-chip ${bucket === b.id ? 'active' : ''}`} onClick={() => setBucket(b.id)}>
                {b.label}{summary && b.id !== 'all' ? ` (${summary[b.id] ?? 0})` : ''}
              </button>
            ))}
          </div>
          <div className="theme-table-scroll">
            <table className="jp-table">
              <thead>
                <tr><th>Lead</th><th>Follow-up</th><th>Due</th><th>Last contact</th><th style={{ width: 240 }}>Actions</th></tr>
              </thead>
              <tbody>
                {queueLoading && queueItems.length === 0 ? (
                  <tr><td colSpan={5} className="jp-empty"><Loader2 size={14} className="animate-spin" /> Loading…</td></tr>
                ) : queueItems.length === 0 ? (
                  <tr><td colSpan={5} className="jp-empty">No follow-ups here. Use “Log activity” to plan the next one.</td></tr>
                ) : queueItems.map(item => (
                  <tr key={item.activity_id}>
                    <td>
                      <button type="button" className="fu-link" onClick={() => setTimelineLead(item.lead_id)}>
                        {item.lead_name || item.lead_email || item.lead_id}
                      </button>
                      <div className="jp-cell-sub">{item.lead?.source || (item.lead_exists ? '' : 'Lead no longer in the database')}</div>
                    </td>
                    <td>{item.summary}</td>
                    <td>
                      <div className={`fu-due ${item.bucket}`}>{relative(item.due_at)}</div>
                      <div className="jp-cell-sub">{formatTs(item.due_at)}</div>
                    </td>
                    <td>
                      {item.last_contact ? (
                        <>
                          <div className="fu-inline"><TypeIcon type={item.last_contact.type} size={12} /> {item.last_contact.summary}</div>
                          <div className="jp-cell-sub">{relative(item.last_contact.occurred_at)}</div>
                        </>
                      ) : <span className="jp-hint">—</span>}
                    </td>
                    <td>
                      <div className="fu-row-actions">
                        <button type="button" className="theme-pill-btn" disabled={busyId === item.activity_id}
                          onClick={() => actOnFollowup(item, 'done')} aria-label={`Mark follow-up with ${item.lead_name} done`}>
                          <Check size={13} /> Done
                        </button>
                        <RescheduleControl disabled={busyId === item.activity_id} onPick={(d) => actOnFollowup(item, 'reschedule', d)} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ---------- History ---------- */}
      {tab === 'history' && (
        <div className="theme-table-container">
          <div className="theme-table-controls">
            <div className="theme-control-search">
              <Search size={14} color="#a3a7ae" />
              <input type="text" placeholder="Search lead, email or text…" value={historyQuery}
                onChange={(e) => setHistoryQuery(e.target.value)} aria-label="Search activity history" />
            </div>
            <select className="theme-form-input fu-select-sm" value={historyType} onChange={(e) => setHistoryType(e.target.value)} aria-label="Filter by type">
              <option value="">All types</option>
              {Object.entries(TYPE_META).map(([id, m]) => <option key={id} value={id}>{m.label}</option>)}
            </select>
            <span className="jp-hint">{history.items.length} of {history.total}</span>
          </div>
          <ol className="fu-timeline fu-feed">
            {history.items.length === 0 && !historyLoading && (
              <li className="jp-empty">No activity found. Send an email, change a lead’s status, log a call — or import past emails.</li>
            )}
            {history.items.map(item => (
              <li key={item.activity_id} className="fu-tl-item">
                <TypeIcon type={item.type} />
                <div className="fu-tl-body">
                  <div className="fu-tl-summary">
                    <button type="button" className="fu-link" onClick={() => item.lead_id && setTimelineLead(item.lead_id)} disabled={!item.lead_id}>
                      {item.lead_name || item.lead_email || 'Unknown lead'}
                    </button>
                    {' — '}{item.summary}
                    {item.type === 'followup' && <span className={`fu-badge s-${item.followup_status}`}>{item.followup_status}</span>}
                  </div>
                  <div className="jp-hint">
                    {item.type === 'followup' ? `Due ${formatTs(item.due_at)}` : formatTs(item.occurred_at)}
                    {' · '}{(TYPE_META[item.type] || {}).label}{item.source && item.source !== 'manual' ? ` · ${item.source}` : ''}
                  </div>
                </div>
              </li>
            ))}
          </ol>
          {history.items.length < history.total && (
            <button type="button" className="theme-pill-btn" style={{ alignSelf: 'center', marginTop: 12 }}
              disabled={historyLoading} onClick={() => loadHistory(history.items.length)}>
              {historyLoading ? <Loader2 size={13} className="animate-spin" /> : null} Load more
            </button>
          )}
        </div>
      )}

      {logFor !== undefined && (
        <LogActivityModal
          leads={leads}
          initialLead={logFor}
          onClose={() => setLogFor(undefined)}
          onSaved={(msg) => { setLogFor(undefined); say('success', msg); refreshAll(); if (timelineLead) setTimelineLead(t => t); }}
        />
      )}

      {timelineLead && (
        <TimelineDrawer
          key={timelineLead}
          leadId={timelineLead}
          onClose={() => setTimelineLead('')}
          onLog={(lead) => { setTimelineLead(''); setLogFor(lead); }}
          onChanged={() => { loadQueue(); loadSummary(); }}
        />
      )}
    </div>
  );
}
