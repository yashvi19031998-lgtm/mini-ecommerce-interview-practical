'use client';

// WhatsApp desk: today's WhatsApp list, sent one by one from your own WhatsApp - no bot, so the number stays safe.
// The app picks who (mailed-but-not-called first, best score first), writes the message and opens WhatsApp
// with it typed. You press Send in WhatsApp, come back and press "Sent" - the next lead is ready.
// Follow-ups: one short second message 3 days after the first if there was no answer.
// Backend: whatsapp_desk.py via /api/whatsapp/desk and /api/whatsapp/sent.

import React, { useCallback, useEffect, useState } from 'react';
import { Check, ExternalLink, Loader2, MessageCircle, SkipForward, Sparkles, Clock, AlertTriangle } from 'lucide-react';
import { fetchWhatsAppDesk, markWhatsAppSent, fetchPhoneKit } from '../../lib/api';
import { whatsappUrl, niceDate } from '../../lib/leadMeta';

export default function WhatsAppDesk({ onOpenLead, notify = () => {} }) {
  const [data, setData] = useState(null);
  const [tab, setTab] = useState('new');
  const [pos, setPos] = useState(0);
  const [text, setText] = useState('');
  const [opened, setOpened] = useState(false);
  const [busy, setBusy] = useState('');
  const [skipped, setSkipped] = useState([]);

  const load = useCallback(() => {
    fetchWhatsAppDesk(40)
      .then(res => setData(res))
      .catch(err => notify(err.message, 'error'));
  }, [notify]);
  useEffect(() => { load(); }, [load]);

  const list = (data?.[tab] || []).filter(i => !skipped.includes(i.id));
  const item = list[Math.min(pos, Math.max(0, list.length - 1))];

  useEffect(() => { setText(item?.text || ''); setOpened(false); }, [item?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const limitReached = data && data.left_today <= 0;
  const waHref = item ? `${whatsappUrl(item.phone)}?text=${encodeURIComponent(text)}` : '';

  const sent = async () => {
    setBusy('sent');
    try {
      const res = await markWhatsAppSent(item.id, text, item.kind);
      notify(`${item.name}: WhatsApp logged (${res.sent_today} / ${res.daily_limit} today)`, 'success');
      setData(d => ({
        ...d,
        [tab]: d[tab].filter(i => i.id !== item.id),
        counts: { ...d.counts, [tab]: Math.max(0, d.counts[tab] - 1) },
        sent_today: res.sent_today, left_today: Math.max(0, res.daily_limit - res.sent_today),
      }));
    } catch (err) {
      notify(err.message, 'error');
    } finally {
      setBusy('');
    }
  };

  const skip = () => { setSkipped(s => [...s, item.id]); };

  const aiText = async () => {
    setBusy('ai');
    try {
      const res = await fetchPhoneKit(item.id, true);
      if (res.whatsapp) setText(res.whatsapp);
      if (res.by !== 'ai') notify('AI is not available (no key) - the standard text is shown.', 'info');
    } catch (err) {
      notify(err.message, 'error');
    } finally {
      setBusy('');
    }
  };

  if (!data) return <div className="td-loading"><Loader2 size={16} className="animate-spin" /> Loading today's WhatsApp list…</div>;

  return (
    <div className="wd">
      <header className="wd-head">
        <div>
          <h1 className="lv-title">WhatsApp</h1>
          <p className="lv-sub">Send from your own WhatsApp, one by one: the message is written for you, you press Send.</p>
        </div>
        <div className="wd-stats">
          <span className={`wd-stat ${limitReached ? 'warn' : ''}`}><MessageCircle size={14} /> {data.sent_today} / {data.daily_limit} sent today</span>
          <span className={`wd-stat ${data.office_hours ? 'ok' : 'warn'}`}>
            <Clock size={14} /> {data.office_hours ? 'Office hours' : 'Outside office hours (Mon–Sat 10–19)'}
          </span>
        </div>
      </header>

      <div className="seg-group" role="tablist" aria-label="WhatsApp list">
        {[['new', 'New'], ['followup', 'Follow-up']].map(([id, label]) => (
          <button key={id} type="button" role="tab" aria-selected={tab === id} className={`seg ${tab === id ? 'on' : ''}`}
            onClick={() => { setTab(id); setPos(0); }}>
            {label} <span className="fchip-n">{(data.counts[id] || 0).toLocaleString()}</span>
          </button>
        ))}
      </div>

      {limitReached && (
        <div className="wd-note warn"><AlertTriangle size={16} /> Today's limit of {data.daily_limit} WhatsApps is reached. More in one day looks like spam to WhatsApp and can get the number blocked. Continue tomorrow.</div>
      )}

      {!item ? (
        <div className="lv-empty">
          <p><strong>{tab === 'new' ? 'No new leads to WhatsApp right now.' : 'No follow-ups due.'}</strong></p>
          <p>{tab === 'new' ? 'Leads with a phone number show up here as they are found.' : 'A follow-up shows here 3 days after a WhatsApp that got no answer.'}</p>
        </div>
      ) : (
        <div className="wd-grid">
          <section className="wd-card" aria-label={`WhatsApp to ${item.name}`}>
            <div className="wd-card-top">
              {item.score != null && <span className={`score s-${item.band}`}>{item.score}</span>}
              <button type="button" className="wd-name" onClick={() => onOpenLead && onOpenLead(item.id)} title="Open lead details">{item.name}</button>
              <span className="pill tone-amber">{item.kind === 'followup' ? 'Follow-up' : item.stage_label}</span>
            </div>
            {item.about && <p className="wd-about">{item.about}</p>}
            <p className="wd-meta">
              {item.phone} · {item.source}{item.found_at ? ` · found ${niceDate(item.found_at)}` : ''}
              {item.last_whatsapp ? ` · first WhatsApp ${niceDate(item.last_whatsapp)}` : ''}
              {item.post && <> · <a href={item.post} target="_blank" rel="noopener noreferrer">post <ExternalLink size={11} /></a></>}
            </p>

            <label className="wd-label" htmlFor="wd-text">Message</label>
            <textarea id="wd-text" className="lp-wa-text" rows={6} value={text} onChange={e => setText(e.target.value)} />
            <div className="wd-actions">
              <button type="button" className="td-link" onClick={aiText} disabled={!!busy}>
                {busy === 'ai' ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />} Write with AI
              </button>
              <span className="wd-count">{text.length} characters</span>
            </div>

            {!opened ? (
              <div className="wd-buttons">
                <a className={`btn btn-wa wd-open ${limitReached ? 'disabled' : ''}`} href={limitReached ? undefined : waHref}
                  target="_blank" rel="noopener noreferrer" onClick={() => !limitReached && setOpened(true)} aria-disabled={limitReached}>
                  <MessageCircle size={16} /> Open in WhatsApp
                </a>
                <button type="button" className="btn btn-ghost" onClick={skip}><SkipForward size={15} /> Skip</button>
              </div>
            ) : (
              <div className="wd-confirm">
                <span>Did you press Send in WhatsApp?</span>
                <button type="button" className="btn btn-primary" onClick={sent} disabled={!!busy}>
                  {busy === 'sent' ? <Loader2 size={15} className="animate-spin" /> : <Check size={15} />} Yes, sent - next
                </button>
                <button type="button" className="btn btn-ghost" onClick={() => setOpened(false)}>Not sent</button>
              </div>
            )}
          </section>

          <aside className="wd-next" aria-label="Up next">
            <h2 className="td-card-title">Up next ({Math.max(0, list.length - 1)})</h2>
            <ol>
              {list.filter(i => i.id !== item.id).slice(0, 12).map(i => (
                <li key={i.id}>
                  <button type="button" onClick={() => setPos(list.indexOf(i))}>
                    {i.score != null && <span className={`score s-${i.band}`}>{i.score}</span>}
                    <span className="wd-next-name">{i.name}</span>
                  </button>
                </li>
              ))}
            </ol>
            <p className="wd-tip">Tip: keep it to about {data.daily_limit} a day, during office hours, each message a little different. That is what keeps a WhatsApp number from being blocked.</p>
          </aside>
        </div>
      )}
    </div>
  );
}
