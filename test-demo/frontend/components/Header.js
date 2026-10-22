'use client';

import React from 'react';
import { 
  Database, Terminal, DownloadCloud, Settings, RefreshCw, 
  Send, Play, Download, Sparkles, LogOut, User, Menu, ChevronRight 
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
  onToggleMobileMenu = null
}) {
  const tabsMeta = {
    leads: {
      category: 'Pipeline',
      title: 'Leads Database & Outreach CRM',
      subtitle: 'Authoritative multi-channel leads database with atomic deduplication & cold outreach',
      icon: Database,
      iconColor: 'var(--primary-lavender)'
    },
    scraper: {
      category: 'Harvester',
      title: 'Live Scraper Console & Multi-Harvester',
      subtitle: 'Coordinate parallel background scrapers across 12 public tech hiring sources',
      icon: Terminal,
      iconColor: 'var(--success)'
    },
    import: {
      category: 'Growth',
      title: 'Lead Importer & Extraction Engine',
      subtitle: 'Keyword discovery scans, exported WhatsApp group chat parser, and raw text crawler',
      icon: DownloadCloud,
      iconColor: 'var(--primary-lavender)'
    },
    settings: {
      category: 'Preferences',
      title: 'Company Profile & Gmail SMTP Configuration',
      subtitle: 'Manage company branding, Gmail SMTP credentials, and outgoing signatures',
      icon: Settings,
      iconColor: 'var(--pink-accent)'
    }
  };

  const meta = tabsMeta[activeTab] || tabsMeta.leads;
  const TabIcon = meta.icon;

  return (
    <header className="main-header-bar">
      <div className="header-left-col">
        {/* Mobile Menu Hamburger Toggle */}
        {onToggleMobileMenu && (
          <button
            onClick={onToggleMobileMenu}
            className="mobile-menu-btn"
            title="Open navigation menu"
            aria-label="Toggle navigation drawer"
          >
            <Menu size={18} />
          </button>
        )}

        <div className="header-icon-badge" style={{ color: meta.iconColor }}>
          <TabIcon size={20} />
        </div>
        <div>
          {/* Breadcrumbs Navigation */}
          <div className="header-breadcrumbs">
            <span
              className="header-breadcrumb-root"
              onClick={() => setActiveTab && setActiveTab('leads')}
            >
              Workspace
            </span>
            <ChevronRight size={11} className="header-breadcrumb-sep" />
            <span>{meta.category}</span>
            <ChevronRight size={11} className="header-breadcrumb-sep" />
            <span className="header-breadcrumb-current">{meta.title.split('&')[0].trim()}</span>
          </div>

          <h1 className="header-title">{meta.title}</h1>
          <p className="header-subtitle">{meta.subtitle}</p>
        </div>
      </div>

      <div className="header-right-actions">
        {/* Backend Connectivity Status Pill */}
        <div className={`status-pill ${backendOnline ? 'status-pill-online' : 'status-pill-standby'}`}>
          <span className={`pulse-dot ${backendOnline ? 'pulse-emerald' : 'pulse-amber'}`}></span>
          <span>{backendOnline ? 'Python DB Live (5000)' : 'Python Standby'}</span>
        </div>

        {/* Global Refresh Button */}
        <button
          onClick={onRefreshLeads}
          disabled={isRefreshing}
          className="btn-header btn-header-secondary"
          title="Reload leads from database"
        >
          <RefreshCw size={13} className={isRefreshing ? 'animate-spin' : ''} />
          Reload
        </button>

        {/* Quick Launch Scraper */}
        <button
          onClick={onTriggerQuickScraper}
          disabled={isScraperRunning}
          className="btn-header btn-header-primary"
        >
          <Play size={13} />
          {isScraperRunning ? 'Scraper Busy...' : 'Run Scraper'}
        </button>

        {/* Sync Supabase */}
        <button
          onClick={onSyncSupabase}
          className="btn-header btn-header-secondary"
          title="Sync with Supabase Cloud Database"
        >
          <Send size={13} />
          Supabase
        </button>

        {/* User Sign Out */}
        {user && onSignOut && (
          <button
            onClick={onSignOut}
            className="btn-header btn-header-danger"
            title="Sign out of account"
          >
            <LogOut size={13} />
            Sign Out
          </button>
        )}
      </div>
    </header>
  );
}
