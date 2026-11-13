'use client';

// One search form for every Scraping / Mining page (and CRM Sources), so all modules look and behave alike.
// Each page turns on only the sections its sources can really use:
//
//   keywords   (required)  what to search for                       -> ChipInput
//   audience   (optional)  Target audience: industries / segments  -> ChipInput with suggestions
//   titles     (optional)  decision-maker titles (contact databases only)
//   extra      (optional)  module-specific fields (ReactNode), shown after the common fields
//   location   state + city (India) or country + city
//   sources    multi-select of sources / portals with status groups, or null
//   maxResults select, or null
//
// Controlled component: the page owns all values and errors. On submit, text typed in a chip box but not yet
// turned into a chip is included (so "type + click Search" works), and onSubmit(event, {keywords, audience, titles})
// receives the final lists.

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Search, Loader2, ChevronDown } from 'lucide-react';
import ChipInput from './ChipInput';

export const AUDIENCE_SUGGESTIONS = [
  'IT / Software', 'Manufacturing', 'Real Estate', 'Construction', 'Healthcare', 'Education', 'Retail',
  'Ecommerce', 'Hospitality', 'Finance', 'Logistics', 'Automobile', 'Textile', 'Agriculture', 'Pharma',
  'Startups', 'SMEs', 'Exporters'
];

export function splitPending(text) {
  return String(text || '').split(',').map(t => t.trim()).filter(Boolean);
}

function mergePending(values, id, max) {
  const el = typeof document !== 'undefined' ? document.getElementById(id) : null;
  const pending = splitPending(el?.value);
  const out = [...values];
  for (const p of pending) {
    if (p.length <= 80 && !out.some(v => v.toLowerCase() === p.toLowerCase()) && out.length < max) out.push(p);
  }
  return out;
}

