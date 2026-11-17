'use client';

// Lead Status: every lead in one "what next" stage - Replied, Follow-up due, Call / WhatsApp pending,
// Message pending, No reply, Mail pending, Waiting, and the skipped ones. Click a stage to see its leads
// with buttons to call / WhatsApp / mail / open the post, and to mark them done.
// Backend: lead_status.py via /api/reports/lead-status[/list|/done].

import React, { useEffect, useMemo, useState } from 'react';
import {
  Download, ExternalLink, Globe, Loader2, Mail, MessageCircle, Phone, Search, Check, X, ListChecks
} from 'lucide-react';
import { fetchLeadStatus, fetchLeadStatusList, markLeadContacted, patchLeadStatus } from '../../lib/api';
import { exportToCsv, formatNum } from './reportUtils';

const BANDS = [
  { id: 'all', label: 'All scores' },
  { id: 'high', label: 'High (7-10)' },
  { id: 'medium', label: 'Medium (4-6)' },
  { id: 'low', label: 'Low (0-3)' },
  { id: 'unscored', label: 'Not scored' },
];

const GROUPS = [
  { id: 'todo', title: 'Your to-do', hint: 'Work for you today' },
  { id: 'auto', title: 'System sends', hint: 'Auto-mail handles these' },
  { id: 'wait', title: 'Waiting', hint: 'Nothing to do yet' },
  { id: 'done', title: 'Skipped', hint: 'No action needed' },
];

const TONE = {
  replied: 'green', followup_due: 'red', call_pending: 'amber', message_pending: 'amber', no_reply: 'amber',
  mail_pending: 'blue', waiting: 'gray', old_post: 'gray', no_contact: 'gray', not_fit: 'gray', closed: 'gray',
};

// Which "I did it" buttons each stage shows
const DONE_BUTTONS = {
  replied: ['mailed', 'called', 'whatsapp'],
  followup_due: ['called', 'whatsapp', 'mailed'],
  call_pending: ['called', 'whatsapp'],
  message_pending: ['messaged'],
  no_reply: ['called', 'whatsapp', 'mailed'],
  mail_pending: ['mailed'],
};
const DONE_LABEL = { called: 'Called', whatsapp: 'WhatsApp sent', messaged: 'Replied on post', mailed: 'Mailed' };
const CONTACT_LABEL = { email_sent: 'auto-mail', email: 'mail', call: 'call', whatsapp: 'WhatsApp', message: 'post reply', meeting: 'meeting' };

