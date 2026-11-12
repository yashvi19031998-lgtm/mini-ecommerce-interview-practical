'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { KeyRound, CheckCircle2, AlertTriangle, CircleDashed, ExternalLink, RefreshCw, Loader2 } from 'lucide-react';
import { fetchApiKeysStatus } from '../lib/api';

const STATUS = {
  configured: { label: 'Configured', cls: 'ok', Icon: CheckCircle2 },
  fallback: { label: 'Using SMTP login', cls: 'ok', Icon: CheckCircle2 },
  partial: { label: 'Incomplete', cls: 'warn', Icon: AlertTriangle },
  missing: { label: 'Not set', cls: 'off', Icon: CircleDashed },
};
const COST = { free: 'Free', limited: 'Free (limited)', paid: 'Paid' };

// Lists every API key the app uses and whether it is set in .env. Values are never sent to the browser.
export default function ApiKeysPanel() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState('all');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      setData(await fetchApiKeysStatus());
    } catch (err) {
      setError(err.message || 'Could not load API key status. Is the Python backend running?');
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  const groups = useMemo(() => {
    const out = [];
    for (const it of data?.items || []) {
      if (filter === 'missing' && !['missing', 'partial'].includes(it.status)) continue;
      if (filter === 'free' && it.cost === 'paid') continue;
      let g = out.find(x => x.name === it.group);
      if (!g) out.push(g = { name: it.group, items: [] });
      g.items.push(it);
    }
    return out;
  }, [data, filter]);

  const c = data?.counts || {};
  return (
    <div className="glass-panel">
      <div className="ak-head">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <div style={{ background: 'var(--bg-lavender-light)', color: 'var(--primary-lavender)', padding: '7px', borderRadius: '8px' }}>
            <KeyRound size={18} />
          </div>
          <div>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)' }}>API Keys &amp; Integrations</h3>
            <p style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
              Add keys in <code>test-demo/.env</code>, then restart the Python backend. Key values are never shown here.
            </p>
          </div>
        </div>
        <button type="button" className="btn btn-secondary btn-sm" onClick={load} disabled={loading} aria-label="Refresh API key status">
          {loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />} Refresh
        </button>
      </div>

      {error && <div role="alert" className="jp-alert jp-alert-error"><AlertTriangle size={14} /> {error}</div>}

      {data && (
        <>
          <div className="ak-summary">
            <span><strong>{(c.configured || 0) + (c.fallback || 0)}</strong> of {data.total} set up</span>
            {c.partial ? <span className="ak-warn-text">{c.partial} incomplete</span> : null}
            <div style={{ flex: 1 }} />
            <div className="ak-filters" role="group" aria-label="Filter integrations">
              {[['all', 'All'], ['missing', 'Not set'], ['free', 'Free only']].map(([v, l]) => (
                <button key={v} type="button" className={`ak-filter ${filter === v ? 'active' : ''}`} aria-pressed={filter === v} onClick={() => setFilter(v)}>{l}</button>
              ))}
            </div>
          </div>

          {groups.length === 0 && <p className="jp-hint" style={{ padding: '0.75rem 0' }}>Nothing to show for this filter.</p>}

          {groups.map(g => (
            <div key={g.name} className="ak-group">
              <div className="ak-group-title">{g.name}</div>
              {g.items.map(it => {
                const st = STATUS[it.status] || STATUS.missing;
                return (
                  <div key={it.id} className="ak-row">
                    <div className="ak-main">
                      <div className="ak-name">
                        {it.name}
                        <span className={`ak-cost ${it.cost}`} title={it.cost_note}>{COST[it.cost] || it.cost}</span>
                      </div>
                      <div className="ak-purpose">{it.purpose} · <span className="ak-used">{it.used_by}</span></div>
                      <div className="ak-keys">
                        {it.keys.map(k => (
                          <code key={k.name} className={k.set ? 'set' : ''} title={k.aliases?.length ? `Also accepted: ${k.aliases.join(', ')}` : ''}>
                            {k.set ? '✓ ' : ''}{k.name}
                          </code>
                        ))}
                      </div>
                      <div className="ak-note">{it.cost_note}</div>
                    </div>
                    <div className="ak-side">
                      <span className={`ak-status ${st.cls}`}><st.Icon size={13} /> {st.label}</span>
                      <a href={it.url} target="_blank" rel="noopener noreferrer" className="ak-link">Get key <ExternalLink size={12} /></a>
                    </div>
                  </div>
                );
              })}
            </div>
          ))}
        </>
      )}
    </div>
  );
}
