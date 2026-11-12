'use client';

// Chip / tag input: type a value and press Enter or comma. Used by CRM Sources and Search Engines.
import React, { useState } from 'react';
import { X } from 'lucide-react';

const MAX_LEN = 80;

export default function ChipInput({ id, label, hint, values, setValues, max, placeholder, error, onChangeClear, suggestions = null }) {
  const [text, setText] = useState('');
  const [localError, setLocalError] = useState('');
  const add = (raw) => {
    const parts = String(raw).split(',').map(t => t.trim()).filter(Boolean);
    const next = [...values];
    let err = '';
    for (const t of parts) {
      if (t.length > MAX_LEN) { err = `"${t.slice(0, 20)}…" is longer than ${MAX_LEN} characters`; continue; }
      if (next.some(x => x.toLowerCase() === t.toLowerCase())) continue;
      if (next.length >= max) { err = `You can add at most ${max}`; break; }
      next.push(t);
    }
    setValues(next);
    setText('');
    setLocalError(err);
  };
  return (
    <div className="form-group">
      <label className="form-label" htmlFor={id}>{label} <span className="jp-hint">{hint}</span></label>
      <div className={`jp-chip-input ${error || localError ? 'has-error' : ''}`}>
        {values.map(v => (
          <span key={v} className="jp-chip">{v}
            <button type="button" aria-label={`Remove ${v}`} onClick={() => setValues(values.filter(x => x !== v))}><X size={12} /></button>
          </span>
        ))}
        <input id={id} type="text" value={text} placeholder={values.length ? 'Add another…' : placeholder} list={suggestions ? `${id}-list` : undefined}
          onChange={(e) => { setText(e.target.value); if (e.target.value.trim() && onChangeClear) onChangeClear(); }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add(text); }
            else if (e.key === 'Backspace' && !text && values.length) setValues(values.slice(0, -1));
          }}
          onBlur={() => text.trim() && add(text)} />
      </div>
      {(error || localError) && <div className="jp-field-error">{error || localError}</div>}
      {suggestions && <datalist id={`${id}-list`}>{suggestions.filter(x => !values.includes(x)).map(x => <option key={x} value={x} />)}</datalist>}
    </div>
  );
}
