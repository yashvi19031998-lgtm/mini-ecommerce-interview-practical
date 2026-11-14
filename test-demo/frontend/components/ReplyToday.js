'use client';

// Reply Today: fresh buyer posts (Reddit, Freelancer.com, Hacker News...) that have no e-mail address.
// The only way in is to answer on the post, so each row opens the post and gives a ready reply to copy.
// Backend: reply_today.py via /api/followups/reply-today, /reply-draft, /reply-done.

import React, { useEffect, useState } from 'react';
import { ExternalLink, Copy, Check, Loader2, Wand2, MessageSquare } from 'lucide-react';
import { fetchReplyToday, fetchReplyDraft, markReplyDone } from '../lib/api';

const DAY_OPTIONS = [1, 3, 7];
const CHANNEL_LABELS = {
  freelancer_bid: 'Freelancer bid', reddit: 'Reddit', hackernews: 'Hacker News', phone: 'Phone / WhatsApp',
  website: 'Website',
};

function band(score) {
  if (score === null || score === undefined) return 'unscored';
  return score >= 7 ? 'high' : score >= 4 ? 'medium' : 'low';
}

export default function ReplyToday({ onNotice = () => {} }) {
  const [days, setDays] = useState(3);
  const [channel, setChannel] = useState('all');
  const [data, setData] = useState({ items: [], counts: null });
  const [loading, setLoading] = useState(false);
  const [drafts, setDrafts] = useState({});      // id -> { text, by, note, loading }
  const [copied, setCopied] = useState('');
  const [done, setDone] = useState({});          // id -> true once marked replied

  useEffect(() => {
    setLoading(true);
    fetchReplyToday({ days })
      .then(res => setData({ items: res.items || [], counts: res.counts || null }))
      .catch(err => onNotice('error', err.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [days]);

  const write = async (id) => {
    setDrafts(d => ({ ...d, [id]: { ...(d[id] || {}), loading: true } }));
    try {
      const res = await fetchReplyDraft(id);
      setDrafts(d => ({ ...d, [id]: { text: res.text, by: res.by, note: res.note, loading: false } }));
    } catch (err) {
      setDrafts(d => ({ ...d, [id]: { ...(d[id] || {}), loading: false } }));
      onNotice('error', err.message);
    }
  };

  const copy = async (id) => {
    try {
      await navigator.clipboard.writeText(drafts[id]?.text || '');
      setCopied(id);
      setTimeout(() => setCopied(c => (c === id ? '' : c)), 1500);
    } catch {
      onNotice('error', 'Could not copy - select the text and copy it by hand.');
    }
  };

  const markDone = async (id) => {
    try {
      await markReplyDone(id, drafts[id]?.text || '');
      setDone(d => ({ ...d, [id]: true }));
    } catch (err) {
      onNotice('error', err.message);
    }
  };

  const byChannel = data.counts?.by_channel || {};
  const items = data.items.filter(i => channel === 'all' || i.channel === channel);

  return (
    <div className="theme-table-container">
      <div className="fu-chip-group" style={{ paddingBottom: 8, alignItems: 'center' }}>
        {DAY_OPTIONS.map(d => (
          <button key={d} type="button" className={`fu-chip ${days === d ? 'active' : ''}`} onClick={() => setDays(d)}>
            Last {d} day{d > 1 ? 's' : ''}
          </button>
        ))}
        <span className="jp-hint" style={{ margin: '0 4px' }}>|</span>
        <button type="button" className={`fu-chip ${channel === 'all' ? 'active' : ''}`} onClick={() => setChannel('all')}>
          All ({data.counts?.total ?? 0})
        </button>
        {Object.entries(byChannel).map(([c, n]) => (
          <button key={c} type="button" className={`fu-chip ${channel === c ? 'active' : ''}`} onClick={() => setChannel(c)}>
            {CHANNEL_LABELS[c] || c} ({n})
          </button>
        ))}
      </div>
      <div className="jp-hint" style={{ paddingBottom: 8 }}>
        People asking for IT or digital work right now, with no e-mail address - answer them on the post itself.
        Open the post, write a reply, copy it, post it there, then press &quot;Replied&quot;. Highest score first.
      </div>
      <div>
            {loading && items.length === 0 ? (
              <div className="jp-empty"><Loader2 size={14} className="animate-spin" /> Loading…</div>
            ) : items.length === 0 ? (
              <div className="jp-empty">No new posts to answer in this period.</div>
            ) : items.map(item => {
              const draft = drafts[item.id];
              const replied = done[item.id];
              return (
                <div key={item.id} className="rt-card" style={replied ? { opacity: 0.5 } : undefined}>
                  <div className="rt-post">
                    <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                      <span className={`fu-score b-${band(item.score)}`}>{item.score ?? '—'}</span>
                      <div style={{ fontWeight: 600, minWidth: 0, overflowWrap: 'anywhere' }}>
                        {(item.title || item.id).replace(/\s*--\s*\d+\s*$/, '')}
                      </div>
                    </div>
                    <div className="jp-cell-sub">
                      {CHANNEL_LABELS[item.channel] || item.channel} · {item.posted}
                      {item.budget ? ` · ${item.budget}` : ''}
                    </div>
                    {(item.requirement || item.summary) && (
                      <div className="jp-cell-sub fu-clamp" title={item.summary}>{item.requirement || item.summary}</div>
                    )}
                    <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
                      {item.url && (
                        <a className="theme-pill-btn" href={item.url} target="_blank" rel="noopener noreferrer">
                          <ExternalLink size={13} /> Open post
                        </a>
                      )}
                      {item.phone && <span className="jp-cell-sub">{item.phone}</span>}
                    </div>
                  </div>
                  <div className="rt-reply">
                    {draft?.text ? (
                      <>
                        <textarea
                          className="theme-form-textarea" rows={6} style={{ width: '100%', fontSize: 13 }}
                          value={draft.text}
                          onChange={(e) => setDrafts(d => ({ ...d, [item.id]: { ...d[item.id], text: e.target.value } }))}
                        />
                        {draft.note && <div className="jp-hint">{draft.note}</div>}
                      </>
                    ) : null}
                    <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
                      <button type="button" className="theme-pill-btn" disabled={draft?.loading || replied} onClick={() => write(item.id)}>
                        {draft?.loading ? <Loader2 size={13} className="animate-spin" /> : <Wand2 size={13} />}
                        {draft?.text ? ' Rewrite' : ' Write reply'}
                      </button>
                      {draft?.text && (
                        <button type="button" className="theme-pill-btn" onClick={() => copy(item.id)}>
                          {copied === item.id ? <Check size={13} /> : <Copy size={13} />} {copied === item.id ? 'Copied' : 'Copy'}
                        </button>
                      )}
                      <button type="button" className="theme-pill-btn" disabled={replied} onClick={() => markDone(item.id)}>
                        <MessageSquare size={13} /> {replied ? 'Replied' : 'Mark replied'}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
      </div>
    </div>
  );
}