export default function LeadStatusTab({ onNotice = () => {} }) {
  const [band, setBand] = useState(() => {
    try { return localStorage.getItem('lead_status_band') || 'all'; } catch { return 'all'; }
  });
  const [source, setSource] = useState('');
  const [query, setQuery] = useState('');
  const [q, setQ] = useState('');
  const [data, setData] = useState(null);
  const [stage, setStage] = useState(null);
  const [list, setList] = useState(null); // { items, total, loading }
  const [busy, setBusy] = useState({});
  const [reload, setReload] = useState(0);

  const opts = useMemo(() => ({ band, source, q }), [band, source, q]);

  // Search waits until typing stops
  useEffect(() => {
    const t = setTimeout(() => setQ(query.trim()), 350);
    return () => clearTimeout(t);
  }, [query]);

  useEffect(() => {
    fetchLeadStatus(opts)
      .then(res => {
        setData(res);
        // First visit: open the first to-do stage that has leads
        setStage(prev => prev || (res.stages.find(s => s.group === 'todo' && s.count) || res.stages.find(s => s.count) || res.stages[0])?.id);
      })
      .catch(err => onNotice('error', err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opts, reload]);

  useEffect(() => {
    if (!stage) return;
    let alive = true;
    setList(prev => ({ items: prev?.stage === stage ? prev.items : [], total: prev?.total || 0, loading: true, stage }));
    fetchLeadStatusList(stage, opts)
      .then(res => alive && setList({ items: res.items || [], total: res.total || 0, loading: false, stage }))
      .catch(err => { if (alive) { setList(null); onNotice('error', err.message); } });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage, opts, reload]);

  const pickBand = (id) => {
    setBand(id);
    try { localStorage.setItem('lead_status_band', id); } catch { /* private mode */ }
  };

  const removeFromList = (id) => setList(prev => prev && ({ ...prev, items: prev.items.filter(i => i.id !== id), total: Math.max(0, prev.total - 1) }));

  const done = async (item, action) => {
    setBusy(b => ({ ...b, [item.id]: true }));
    try {
      await markLeadContacted(item.id, action);
      removeFromList(item.id);
      onNotice('success', `${item.name}: marked "${DONE_LABEL[action]}"`);
      setReload(r => r + 1);
    } catch (err) {
      onNotice('error', err.message);
    } finally {
      setBusy(b => ({ ...b, [item.id]: false }));
    }
  };

  const notInterested = async (item) => {
    setBusy(b => ({ ...b, [item.id]: true }));
    try {
      await patchLeadStatus(item.id, 'LOST');
      removeFromList(item.id);
      setReload(r => r + 1);
    } catch (err) {
      onNotice('error', err.message);
    } finally {
      setBusy(b => ({ ...b, [item.id]: false }));
    }
  };

  const current = data?.stages.find(s => s.id === stage);

  const handleExport = () => {
    if (!list?.items.length) return;
    exportToCsv(`lead_status_${stage}.csv`,
      ['Lead', 'Score', 'Email', 'Phone', 'WhatsApp', 'Post link', 'Website', 'Source', 'Found', 'Last contact', 'Follow-up due', 'About'],
      list.items.map(i => [i.name, i.score ?? '', i.email, i.phone, i.whatsapp, i.link, i.website, i.source, i.found_at,
        i.last_contact, i.due, i.about]));
  };

  return (
    <div className="ls-wrap">
      {/* Filters */}
      <div className="ls-filters">
        <div className="rp-chip-group" style={{ flexWrap: 'wrap' }}>
          {BANDS.map(b => (
            <button key={b.id} type="button" className={`rp-chip ${band === b.id ? 'active' : ''}`} onClick={() => pickBand(b.id)}>
              {b.label}
            </button>
          ))}
        </div>
        <div className="ls-filter-row">
          <select className="ls-select" value={source} onChange={e => setSource(e.target.value)} aria-label="Source">
            <option value="">All sources</option>
            {(data?.sources || []).map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <div className="ls-search">
            <Search size={14} />
            <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search name, e-mail, phone…" aria-label="Search leads" />
            {query && <button type="button" onClick={() => setQuery('')} aria-label="Clear search"><X size={13} /></button>}
          </div>
        </div>
      </div>

      {/* Stage cards */}
      {!data ? (
        <div className="jp-empty"><Loader2 size={14} className="animate-spin" /> Loading…</div>
      ) : (
        <>
          <div className="ls-headline">
            <ListChecks size={18} />
            <span><strong>{formatNum(data.todo)}</strong> leads need you today · {formatNum(data.total)} leads in total</span>
          </div>
          <div className="ls-groups">
            {GROUPS.map(g => {
              const stages = data.stages.filter(s => s.group === g.id);
              return (
                <div key={g.id} className={`ls-group ls-group-${g.id}`}>
                  <div className="ls-group-title">{g.title}<span>{g.hint}</span></div>
                  <div className="ls-cards">
                    {stages.map(s => (
                      <button key={s.id} type="button" onClick={() => setStage(s.id)}
                        className={`ls-card tone-${TONE[s.id]} ${stage === s.id ? 'active' : ''}`} title={s.action}>
                        <span className="ls-card-count">{formatNum(s.count)}</span>
                        <span className="ls-card-label">{s.label}</span>
                        <span className="ls-card-action">{s.action}</span>
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* Leads of the chosen stage */}
      {current && (
        <div className="rp-table-card">
          <div className="rp-table-top">
            <div className="rp-table-title">
              {current.label} <span className="jp-hint">· {formatNum(list?.total ?? current.count)} leads · {current.action}</span>
            </div>
            <button type="button" className="theme-pill-btn neutral" onClick={handleExport} disabled={!list?.items.length}>
              <Download size={13} /> Export CSV
            </button>
          </div>
          {list?.loading && !list.items.length ? (
            <div className="jp-empty"><Loader2 size={14} className="animate-spin" /> Loading…</div>
          ) : !list?.items.length ? (
            <div className="jp-empty">No leads here. {current.group === 'todo' ? 'Nothing to do in this step 🎉' : ''}</div>
          ) : (
            <div className="ls-list">
              {list.items.map(i => (
                <div key={i.id} className="ls-item">
                  <div className="ls-item-main">
                    <div className="ls-item-top">
                      {i.score != null && <span className={`ls-score ${i.score >= 7 ? 'high' : i.score >= 4 ? 'mid' : 'low'}`}>{i.score}/10</span>}
                      <span className="ls-item-name">{i.name}</span>
                    </div>
                    {i.about && <div className="ls-item-about">{i.about}</div>}
                    <div className="ls-item-meta">
                      {i.source && <span>{i.source}</span>}
                      {i.found_at && <span>Found {i.found_at}</span>}
                      {i.last_contact && <span>Last {CONTACT_LABEL[i.last_contact_type] || 'contact'}: {i.last_contact}</span>}
                      {i.due && <span className="ls-due">Follow-up due {i.due}</span>}
                    </div>
                  </div>
                  <div className="ls-item-actions">
                    <div className="ls-contact">
                      {i.email && <a className="ls-btn" href={`mailto:${i.email}`} title={i.email}><Mail size={13} /> {i.email}</a>}
                      {i.phone && <a className="ls-btn" href={`tel:${i.phone.replace(/[^\d+]/g, '')}`}><Phone size={13} /> {i.phone}</a>}
                      {i.whatsapp && <a className="ls-btn wa" href={i.whatsapp} target="_blank" rel="noopener noreferrer"><MessageCircle size={13} /> WhatsApp</a>}
                      {i.link && <a className="ls-btn" href={i.link} target="_blank" rel="noopener noreferrer"><ExternalLink size={13} /> {i.platform ? `Open on ${i.platform}` : 'Open post'}</a>}
                      {i.website && !i.link && <a className="ls-btn" href={i.website.startsWith('http') ? i.website : `https://${i.website}`} target="_blank" rel="noopener noreferrer"><Globe size={13} /> Website</a>}
                    </div>
                    {(DONE_BUTTONS[stage] || current.group === 'todo') && (
                      <div className="ls-done">
                        {(DONE_BUTTONS[stage] || []).map(a => (
                          <button key={a} type="button" className="ls-btn done" disabled={busy[i.id]} onClick={() => done(i, a)}>
                            <Check size={13} /> {DONE_LABEL[a]}
                          </button>
                        ))}
                        <button type="button" className="ls-btn muted" disabled={busy[i.id]} onClick={() => notInterested(i)} title="Close this lead (status LOST)">
                          Not interested
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {list.total > list.items.length && (
                <div className="jp-hint" style={{ padding: '0.75rem 1.25rem' }}>
                  Showing the best {list.items.length} of {formatNum(list.total)}. Use the score / source filter or search to narrow down.
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
