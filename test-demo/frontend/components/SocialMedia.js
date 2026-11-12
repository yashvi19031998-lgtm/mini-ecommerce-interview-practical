'use client';

// Scraping / Mining -> Social Media.
// STUB - wired into app/page.js (activeTab 'mining-social'). Replace the body with the real page.
// API helpers already exist in ../lib/api.js: fetchSocialSources, searchSocial, saveSocialResults, runDeepSearch.
// Use MiningForm (location.mode = 'india').

import React from 'react';
import MiningComingSoon from './MiningComingSoon';

export default function SocialMedia({ onLeadsSaved, onOpenSearchEngine }) {
  return <MiningComingSoon id="mining-social" onOpenSearchEngine={onOpenSearchEngine} />;
}
