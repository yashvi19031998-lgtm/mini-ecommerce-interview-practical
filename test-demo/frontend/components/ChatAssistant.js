'use client';

// In-app chat assistant ("Ask LeadsGen"): a floating button that opens a small chat panel.
// Answers come from /api/chat (chat_assistant.py) - read-only questions about leads, e-mails, scrapers.

import React, { useEffect, useRef, useState } from 'react';
import { MessageCircle, X, Send, Loader2, Bot, ThumbsUp, ThumbsDown } from 'lucide-react';
import { askAssistant, rateAssistantAnswer } from '../lib/api';

const STARTERS = [
  'Aaje shu karu?',
  'Mail flow kevi rite chale che?',
  'Aa mahina no report',
  'Mail gayo pan call nathi thayo te leads batav',
  'Gai kale shu thayu?',
  'Hot leads this week'
];

const COLUMN_LABELS = {
  lead_id: 'Lead', company: 'Company', email: 'E-mail', phone: 'Phone', location: 'Location',
  source: 'Source', score: 'Score', status: 'Status', scraper: 'Scraper', runs: 'Runs',
  records: 'Records', new_leads: 'New leads', failed: 'Failed', leads: 'Leads', hot: 'Hot',
  with_contact_pct: 'Contact %'
};

function ResultTable({ table }) {
  if (!table || !table.rows || table.rows.length === 0) return null;
  return (
    <div className="ca-table-wrap">
      <table className="ca-table">
        <thead>
          <tr>{table.columns.map(c => <th key={c}>{COLUMN_LABELS[c] || c}</th>)}</tr>
        </thead>
        <tbody>
          {table.rows.map((r, i) => (
            <tr key={i}>{table.columns.map(c => <td key={c}>{r[c] === '' || r[c] === undefined ? '—' : String(r[c])}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ChatAssistant() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const listRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages, busy]);

  useEffect(() => {
    if (!open) return undefined;
    inputRef.current?.focus();
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  const ask = async (text) => {
    const q = String(text || '').trim();
    if (!q || busy) return;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', text: q }]);
    setBusy(true);
    try {
      // last few turns, so follow-ups like "only the ones with an e-mail" are understood
      const history = messages.filter(m => !m.error).slice(-6).map(m => ({ role: m.role === 'user' ? 'user' : 'assistant', text: m.text }));
      const res = await askAssistant(q, history);
      setMessages(prev => [...prev, {
        role: 'bot', question: q, text: res.reply, table: res.table, suggestions: res.suggestions || [], engine: res.engine, note: res.note
      }]);
    } catch (err) {
      setMessages(prev => [...prev, { role: 'bot', text: err.message || 'Could not get an answer. Is the backend running?', error: true }]);
    } finally {
      setBusy(false);
    }
  };

  // Rating teaches the assistant: helpful answers are reused as examples, unhelpful ones get more effort
  const rate = async (i, helpful) => {
    const m = messages[i];
    setMessages(prev => prev.map((x, n) => (n === i ? { ...x, rated: helpful ? 'up' : 'down' } : x)));
    try { await rateAssistantAnswer(m.question, m.text, helpful); } catch { /* rating is optional */ }
  };

  return (
    <>
      {!open && (
        <button type="button" className="ca-launcher" onClick={() => setOpen(true)} aria-label="Open the LeadsGen assistant" title="Ask LeadsGen">
          <MessageCircle size={22} />
        </button>
      )}

      {open && (
        <section className="ca-panel" role="dialog" aria-label="LeadsGen assistant">
          <header className="ca-head">
            <div className="ca-title"><Bot size={17} /> Ask LeadsGen</div>
            <button type="button" className="ca-close" onClick={() => setOpen(false)} aria-label="Close the assistant"><X size={17} /></button>
          </header>

          <div className="ca-list" ref={listRef} aria-live="polite">
            {messages.length === 0 && (
              <div className="ca-intro">
                <p>Puchho kai pan: aaje shu karvanu, mail flow, koi pan date no report, ek lead ni vigat, system kevi rite chale che — English, Gujarati ke Gujlish ma.</p>
                <p className="ca-tip">Shikhvado: “yaad rakh: …” lakho, te pachhi dar javab ma dhyan rakhshe.</p>
                <div className="ca-chips">
                  {STARTERS.map(s => <button key={s} type="button" className="ca-chip" onClick={() => ask(s)}>{s}</button>)}
                </div>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`ca-msg ${m.role === 'user' ? 'ca-user' : 'ca-bot'} ${m.error ? 'ca-error' : ''}`}>
                <div className="ca-bubble">{m.text}</div>
                {m.role === 'bot' && <ResultTable table={m.table} />}
                {m.role === 'bot' && m.suggestions && m.suggestions.length > 0 && (
                  <div className="ca-chips">
                    {m.suggestions.map(s => <button key={s} type="button" className="ca-chip" onClick={() => ask(s)}>{s}</button>)}
                  </div>
                )}
                {m.role === 'bot' && m.engine === 'gemini' && <div className="ca-note">Answered by Gemini AI from your data</div>}
                {m.role === 'bot' && m.engine === 'claude' && <div className="ca-note">Answered by Claude AI from your data</div>}
                {m.role === 'bot' && m.note && <div className="ca-note">{m.note}</div>}
                {m.role === 'bot' && !m.error && m.question && (
                  <div className="ca-rate">
                    {m.rated ? <span>{m.rated === 'up' ? 'Thanks - I will answer like this again.' : 'Noted - I will try harder on this question.'}</span> : (
                      <>
                        <button type="button" onClick={() => rate(i, true)} aria-label="Helpful answer" title="Helpful"><ThumbsUp size={13} /></button>
                        <button type="button" onClick={() => rate(i, false)} aria-label="Not helpful" title="Not helpful"><ThumbsDown size={13} /></button>
                      </>
                    )}
                  </div>
                )}
              </div>
            ))}
            {busy && <div className="ca-msg ca-bot"><div className="ca-bubble ca-typing"><Loader2 size={14} className="animate-spin" /> Thinking…</div></div>}
          </div>

          <form className="ca-input-row" onSubmit={(e) => { e.preventDefault(); ask(input); }}>
            <input
              ref={inputRef}
              className="ca-input"
              value={input}
              maxLength={500}
              onChange={(e) => setInput(e.target.value)}
              placeholder="e.g. Aaje ketla hot leads?"
              aria-label="Your question"
            />
            <button type="submit" className="ca-send" disabled={busy || !input.trim()} aria-label="Send"><Send size={16} /></button>
          </form>
        </section>
      )}
    </>
  );
}
