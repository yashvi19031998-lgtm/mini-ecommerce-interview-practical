'use client';

// Lead panel: slides in from the right on Today and Leads. Everything about one lead in one place:
// what to do next (with the buttons to do it), how to reach them, what they need, the outcome, a
// follow-up date and the full history. Replaces the read-only "Dossier" modal as the main detail view.

import React, { useEffect, useState } from 'react';
import {
  X, Mail, Phone, MessageCircle, ExternalLink, Globe, Link2, Check, Copy, CalendarPlus, Loader2,
  Clock, Send, PhoneCall, StickyNote, Reply, Ban, ArrowRightLeft, Sparkles
} from 'lucide-react';
import { fetchLeadTimeline, markLeadContacted, patchLeadStatus, scheduleFollowup } from '../../lib/api';
import {
  ACTIONS, BANDS, OUTCOMES, OUTCOME_LABEL, leadName, leadAbout, leadEmail, leadPhone, whatsappUrl,
  postUrl, websiteUrl, leadScore, leadOutcome, leadSource, niceDate
} from '../../lib/leadMeta';

const DONE_BY_ACTION = {
  replied: ['mailed', 'called', 'whatsapp'],
  followup_due: ['called', 'whatsapp', 'mailed'],
  call_pending: ['called', 'whatsapp'],
  message_pending: ['messaged'],
  no_reply: ['called', 'whatsapp', 'mailed'],
  mail_pending: ['mailed'],
  waiting: ['called', 'whatsapp', 'mailed'],
};
const DONE_LABEL = { called: 'I called', whatsapp: 'I sent a WhatsApp', messaged: 'I replied on the post', mailed: 'I sent a mail' };

const EVENT = {
  email_sent: { icon: Send, label: 'Auto-mail sent' },
  email: { icon: Mail, label: 'Mail' },
  call: { icon: PhoneCall, label: 'Call' },
  whatsapp: { icon: MessageCircle, label: 'WhatsApp' },
  message: { icon: Reply, label: 'Post reply' },
  meeting: { icon: CalendarPlus, label: 'Meeting' },
  note: { icon: StickyNote, label: 'Note' },
  reply: { icon: Reply, label: 'They replied' },
  status_change: { icon: ArrowRightLeft, label: 'Status' },
  followup: { icon: Clock, label: 'Follow-up planned' },
  bounce: { icon: Ban, label: 'Bounced' },
  opted_out: { icon: Ban, label: 'Asked to stop' },
};

