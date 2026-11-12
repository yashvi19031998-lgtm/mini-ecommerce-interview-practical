'use client';

// Placeholder for Scraping / Mining modules that are planned but not built yet.
// Each card says what the module will do and which free / legal method it will use.

import React from 'react';
import { Clock, CheckCircle2, AlertTriangle, ArrowRight } from 'lucide-react';

export const MINING_PLANS = {
  'mining-maps': {
    title: 'Google Maps',
    what: 'Local businesses by category and city: name, phone, website, address, rating.',
    how: ['OpenStreetMap (free, no key)', 'Google Places API (free monthly quota, card needed - key slot in Settings)', 'Maps listings found through the search engine', 'Deep Search for email'],
    not: 'Scraping google.com/maps directly is against Google\'s terms and gets blocked quickly.',
  },
  'mining-social': {
    title: 'Social Media',
    what: 'Business pages on Instagram, Facebook, LinkedIn and X for a keyword + city, with the website from their bio.',
    how: ['Search engine site: queries (Brave / Serper key recommended)', 'Deep Search on the website found in the profile'],
    not: 'No logging in to social networks and no scraping of private profiles or follower lists.',
  },
  'mining-adlibrary': {
    title: 'Ad Library',
    what: 'Companies that are running ads right now (they have budget = hot leads).',
    how: ['Meta Ad Library (advertiser page names and links)', 'Deep Search on the advertiser\'s website'],
    not: 'In India the official Meta Ad Library API only covers political / social-issue ads; commercial ads need the public website view.',
  },
  'mining-ecommerce': {
    title: 'Ecommerce Platforms',
    what: 'Online stores and marketplace sellers for a product category.',
    how: ['Shopify stores (myshopify.com) via the search engine', 'Seller names shown on Amazon / Flipkart product pages (sellers must be shown by law)', 'Deep Search on the store website'],
    not: 'Amazon and Flipkart block automated access; we will not bypass that.',
  },
  'mining-directories': {
    title: 'Global Directories',
    what: 'Companies outside India from official open registers and directories.',
    how: ['OpenStreetMap (worldwide)', 'UK Companies House API (free key)', 'US SEC EDGAR (free)', 'GoodFirms worldwide'],
    not: 'Paid-only databases (OpenCorporates API, D&B) are not included.',
  },
  'mining-whatsapp': {
    title: 'WhatsApp Groups',
    what: 'Public WhatsApp group invite links for a topic (group name + link).',
    how: ['Search engine site:chat.whatsapp.com queries'],
    not: 'Member phone numbers cannot be collected: that needs joining groups with automation (WhatsApp bans the number) and India\'s DPDP Act 2023 protects personal numbers.',
  },
  'mining-realestate': {
    title: 'Real Estate',
    what: 'Builders, developers and agents by city with phone / email.',
    how: ['State RERA portals - registered promoters and agents (public government data)', '99acres / MagicBricks listings via the search engine', 'Deep Search on builder websites'],
    not: 'Phone numbers hidden behind a login on property portals are not collected.',
  },
};

export default function MiningComingSoon({ id, onOpenSearchEngine }) {
  const plan = MINING_PLANS[id];
  if (!plan) return null;
  return (
    <div className="theme-card-panel">
      <div className="theme-panel-header" style={{ marginBottom: '0.75rem' }}>
        <div>
          <div className="theme-panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {plan.title} <span className="se-badge soon"><Clock size={12} /> Coming soon</span>
          </div>
          <div className="theme-panel-sub">{plan.what}</div>
        </div>
      </div>
      <div className="mcs-grid">
        <div>
          <div className="mcs-head">How it will work (free / official)</div>
          <ul className="mcs-list">{plan.how.map(h => <li key={h}><CheckCircle2 size={14} /> {h}</li>)}</ul>
        </div>
        <div>
          <div className="mcs-head">What it will not do</div>
          <p className="mcs-not"><AlertTriangle size={14} /> {plan.not}</p>
        </div>
      </div>
      {onOpenSearchEngine && (
        <button type="button" className="theme-pill-btn neutral" style={{ marginTop: '1rem' }} onClick={onOpenSearchEngine}>
          Use Search Engines meanwhile <ArrowRight size={13} />
        </button>
      )}
    </div>
  );
}
