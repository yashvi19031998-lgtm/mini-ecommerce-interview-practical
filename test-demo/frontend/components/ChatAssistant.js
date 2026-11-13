'use client';

// In-app chat assistant ("Ask LeadsGen"): a floating button that opens a small chat panel.
// Answers come from /api/chat (chat_assistant.py) - read-only questions about leads, e-mails, scrapers.

import React, { useEffect, useRef, useState } from 'react';
import { MessageCircle, X, Send, Loader2, Bot } from 'lucide-react';
import { askAssistant } from '../lib/api';

const STARTERS = [
  'Aaje ketla nava leads?',
  'Aaje ketla mail gaya?',
  'Kayo scraper saro che?',
  'Ahmedabad na website vagar na leads',
  'Follow-up baki',
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
      const res = await askAssistant(q);
      setMessages(prev => [...prev, {
        role: 'bot', text: res.reply, table: res.table, suggestions: res.suggestions || [], engine: res.engine
      }]);
    } catch (err) {
      setMessages(prev => [...prev, { role: 'bot', text: err.message || 'Could not get an answer. Is the backend running?', error: true }]);
    } finally {
      setBusy(false);
    }
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
                <p>Puchho tamara leads, mail, follow-up ane scrapers vishe — English, Gujarati ke Gujlish ma.</p>
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
