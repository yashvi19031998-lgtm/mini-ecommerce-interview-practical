'use client';

// Today: the landing page. Answers "what do I do now?" first, "how are we doing?" second.
// Left: one lane per to-do (Reply now, Follow-up due, Call or WhatsApp, Reply on post, No reply yet),
// each with its best leads and a verb button. Right: this month against last month + what the system
// is doing on its own. Backend: GET /api/today (lead_status.py + reports_engine.py).

import React, { useCallback, useEffect, useState } from 'react';
import { ArrowRight, Check, CheckCircle2, ExternalLink, Loader2, Mail, MessageCircle, Phone, RefreshCw, Target } from 'lucide-react';
import { fetchToday, markLeadContacted, saveSettings } from '../../lib/api';
import { ACTIONS, TODO_ACTIONS, whatsappUrl, niceDate } from '../../lib/leadMeta';

const fmt = (n) => (n == null ? '–' : Number(n).toLocaleString());

// Month tiles, in the order of the sales funnel
const MONTH = [
  { key: 'new_leads', label: 'Leads found' },
  { key: 'emails_sent', label: 'Mails sent' },
  { key: 'contacted', label: 'Contacted' },
  { key: 'replied', label: 'Replies' },
  { key: 'meetings', label: 'Meetings' },
  { key: 'won', label: 'Won' },
];

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
}

function Delta({ value, prev }) {
  if (prev == null || value == null) return null;
  const diff = value - prev;
  if (diff === 0) return <span className="td-delta flat">same as last month</span>;
  return <span className={`td-delta ${diff > 0 ? 'up' : 'down'}`}>{diff > 0 ? '+' : '−'}{fmt(Math.abs(diff))} vs last month</span>;
}

// The one button that does the lane's job for this lead
function PrimaryAction({ stage, item }) {
  if (stage === 'call_pending' && item.phone) {
    return (
      <>
        <a className="btn btn-primary sm" href={`tel:${item.phone.replace(/[^\d+]/g, '')}`}><Phone size={14} /> Call</a>
        {item.whatsapp && <a className="btn btn-wa sm" href={item.whatsapp} target="_blank" rel="noopener noreferrer"><MessageCircle size={14} /> WhatsApp</a>}
      </>
    );
  }
  if (stage === 'message_pending' && item.link) {
    return <a className="btn btn-primary sm" href={item.link} target="_blank" rel="noopener noreferrer"><ExternalLink size={14} /> {item.platform ? `Open on ${item.platform}` : 'Open post'}</a>;
  }
  if (item.email) {
    return <a className="btn btn-primary sm" href={`mailto:${item.email}`}><Mail size={14} /> Mail</a>;
  }
  if (item.phone) {
    const wa = item.whatsapp || whatsappUrl(item.phone);
    return wa ? <a className="btn btn-wa sm" href={wa} target="_blank" rel="noopener noreferrer"><MessageCircle size={14} /> WhatsApp</a> : null;
  }
  return null;
}

const DONE_FOR = { call_pending: 'called', message_pending: 'messaged', replied: 'mailed', followup_due: 'mailed', no_reply: 'mailed' };
const DONE_TEXT = { called: 'Done', messaged: 'Done', mailed: 'Done' };

