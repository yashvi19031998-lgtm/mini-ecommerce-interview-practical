'use client';

// Scraping / Mining -> Global Directories.
// STUB - wired into app/page.js (activeTab 'mining-directories'). Replace the body with the real page.
// API helpers already exist in ../lib/api.js: fetchGlobalDirectories, searchGlobalDirectories,
// saveGlobalDirectoryResults, runDeepSearch. Use MiningForm (location.mode = 'country').

import React from 'react';
import MiningComingSoon from './MiningComingSoon';

export default function GlobalDirectories({ onLeadsSaved, onOpenSearchEngine }) {
  return <MiningComingSoon id="mining-directories" onOpenSearchEngine={onOpenSearchEngine} />;
}
