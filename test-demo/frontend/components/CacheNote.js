'use client';

import React from 'react';
import { History, RefreshCw } from 'lucide-react';

function timeAgo(epochSeconds) {
  const mins = Math.max(0, Math.round((Date.now() / 1000 - epochSeconds) / 60));
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} days ago`;
}

// Shown when a search was answered from saved results (search_cache.py) instead of the live sites.
export default function CacheNote({ cache, onRefresh, busy }) {
  if (!cache?.hit) return null;
  return (
    <div className="cache-note" role="note">
      <History size={14} />
      <span>Showing saved results from <strong>{timeAgo(cache.saved_at)}</strong> — no new requests were sent to the sites.</span>
      <button type="button" className="theme-pill-btn neutral" onClick={onRefresh} disabled={busy}>
        <RefreshCw size={13} className={busy ? 'animate-spin' : ''} /> Search live again
      </button>
    </div>
  );
}
