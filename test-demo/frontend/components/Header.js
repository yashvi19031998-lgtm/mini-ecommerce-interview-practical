'use client';

import React from 'react';
import { 
  Search, RefreshCw, Play, Send, Moon, Sun, Bell, 
  Menu, LogOut, ChevronRight, CheckCircle2, AlertCircle
} from 'lucide-react';

export default function Header({
  activeTab,
  setActiveTab,
  isScraperRunning,
  backendOnline,
  onRefreshLeads,
  isRefreshing,
  onTriggerQuickScraper,
  onSyncSupabase,
  user = null,
  onSignOut = null,
  onToggleCollapse = null,
  searchQuery = '',
  onSearchChange = null
}) {
  const tabTitles = {
    leads: { root: 'Workspace', leaf: 'Leads Database' },
    scraper: { root: 'Workspace', leaf: 'Live Scrapers' },
    import: { root: 'Growth', leaf: 'Import & Parse' },
    settings: { root: 'Configuration', leaf: 'Settings & SMTP' }
  };

  const crumb = tabTitles[activeTab] || tabTitles.leads;

  return (
    <header className="theme-header">
      {/* Left section: Collapse Toggle & Breadcrumbs */}
      <div className="theme-header-left">
        <button 
          onClick={onToggleCollapse} 
          className="theme-collapse-toggle" 
          title="Toggle Sidebar"
          aria-label="Toggle Sidebar"
        >
          <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6">
            <path d="M3.5 5.5h13M3.5 10h13M3.5 14.5h9" />
          </svg>
        </button>

        <div className="theme-header-star" title="Workspace Bookmarks">
          <svg width="17" height="17" viewBox="0 0 20 20" fill="none" stroke="#8a8f98" strokeWidth="1.5">
            <path d="M10 3.5l2.1 4.3 4.7.6-3.4 3.3.8 4.7L10 14.2l-4.2 2.2.8-4.7L3.2 8.4l4.7-.6z" />
          </svg>
        </div>

        <span className="theme-crumb-sep">/</span>
        <span className="theme-crumb-root">{crumb.root}</span>
        <span className="theme-crumb-sep">/</span>
        <span className="theme-crumb-leaf">{crumb.leaf}</span>
      </div>

      {/* Center Search Pill matching Theme (max-width 340px, rounded-full) */}
      <div className="theme-header-center">
        <div className="theme-search-pill">
          <svg width="15" height="15" viewBox="0 0 20 20" fill="none" stroke="#a3a7ae" strokeWidth="1.7">
            <circle cx="9" cy="9" r="5.2" />
            <path d="M13 13l3.2 3.2" />
          </svg>
          <input 
            type="text" 
            placeholder="Search leads, companies, emails..." 
            value={searchQuery}
            onChange={(e) => onSearchChange && onSearchChange(e.target.value)}
          />
        </div>
      </div>

      {/* Right Action Icons & Status */}
      <div className="theme-header-right">
        {/* Backend Online status pill */}
        <div className={`theme-header-pill ${backendOnline ? 'online' : 'standby'}`}>
          <span className={`theme-header-dot ${backendOnline ? 'green' : 'amber'}`}></span>
          <span>{backendOnline ? 'DB Connected' : 'DB Standby'}</span>
        </div>

        <button 
          onClick={onRefreshLeads} 
          disabled={isRefreshing}
          className="theme-header-icon-btn" 
          title="Refresh Leads Database"
          aria-label="Refresh Database"
        >
          <RefreshCw size={17} className={isRefreshing ? 'animate-spin' : ''} />
        </button>

        <button 
          onClick={onTriggerQuickScraper} 
          disabled={isScraperRunning}
          className={`theme-header-icon-btn ${isScraperRunning ? 'running' : ''}`}
          title={isScraperRunning ? 'Scraper is running' : 'Start Quick Scraper'}
          aria-label="Quick Scraper"
        >
          <Play size={17} fill={isScraperRunning ? '#1f9254' : 'none'} color={isScraperRunning ? '#1f9254' : 'currentColor'} />
        </button>

        <div className="theme-header-notification-wrap" title="System alerts">
          <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
            <rect x="3" y="4" width="14" height="12" rx="2.4" />
            <path d="M12.6 4v12" />
          </svg>
          {isScraperRunning && <span className="theme-notif-badge"></span>}
        </div>
      </div>
    </header>
  );
}