function SourcesSelect({ id, label, items, selected, setSelected, error, groups, placeholder, allLabel, onClear }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);
  const available = useMemo(() => items.filter(s => s.status === 'available'), [items]);
  const allSelected = available.length > 0 && available.every(s => selected.has(s.id));
  const update = (next) => { setSelected(next); if (next.size && onClear) onClear(); };
  const toggle = (sid) => { const n = new Set(selected); if (n.has(sid)) n.delete(sid); else n.add(sid); update(n); };
  const text = !selected.size ? placeholder
    : allSelected && available.length > 1 ? `${allLabel} (${selected.size})`
      : items.filter(s => selected.has(s.id)).map(s => s.name).join(', ');
  return (
    <div className="form-group jp-span-2" ref={ref} style={{ position: 'relative' }}>
      <label className="form-label" id={`${id}-label`}>{label}</label>
      <button type="button" className={`theme-form-input jp-multiselect ${error ? 'has-error' : ''}`}
        onClick={() => setOpen(!open)} aria-haspopup="listbox" aria-expanded={open} aria-labelledby={`${id}-label`}>
        <span className="jp-multiselect-text">{text}</span><ChevronDown size={14} />
      </button>
      {error && <div className="jp-field-error">{error}</div>}
      {open && (
        <div className="jp-menu" role="listbox" aria-multiselectable="true">
          <label className="jp-menu-item jp-menu-all">
            <input type="checkbox" checked={allSelected}
              onChange={() => update(allSelected ? new Set() : new Set(available.map(s => s.id)))} />
            <span>Select all available ({available.length})</span>
          </label>
          {groups.map(g => {
            const list = items.filter(s => s.status === g.status && (!g.kind || s.kind === g.kind));
            if (!list.length) return null;
            return (
              <div key={g.label}>
                <div className="jp-menu-group">{g.label}</div>
                {list.map(s => {
                  const disabled = s.status !== 'available';
                  const sub = disabled ? s.reason : (s.note || s.region || '');
                  return (
                    <label key={s.id} className={`jp-menu-item ${disabled ? 'disabled' : ''}`} title={sub}>
                      <input type="checkbox" disabled={disabled} checked={selected.has(s.id)} onChange={() => toggle(s.id)} />
                      <span className="jp-menu-text"><span>{s.name}</span>{sub && <span className="jp-menu-sub">{sub}</span>}</span>
                    </label>
                  );
                })}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function MiningForm({
  idPrefix, onSubmit, busy = false, disabled = false, submitLabel = 'Search', busyLabel = 'Searching…', busyHint = '',
  keywords, audience = null, titles = null, extra = null, location = null, sources = null, maxResults = null
}) {
  const kwId = keywords.id || `${idPrefix}-keywords`;
  const audId = `${idPrefix}-audience`;
  const titleId = titles?.id || `${idPrefix}-titles`;

  useEffect(() => {
    let active = true;
    if ((!keywords.values || keywords.values.length === 0) && typeof window !== 'undefined') {
      import('../lib/api').then(({ fetchSettings }) => {
        fetchSettings().then(res => {
          if (!active) return;
          if (res?.success && res.settings) {
            const s = res.settings;
            if (keywords.values.length === 0 && Array.isArray(s.defaultKeywords) && s.defaultKeywords.length > 0) {
              keywords.setValues(s.defaultKeywords.slice(0, keywords.max || 5));
            }
            if (location) {
              if (location.city !== undefined && !location.city && s.defaultCity && location.setCity) {
                location.setCity(s.defaultCity);
              }
              if (location.state !== undefined && !location.state && s.defaultState && location.setState) {
                location.setState(s.defaultState);
              }
            }
          }
        }).catch(() => {});
      }).catch(() => {});
    }
    return () => { active = false; };
  }, []);

  const submit = (e) => {
    e.preventDefault();
    const final = { keywords: mergePending(keywords.values, kwId, keywords.max) };
    if (final.keywords.length !== keywords.values.length) keywords.setValues(final.keywords);
    if (audience) {
      final.audience = mergePending(audience.values, audId, audience.max || 5);
      if (final.audience.length !== audience.values.length) audience.setValues(final.audience);
    }
    if (titles) {
      final.titles = mergePending(titles.values, titleId, titles.max);
      if (final.titles.length !== titles.values.length) titles.setValues(final.titles);
    }
    onSubmit(e, final);
  };

  return (
    <form onSubmit={submit} noValidate>
      <div className="jp-form-grid">
        <div className="jp-span-2">
          <ChipInput id={kwId} label={keywords.label} hint={keywords.hint} values={keywords.values}
            setValues={(v) => { keywords.setValues(v); if (v.length && keywords.onClear) keywords.onClear(); }}
            max={keywords.max} placeholder={keywords.placeholder} error={keywords.error} onChangeClear={keywords.onClear}
            suggestions={keywords.suggestions} />
        </div>

        {audience && (
          <div className="jp-span-2">
            <ChipInput id={audId} label="Target audience" hint={audience.hint || '(optional — industries or segments, up to 5)'}
              values={audience.values} setValues={audience.setValues} max={audience.max || 5}
              placeholder={audience.placeholder || 'e.g. Manufacturing, Real Estate, Startups'}
              error={audience.error} suggestions={AUDIENCE_SUGGESTIONS} />
          </div>
        )}

        {titles && (
          <div className="jp-span-2">
            <ChipInput id={titleId} label={titles.label || 'Decision-maker titles'} hint={titles.hint}
              values={titles.values} setValues={titles.setValues} max={titles.max} placeholder={titles.placeholder || 'e.g. CEO, Founder, CTO'} />
          </div>
        )}

        {extra}

        {location && (
          <>
            {location.mode === 'country' ? (
              <div className="form-group">
                <label className="form-label" htmlFor={`${idPrefix}-country`}>Country</label>
                <select id={`${idPrefix}-country`} className="theme-form-input" value={location.country}
                  onChange={(e) => { location.setCountry(e.target.value); if (e.target.value && location.onClear) location.onClear('country'); }}
                  aria-invalid={!!location.countryError}>
                  <option value="">Select country…</option>
                  {(location.countries || []).map(c => <option key={c.id || c} value={c.id || c}>{c.name || c}</option>)}
                </select>
                {location.countryError && <div className="jp-field-error">{location.countryError}</div>}
              </div>
            ) : (
              <div className="form-group">
                <label className="form-label" htmlFor={`${idPrefix}-state`}>State</label>
                <select id={`${idPrefix}-state`} className="theme-form-input" value={location.state}
                  onChange={(e) => { location.setState(e.target.value); if (e.target.value && location.onClear) location.onClear('state'); }}
                  aria-invalid={!!location.stateError}>
                  {location.stateRequired && <option value="">Select state…</option>}
                  {(location.states || []).map(s => <option key={s} value={s}>{s}</option>)}
                </select>
                {location.stateError && <div className="jp-field-error">{location.stateError}</div>}
              </div>
            )}
            {location.showCity !== false && (
              <div className="form-group">
                <label className="form-label" htmlFor={`${idPrefix}-city`}>City <span className="jp-hint">{location.cityHint || '(optional)'}</span></label>
                <input id={`${idPrefix}-city`} className="theme-form-input" value={location.city} maxLength={60}
                  placeholder={location.cityPlaceholder || 'e.g. Ahmedabad'}
                  onChange={(e) => { location.setCity(e.target.value); if (location.onClear) location.onClear('city'); }}
                  aria-invalid={!!location.cityError} />
                {location.cityError && <div className="jp-field-error">{location.cityError}</div>}
              </div>
            )}
          </>
        )}

        {sources && <SourcesSelect id={`${idPrefix}-src`} {...sources} />}

        {maxResults && (
          <div className="form-group">
            <label className="form-label" htmlFor={`${idPrefix}-max`}>Max results</label>
            <select id={`${idPrefix}-max`} className="theme-form-input" value={maxResults.value}
              onChange={(e) => maxResults.setValue(Number(e.target.value))}>
              {maxResults.choices.map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <button type="submit" className="theme-pill-btn primary" disabled={busy || disabled}>
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />} {busy ? busyLabel : submitLabel}
        </button>
        {busy && busyHint && <span className="jp-hint">{busyHint}</span>}
      </div>
    </form>
  );
}
