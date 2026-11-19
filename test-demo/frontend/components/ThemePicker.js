'use client';

// Settings > Appearance: pick the colour theme. Click a card to switch at once (live preview); the choice is
// kept in this browser and saved in the settings, so every browser that signs in opens with it.
// The themes themselves are in app/themes.css (<html data-palette="...">).

import React from 'react';
import { Check } from 'lucide-react';

export const PALETTES = [
  { id: 'premium', name: 'Premium', desc: 'Obsidian, ink and gold - premium (default)', side: '#0c0c11', accent: '#c9a24d', bg: '#f6f6f4' },
  { id: 'classic', name: 'Classic', desc: 'White with blue - the original look', side: '#ffffff', sideLine: '#e5e7eb', accent: '#1a6dff', bg: '#ffffff' },
  { id: 'midnight', name: 'Midnight', desc: 'Navy sidebar, indigo - calm, corporate', side: '#0f172a', accent: '#4f46e5', bg: '#f5f6fb' },
  { id: 'emerald', name: 'Emerald', desc: 'Deep green, green accent - growth', side: '#0b2e24', accent: '#047857', bg: '#f4f8f6' },
  { id: 'royal', name: 'Royal', desc: 'Dark plum, violet - modern SaaS', side: '#1c1533', accent: '#6d28d9', bg: '#f7f6fc' },
  { id: 'ember', name: 'Ember', desc: 'Charcoal, burnt orange - warm, bold', side: '#1c1917', accent: '#c2410c', bg: '#faf8f5' },
  { id: 'ocean', name: 'Ocean', desc: 'Dark teal, teal accent - fresh, clean', side: '#0b2a2e', accent: '#0f766e', bg: '#f4f8f8' },
];
const IDS = PALETTES.map(p => p.id);
const STORE = 'ui-palette';

export const DEFAULT_PALETTE = 'premium';

export function applyPalette(id) {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  const pick = IDS.includes(id) ? id : DEFAULT_PALETTE;
  if (pick === 'classic') root.removeAttribute('data-palette');
  else root.setAttribute('data-palette', pick);
}

export function savedPalette() {
  try { return localStorage.getItem(STORE) || ''; } catch { return ''; }
}

export function rememberPalette(id) {
  try { localStorage.setItem(STORE, id); } catch { /* private mode */ }
  applyPalette(id);
}

export default function ThemePicker({ value = DEFAULT_PALETTE, onChange }) {
  return (
    <section className="tp" aria-labelledby="tp-title">
      <div className="tp-head">
        <h2 className="tp-title" id="tp-title">Appearance</h2>
      </div>
      <p className="tp-sub">Pick a colour theme. It changes at once; it is saved for every browser you sign in from.</p>
      <div className="tp-grid" role="radiogroup" aria-label="Colour theme">
        {PALETTES.map(p => (
          <button key={p.id} type="button" role="radio" aria-checked={value === p.id}
            className={`tp-card ${value === p.id ? 'on' : ''}`} onClick={() => onChange(p.id)}>
            <span className="tp-mini" aria-hidden="true">
              <span className="tp-mini-side" style={{ background: p.side, borderRight: p.sideLine ? `1px solid ${p.sideLine}` : 'none' }}>
                <i style={{ background: p.id === 'classic' ? '#dbe6ff' : `${p.accent}66` }} />
                <i style={p.id === 'classic' ? { background: '#e5e7eb' } : undefined} />
                <i style={p.id === 'classic' ? { background: '#e5e7eb' } : undefined} />
              </span>
              <span className="tp-mini-main" style={{ background: p.bg }}>
                <i style={{ width: '70%' }} />
                <i style={{ width: '50%' }} />
                <b style={{ background: p.accent }} />
              </span>
            </span>
            <span className="tp-name">{p.name}{value === p.id && <Check size={14} />}</span>
            <span className="tp-desc">{p.desc}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