export default function TodayPage({ userName = '', onOpenLead, onOpenLeads, onFindLeads, notify = () => {}, reloadKey = 0 }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [done, setDone] = useState({});
  const [loading, setLoading] = useState(false);
  const [editGoals, setEditGoals] = useState(null); // { key: '123' } while the goal form is open

  const load = useCallback(() => {
    setLoading(true);
    fetchToday(5)
      .then(res => { setData(res); setError(''); })
      .catch(err => setError(err.message || 'Could not load today'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load, reloadKey]);

  const markDone = async (stage, item) => {
    const action = DONE_FOR[stage] || 'mailed';
    setDone(d => ({ ...d, [item.id]: 'busy' }));
    try {
      await markLeadContacted(item.id, action);
      setDone(d => ({ ...d, [item.id]: 'done' }));
      notify(`${item.name}: logged. It moves to "Waiting for reply".`, 'success');
    } catch (err) {
      setDone(d => { const n = { ...d }; delete n[item.id]; return n; });
      notify(err.message, 'error');
    }
  };

  const saveGoals = async (e) => {
    e.preventDefault();
    const clean = Object.fromEntries(Object.entries(editGoals).map(([k, v]) => [k, Math.max(0, parseInt(v, 10) || 0)]).filter(([, v]) => v > 0));
    try {
      await saveSettings({ monthlyGoals: clean });
      setEditGoals(null);
      notify('Goals saved', 'success');
      load();
    } catch (err) {
      notify(err.message, 'error');
    }
  };

  const stageCount = (id) => data?.stages?.find(s => s.id === id)?.count ?? 0;
  const lanes = (data?.lanes || []).filter(l => TODO_ACTIONS.includes(l.id));
  const busyLanes = lanes.filter(l => l.count > 0);
  const clearLanes = lanes.filter(l => l.count === 0);
  const today = new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' });

  return (
    <div className="td">
      <header className="td-head">
        <div>
          <div className="td-date">{today}</div>
          <h1 className="td-title">
            {greeting()}{userName ? `, ${userName}` : ''}.{' '}
            {data ? (data.todo > 0
              ? <span><strong>{fmt(data.todo)}</strong> leads are waiting for you.</span>
              : <span>Nothing is waiting for you.</span>) : null}
          </h1>
        </div>
        <div className="td-head-actions">
          <button type="button" className="btn btn-ghost" onClick={load} disabled={loading} aria-label="Refresh">
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
          {onFindLeads && <button type="button" className="btn btn-primary" onClick={onFindLeads}>Find new leads</button>}
        </div>
      </header>

      {error && <div className="td-error">{error} <button type="button" className="btn btn-ghost sm" onClick={load}>Try again</button></div>}

      <div className="td-grid">
        {/* To-do lanes */}
        <div className="td-main">
          {!data && !error && <div className="td-loading"><Loader2 size={16} className="animate-spin" /> Loading your day…</div>}

          {clearLanes.length > 0 && (
            <div className="td-clear">
              {clearLanes.map(l => (
                <span key={l.id} className="td-clear-item"><CheckCircle2 size={14} /> {ACTIONS[l.id].label}: none</span>
              ))}
            </div>
          )}

          {busyLanes.map(lane => {
            const meta = ACTIONS[lane.id];
            return (
              <section key={lane.id} className={`td-lane tone-${meta.tone}`} aria-labelledby={`lane-${lane.id}`}>
                <div className="td-lane-head">
                  <h2 id={`lane-${lane.id}`} className="td-lane-title">
                    <span className="td-lane-count">{fmt(lane.count)}</span> {meta.label}
                  </h2>
                  <span className="td-lane-hint">{meta.hint}</span>
                  <button type="button" className="td-lane-all" onClick={() => onOpenLeads({ action: lane.id })}>
                    See all <ArrowRight size={14} />
                  </button>
                </div>
                <ul className="td-items">
                  {lane.items.map(item => {
                    const state = done[item.id];
                    return (
                      <li key={item.id} className={`td-item ${state === 'done' ? 'is-done' : ''}`}>
                        <button type="button" className="td-item-main" onClick={() => onOpenLead(item.id)} title="Open lead details">
                          <span className="td-item-top">
                            {item.score != null && <span className={`score s-${item.score >= 7 ? 'hot' : item.score >= 4 ? 'warm' : 'cold'}`}>{item.score}</span>}
                            <span className="td-item-name">{item.name}</span>
                          </span>
                          {item.about && <span className="td-item-about">{item.about}</span>}
                          <span className="td-item-meta">
                            {item.source}{item.found_at ? ` · found ${niceDate(item.found_at)}` : ''}
                            {item.last_contact ? ` · last contact ${niceDate(item.last_contact)}` : ''}
                            {item.due ? ` · due ${item.due}` : ''}
                          </span>
                        </button>
                        <div className="td-item-actions">
                          {state === 'done' ? (
                            <span className="td-done-tag"><Check size={14} /> Logged</span>
                          ) : (
                            <>
                              <PrimaryAction stage={lane.id} item={item} />
                              <button type="button" className="btn btn-soft sm" disabled={state === 'busy'} onClick={() => markDone(lane.id, item)}
                                title="Log that you did it; the lead moves to Waiting for reply">
                                {state === 'busy' ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />} {DONE_TEXT[DONE_FOR[lane.id] || 'mailed']}
                              </button>
                            </>
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ul>
                {lane.count > lane.items.length && (
                  <button type="button" className="td-more" onClick={() => onOpenLeads({ action: lane.id })}>
                    {fmt(lane.count - lane.items.length)} more in this list <ArrowRight size={14} />
                  </button>
                )}
              </section>
            );
          })}
        </div>

        {/* How we are doing */}
        <aside className="td-side">
          <section className="td-card">
            <div className="td-card-head">
              <h2 className="td-card-title">This month</h2>
              {!editGoals && (
                <button type="button" className="td-link" onClick={() => setEditGoals(Object.fromEntries(MONTH.map(m => [m.key, String(data?.goals?.[m.key] || '')])))}>
                  <Target size={13} /> {data?.goals && Object.keys(data.goals).length ? 'Edit goals' : 'Set goals'}
                </button>
              )}
            </div>
            {editGoals ? (
              <form className="td-goals-form" onSubmit={saveGoals}>
                <p className="td-goals-help">Target for each month. Leave empty for no target.</p>
                {MONTH.map(m => (
                  <label key={m.key} className="td-goal-input">
                    <span>{m.label}</span>
                    <input type="number" min="0" inputMode="numeric" value={editGoals[m.key]} placeholder="–"
                      onChange={e => setEditGoals(g => ({ ...g, [m.key]: e.target.value }))} />
                  </label>
                ))}
                <div className="td-goals-actions">
                  <button type="button" className="btn btn-ghost sm" onClick={() => setEditGoals(null)}>Cancel</button>
                  <button type="submit" className="btn btn-primary sm">Save goals</button>
                </div>
              </form>
            ) : (
              <dl className="td-month">
                {MONTH.map(m => {
                  const v = data?.month?.[m.key];
                  const goal = data?.goals?.[m.key];
                  const pct = goal ? Math.min(100, Math.round(((v?.value || 0) / goal) * 100)) : null;
                  return (
                    <div key={m.key} className="td-month-row">
                      <dt>{m.label}</dt>
                      <dd>
                        <span className="td-month-val">{fmt(v?.value)}{goal ? <small> / {fmt(goal)}</small> : null}</span>
                        {goal ? <span className={`td-delta ${pct >= 100 ? 'up' : 'flat'}`}>{pct}% of goal</span> : <Delta value={v?.value} prev={v?.prev} />}
                      </dd>
                      {goal ? <div className="td-goal-bar" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={`${m.label}: ${pct}% of goal`}><span style={{ width: `${pct}%` }} className={pct >= 100 ? 'met' : ''} /></div> : null}
                    </div>
                  );
                })}
              </dl>
            )}
          </section>

          <section className="td-card">
            <h2 className="td-card-title">Running on its own</h2>
            <button type="button" className="td-auto" onClick={() => onOpenLeads({ action: 'mail_pending' })}>
              <span className="td-auto-val">{fmt(stageCount('mail_pending'))}</span>
              <span><strong>In the mail queue.</strong> Auto-mail sends them Mon–Sat, 10:00–19:00.</span>
            </button>
            <button type="button" className="td-auto" onClick={() => onOpenLeads({ action: 'waiting' })}>
              <span className="td-auto-val">{fmt(stageCount('waiting'))}</span>
              <span><strong>Waiting for a reply.</strong> They move to “No reply yet” after 4 days.</span>
            </button>
          </section>

          <section className="td-card quiet">
            <h2 className="td-card-title">Skipped</h2>
            <p className="td-skipped">
              {fmt(stageCount('not_fit'))} not a fit · {fmt(stageCount('no_contact'))} without contact details · {fmt(stageCount('old_post'))} on old posts · {fmt(stageCount('closed'))} closed
            </p>
            <button type="button" className="td-lane-all" onClick={() => onOpenLeads({ action: 'no_contact' })}>Review them <ArrowRight size={14} /></button>
          </section>
        </aside>
      </div>
    </div>
  );
}