const inDays = (n) => {
  const d = new Date();
  d.setDate(d.getDate() + n);
  d.setHours(10, 0, 0, 0);
  const p = (x) => String(x).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} 10:00:00`;
};

export default function LeadPanel({ lead, onClose, onChanged = () => {}, onEmail, onWhatsApp, notify = () => {} }) {
  const [timeline, setTimeline] = useState(null);
  const [busy, setBusy] = useState('');
  const [copied, setCopied] = useState('');

  const id = lead?.id || lead?.lead_id;

  useEffect(() => {
    if (!id) return undefined;
    let alive = true;
    setTimeline(null);
    fetchLeadTimeline(id)
      .then(res => alive && setTimeline(res))
      .catch(() => alive && setTimeline({ items: [] }));
    return () => { alive = false; };
  }, [id]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  if (!lead) return null;

  const action = ACTIONS[lead.next_action] || null;
  const band = BANDS[lead.band] || BANDS.unscored;
  const score = leadScore(lead);
  const email = leadEmail(lead);
  const phone = leadPhone(lead);
  const wa = whatsappUrl(phone);
  const post = postUrl(lead);
  const site = websiteUrl(lead);
  const linkedin = String(lead.linkedin_url || '').startsWith('http') ? lead.linkedin_url : '';
  const outcome = leadOutcome(lead);
  const about = leadAbout(lead);

  const run = async (key, fn, okText) => {
    setBusy(key);
    try {
      await fn();
      if (okText) notify(okText, 'success');
      onChanged();
      const res = await fetchLeadTimeline(id).catch(() => null);
      if (res) setTimeline(res);
    } catch (err) {
      notify(err.message || 'That did not save', 'error');
    } finally {
      setBusy('');
    }
  };

  const copy = (text, key) => {
    navigator.clipboard?.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(''), 1500);
  };

  const facts = [
    ['Needs', lead.ai_tech_stack],
    ['Budget', lead.ai_budget || lead.deal_size_estimate],
    ['Location', lead.location || lead.Address],
    ['Source', leadSource(lead)],
    ['Found', niceDate(lead.first_seen_at)],
    ['Last contact', lead.last_contact ? niceDate(lead.last_contact) : 'Never'],
  ].filter(([, v]) => v && String(v).trim() && !['nan', 'n/a'].includes(String(v).toLowerCase()));

  return (
    <>
      <div className="lp-backdrop" onClick={onClose} aria-hidden="true" />
      <aside className="lp" role="dialog" aria-modal="true" aria-label={`Lead: ${leadName(lead)}`}>
        <header className="lp-head">
          <div className="lp-title-wrap">
            <div className="lp-chips">
              <span className={`chip tone-${band.tone}`}>{band.label}{score !== null ? ` · ${score}/10` : ''}</span>
              <span className="chip tone-gray">{OUTCOME_LABEL[outcome]}</span>
            </div>
            <h2 className="lp-title">{leadName(lead)}</h2>
            {lead.full_name && lead.full_name !== leadName(lead) && <div className="lp-sub">{lead.full_name}</div>}
          </div>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close"><X size={18} /></button>
        </header>

        <div className="lp-body">
          {/* What to do next */}
          {action && (
            <section className={`lp-next tone-${action.tone}`}>
              <div className="lp-next-label">Next step</div>
              <div className="lp-next-title">{action.label}</div>
              <div className="lp-next-hint">{action.hint}{lead.followup_due ? ` · due ${lead.followup_due}` : ''}</div>
              {(DONE_BY_ACTION[lead.next_action] || []).length > 0 && (
                <div className="lp-next-done">
                  {DONE_BY_ACTION[lead.next_action].map(a => (
                    <button key={a} type="button" className="btn btn-soft" disabled={!!busy}
                      onClick={() => run(a, () => markLeadContacted(id, a), `${leadName(lead)}: logged`)}>
                      {busy === a ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />} {DONE_LABEL[a]}
                    </button>
                  ))}
                </div>
              )}
            </section>
          )}

          {/* Reach them */}
          <section className="lp-section">
            <h3 className="lp-h">Contact</h3>
            {!email && !phone && !post && !site && <p className="lp-empty">No contact details yet.</p>}
            <div className="lp-contact">
              {email && (
                <div className="lp-row">
                  <Mail size={15} />
                  <span className="lp-row-text">{email}</span>
                  <button type="button" className="icon-btn sm" onClick={() => copy(email, 'email')} aria-label="Copy e-mail">
                    {copied === 'email' ? <Check size={14} /> : <Copy size={14} />}
                  </button>
                  {onEmail && <button type="button" className="btn btn-primary sm" onClick={() => onEmail(lead)}>Write mail</button>}
                </div>
              )}
              {phone && (
                <div className="lp-row">
                  <Phone size={15} />
                  <span className="lp-row-text">{phone}</span>
                  <a className="btn btn-ghost sm" href={`tel:${phone.replace(/[^\d+]/g, '')}`}>Call</a>
                  {wa && <a className="btn btn-wa sm" href={wa} target="_blank" rel="noopener noreferrer"><MessageCircle size={14} /> WhatsApp</a>}
                  {onWhatsApp && <button type="button" className="icon-btn sm" title="Write a WhatsApp message with a template" onClick={() => onWhatsApp(lead)}><Sparkles size={14} /></button>}
                </div>
              )}
              <div className="lp-links">
                {post && <a className="btn btn-ghost sm" href={post} target="_blank" rel="noopener noreferrer"><ExternalLink size={14} /> Open post</a>}
                {site && <a className="btn btn-ghost sm" href={site} target="_blank" rel="noopener noreferrer"><Globe size={14} /> Website</a>}
                {linkedin && <a className="btn btn-ghost sm" href={linkedin} target="_blank" rel="noopener noreferrer"><Link2 size={14} /> LinkedIn</a>}
              </div>
            </div>
          </section>

          {/* What they need */}
          {(about || facts.length > 0) && (
            <section className="lp-section">
              <h3 className="lp-h">About this lead</h3>
              {about && <p className="lp-about">{about}</p>}
              <dl className="lp-facts">
                {facts.map(([k, v]) => (
                  <React.Fragment key={k}><dt>{k}</dt><dd>{String(v)}</dd></React.Fragment>
                ))}
              </dl>
            </section>
          )}

          {/* Outcome + follow-up */}
          <section className="lp-section">
            <h3 className="lp-h">Outcome</h3>
            <div className="lp-outcomes" role="radiogroup" aria-label="Outcome">
              {OUTCOMES.filter(o => o !== 'DISQUALIFIED').map(o => (
                <button key={o} type="button" role="radio" aria-checked={outcome === o}
                  className={`seg ${outcome === o ? 'on' : ''}`} disabled={!!busy}
                  onClick={() => outcome !== o && run(`o-${o}`, () => patchLeadStatus(id, o), `Marked ${OUTCOME_LABEL[o]}`)}>
                  {OUTCOME_LABEL[o]}
                </button>
              ))}
            </div>
            <div className="lp-follow">
              <span className="lp-follow-label"><CalendarPlus size={14} /> Remind me</span>
              {[['Tomorrow', 1], ['In 3 days', 3], ['Next week', 7]].map(([label, n]) => (
                <button key={label} type="button" className="btn btn-ghost sm" disabled={!!busy}
                  onClick={() => run(`f-${n}`, () => scheduleFollowup({ lead_id: id, due_at: inDays(n), note: 'Follow up' }), `Follow-up set: ${label.toLowerCase()}`)}>
                  {label}
                </button>
              ))}
            </div>
            {timeline?.pending_followup && (
              <p className="lp-note">Follow-up planned for {niceDate(timeline.pending_followup.due_at)} ({String(timeline.pending_followup.due_at).slice(0, 16)})</p>
            )}
          </section>

          {/* History */}
          <section className="lp-section">
            <h3 className="lp-h">History</h3>
            {!timeline ? (
              <p className="lp-empty"><Loader2 size={14} className="animate-spin" /> Loading…</p>
            ) : !timeline.items?.length ? (
              <p className="lp-empty">Nothing yet. Contact them and it shows here.</p>
            ) : (
              <ol className="lp-timeline">
                {timeline.items.map(ev => {
                  const meta = EVENT[ev.type] || { icon: StickyNote, label: ev.type };
                  const Icon = meta.icon;
                  return (
                    <li key={ev.activity_id}>
                      <span className="lp-tl-icon"><Icon size={13} /></span>
                      <div>
                        <div className="lp-tl-top"><strong>{meta.label}</strong> <span>{String(ev.occurred_at || '').slice(0, 16)}</span></div>
                        {ev.summary && <div className="lp-tl-text">{ev.summary}</div>}
                      </div>
                    </li>
                  );
                })}
              </ol>
            )}
          </section>
        </div>

        <footer className="lp-foot">
          <button type="button" className="btn btn-ghost" disabled={!!busy || outcome === 'LOST'}
            onClick={() => run('lost', () => patchLeadStatus(id, 'LOST'), 'Closed as not interested')}>
            Not interested
          </button>
          <span className="lp-id">{id}</span>
        </footer>
      </aside>
    </>
  );
}
