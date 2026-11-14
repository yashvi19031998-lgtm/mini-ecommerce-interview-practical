'use client';

import React from 'react';
import { Clock, CheckCircle2, ArrowRight } from 'lucide-react';

export const MINING_PLANS = {
  'mining-maps': {
    title: 'Google Maps',
    what: 'Local businesses by category and city: phone, website, address, rating.',
    how: ['OpenStreetMap directory', 'Google Places API integration', 'Search engine business listings', 'Direct contact enrichment']
  },
  'mining-social': {
    title: 'Social Media',
    what: 'Verified business pages across Instagram, Facebook, LinkedIn and X.',
    how: ['Targeted company profile search', 'Public business profile discovery', 'Website & contact extraction']
  },
  'mining-adlibrary': {
    title: 'Ad Library',
    what: 'Identify active commercial advertisers with active marketing campaigns.',
    how: ['Meta Ad Library indexing', 'Google Ads Transparency queries', 'Advertiser domain enrichment']
  },
  'mining-ecommerce': {
    title: 'Ecommerce Platforms',
    what: 'Online direct-to-consumer stores and marketplace sellers.',
    how: ['Shopify store indexing', 'WooCommerce store discovery', 'Brand contact enrichment']
  },
  'mining-directories': {
    title: 'Global Directories',
    what: 'International companies from official open registers and trade directories.',
    how: ['OpenStreetMap worldwide', 'UK Companies House registry', 'US SEC EDGAR corporate filings']
  },
  'mining-whatsapp': {
    title: 'WhatsApp Groups',
    what: 'Public WhatsApp group invite links for relevant industry communities.',
    how: ['Public directory indexing', 'Community invite verification']
  },
  'mining-realestate': {
    title: 'Real Estate',
    what: 'Registered builders, property developers, and real estate agencies.',
    how: ['State RERA official registers', 'Property portal business listings', 'Developer contact discovery']
  }
};

export default function MiningComingSoon({ id, onOpenSearchEngine }) {
  const plan = MINING_PLANS[id];
  if (!plan) return null;
  return (
    <div className="theme-card-panel">
      <div className="theme-panel-header" style={{ marginBottom: '0.75rem' }}>
        <div>
          <div className="theme-panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {plan.title} <span className="se-badge soon"><Clock size={12} /> In Roadmap</span>
          </div>
          <div className="theme-panel-sub">{plan.what}</div>
        </div>
      </div>
      <div style={{ marginTop: '0.75rem' }}>
        <div className="mcs-head" style={{ marginBottom: '0.5rem', fontWeight: 600, fontSize: '0.85rem' }}>Planned Capabilities</div>
        <ul className="mcs-list">{plan.how.map(h => <li key={h}><CheckCircle2 size={14} /> {h}</li>)}</ul>
      </div>
      {onOpenSearchEngine && (
        <button type="button" className="theme-pill-btn neutral" style={{ marginTop: '1rem' }} onClick={onOpenSearchEngine}>
          Explore Search Engines <ArrowRight size={13} />
        </button>
      )}
    </div>
  );
}
