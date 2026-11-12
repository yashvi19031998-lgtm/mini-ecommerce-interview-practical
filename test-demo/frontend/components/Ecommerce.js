'use client';

// Scraping / Mining -> Ecommerce Platforms.
// STUB - wired into app/page.js (activeTab 'mining-ecommerce'). Replace the body with the real page.
// API helpers already exist in ../lib/api.js: fetchEcommerceSources, searchEcommerce, saveEcommerceResults,
// runDeepSearch. Use MiningForm (location.mode = 'india').

import React from 'react';
import MiningComingSoon from './MiningComingSoon';

export default function Ecommerce({ onLeadsSaved, onOpenSearchEngine }) {
  return <MiningComingSoon id="mining-ecommerce" onOpenSearchEngine={onOpenSearchEngine} />;
}
