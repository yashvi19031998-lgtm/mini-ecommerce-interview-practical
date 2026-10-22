'use client';

import React from 'react';
import { Database, Terminal, DownloadCloud, Settings, RefreshCw, Send, Play } from 'lucide-react';

export default function Navbar({
  activeTab,
  setActiveTab,
  isScraperRunning,
  backendOnline,
  onTriggerQuickScraper,
  onSyncSupabase,
  onRefreshLeads,
  isRefreshing
}) {
  return (
    <header className="app-header">
      <div className="header-inner">
        {/* Brand Section */}
        <div className="brand-section">
          <div className="brand-avatar">S</div>
          <div>
            <h1 className="brand-title">Sangeeta Infotech</h1>
            <p className="brand-subtitle">Autonomous Lead Discovery & Cold Outreach Engine</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="nav-tab-group">
          <button
            id="nav-tab-leads"
            onClick={() => setActiveTab('leads')}
            className={`nav-tab-btn ${activeTab === 'leads' ? 'active' : ''}`}
          >
            <Database size={16} />
            Leads Database
          </button>

          <button
            id="nav-tab-scraper"
            onClick={() => setActiveTab('scraper')}
            className={`nav-tab-btn ${activeTab === 'scraper' ? 'active' : ''}`}
          >
            <Terminal size={16} />
            Live Scraper
            {isScraperRunning && (
              <span className="badge" style={{ background: 'rgba(16, 185, 129, 0.25)', color: '#34d399', marginLeft: '4px', fontSize: '0.65rem' }}>
                <span className="pulse-dot pulse-emerald"></span> RUNNING
              </span>
            )}
          </button>

          <button
            id="nav-tab-import"
            onClick={() => setActiveTab('import')}
            className={`nav-tab-btn ${activeTab === 'import' ? 'active' : ''}`}
          >
            <DownloadCloud size={16} />
            Import & Harvester
          </button>

          <button
            id="nav-tab-settings"
            onClick={() => setActiveTab('settings')}
            className={`nav-tab-btn ${activeTab === 'settings' ? 'active' : ''}`}
          >
            <Settings size={16} />
            Company & SMTP
          </button>
        </nav>

        {/* Global Fast Actions */}
        <div className="header-actions">
          {/* Backend Status Pill */}
          <div className={`status-indicator-pill ${backendOnline ? 'status-online' : 'status-offline'}`}>
            <span className={`pulse-dot ${backendOnline ? 'pulse-emerald' : 'pulse-amber'}`}></span>
            {backendOnline ? 'API Connected' : 'Demo / Standby'}
          </div>

          <button
            id="btn-global-refresh"
            onClick={onRefreshLeads}
            disabled={isRefreshing}
            className="btn btn-secondary btn-sm"
            title="Reload leads from database"
          >
            <RefreshCw size={14} className={isRefreshing ? 'animate-spin' : ''} />
            Refresh
          </button>

          <button
            id="btn-global-scraper"
            onClick={onTriggerQuickScraper}
            disabled={isScraperRunning}
            className="btn btn-primary btn-sm"
            title="Launch Quick Scraper"
          >
            <Play size={14} />
            Launch Scraper
          </button>

          <button
            id="btn-global-sync"
            onClick={onSyncSupabase}
            className="btn btn-secondary btn-sm"
            title="Sync Leads with Supabase Cloud"
          >
            <Send size={14} />
            Supabase
          </button>
        </div>
      </div>
    </header>
  );
}
