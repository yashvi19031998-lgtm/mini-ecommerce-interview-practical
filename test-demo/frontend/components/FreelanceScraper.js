'use client';

// Freelance Scraper: one button that runs only the freelance / contract-work sources
// (run_all_scrapers.py --group freelance --no-email), shows the live log, and leads to Reply Today.

import React, { useEffect, useRef, useState } from 'react';
import { Laptop, Play, Square, Loader2, MessageSquareReply, CheckCircle2, AlertTriangle } from 'lucide-react';
import { fetchScraperRun, startScraper, stopScraper } from '../lib/api';

const SOURCES = [
  { name: 'Freelancer.com', what: 'live projects with a budget (development, apps, SEO, digital marketing)' },
  { name: 'Reddit r/forhire & r/freelance_forhire', what: '[Hiring] posts' },
  { name: 'Reddit buyer & digital marketing search', what: '"looking for a developer", "need SEO", "need a marketing agency"…' },
  { name: 'Reddit subreddit feeds', what: 'r/jobbit, r/startups, r/smallbusiness and more' },
  { name: 'Hacker News', what: '"Who is hiring?" contract / freelance posts' },
  { name: 'We Work Remotely & Remotive', what: 'remote contract roles' },
  { name: 'DuckDuckGo', what: 'r/forhire, Upwork and Twitter "hiring" searches' },
  { name: 'Telegram', what: 'freelance channels (only when the Telegram keys are set)' },
];

function parseResult(logs) {
  const line = [...logs].reverse().find(l => l.startsWith('RUN_RESULT'));
  if (!line) return null;
  return Object.fromEntries(line.replace('RUN_RESULT', '').trim().split(/\s+/).map(kv => kv.split('=')).map(([k, v]) => [k, Number(v)]));
}

export default function FreelanceScraper({ showToast = () => {}, onLeadsSaved = () => {}, onOpenReplyToday = null }) {
  const [status, setStatus] = useState({ running: false, mode: '', logs: [] });
  const [starting, setStarting] = useState(false);
  const wasRunning = useRef(false);
  const logRef = useRef(null);

  const refresh = async () => {
    try {
      const s = await fetchScraperRun();
      setStatus({ running: !!s.running, mode: s.mode || '', logs: s.logs || [] });
      if (wasRunning.current && !s.running && s.mode === 'freelance') onLeadsSaved();
      wasRunning.current = !!s.running && s.mode === 'freelance';
    } catch {
      /* backend offline: the header already shows it */
    }
  };

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 2500);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [status.logs.length]);

  const mine = status.mode === 'freelance';
  const busyElsewhere = status.running && !mine;
  const result = mine && !status.running ? parseResult(status.logs) : null;

  const run = async () => {
    setStarting(true);
    try {
      await startScraper('freelance');
      wasRunning.current = true;
      showToast('Freelance scraper started - it takes a few minutes.', 'success');
      await refresh();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setStarting(false);
    }
  };

  const stop = async () => {
    try {
      await stopScraper();
      await refresh();
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  return (
    <div className="theme-card-panel" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="theme-panel-header">
        <div>
          <div className="theme-panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Laptop size={18} /> Freelance Scraper</div>
          <div className="theme-panel-sub">
            Finds people who want IT or digital marketing work done by a freelancer or developer right now. New posts are
            added to your leads and scored by the AI. No e-mail is sent - you answer them from Reports &rarr; Reply Today.
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        {status.running && mine ? (
          <button type="button" className="theme-pill-btn" onClick={stop}><Square size={14} /> Stop</button>
        ) : (
          <button type="button" className="theme-pill-btn primary" onClick={run} disabled={starting || busyElsewhere}>
            {starting ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} Run freelance scraper
          </button>
        )}
        {onOpenReplyToday && (
          <button type="button" className="theme-pill-btn" onClick={onOpenReplyToday}>
            <MessageSquareReply size={14} /> Open Reply Today
          </button>
        )}
        {status.running && mine && <span className="jp-hint"><Loader2 size={13} className="animate-spin" /> Running… (2-6 minutes)</span>}
        {busyElsewhere && <span className="jp-hint"><AlertTriangle size={13} /> Another scraper run is going on - wait for it to finish.</span>}
      </div>

      {result && (
        <div className="jp-alert jp-alert-success" role="status" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <CheckCircle2 size={16} />
          <span>
            Done: <b>{result.new}</b> new posts added ({result.collected} found, {result.updated} updated
            {result.failed ? `, ${result.failed} source(s) failed` : ''}). Answer them in Reply Today.
          </span>
        </div>
      )}

      <div>
        <div className="jp-hint" style={{ marginBottom: 6 }}>Sources in this run</div>
        <ul style={{ margin: 0, paddingLeft: 18, display: 'grid', gap: 4, fontSize: 14 }}>
          {SOURCES.map(s => <li key={s.name}><span style={{ fontWeight: 600 }}>{s.name}</span> <span className="jp-hint">- {s.what}</span></li>)}
        </ul>
      </div>

      {mine && status.logs.length > 0 && (
        <div>
          <div className="jp-hint" style={{ marginBottom: 6 }}>Live log</div>
          <pre ref={logRef} style={{ maxHeight: 320, overflow: 'auto', fontSize: 12, padding: 12, margin: 0,
            background: 'var(--bg-subtle)', borderRadius: 8, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
            {status.logs.join('\n')}
          </pre>
        </div>
      )}
    </div>
  );
}
