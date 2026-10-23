'use client';

import React from 'react';
import { 
  Database, Terminal, DownloadCloud, Settings, 
  Send, RefreshCw, Play, Download, LogOut, ChevronDown, ChevronRight, Zap
} from 'lucide-react';

export default function Sidebar({
  activeTab,
  setActiveTab,
  isScraperRunning,
  backendOnline,
  totalLeads = 0,
  onTriggerQuickScraper,
  onSyncSupabase,
  onRefreshLeads,
  isRefreshing,
  user = null,
  onSignOut = null,
  isMobileOpen = false,
  onCloseMobile = null,
  isCollapsed = false
}) {
  const navItems = [
    {
      id: 'leads',
      label: 'Leads Database',
      icon: Database,
      badge: totalLeads > 0 ? totalLeads.toLocaleString() : '0'
    },
    {
      id: 'scraper',
      label: 'Live Scrapers',
      icon: Terminal,
      badge: isScraperRunning ? 'RUNNING' : '12 READY'
    },
    {
      id: 'import',
      label: 'Import & Parse',
      icon: DownloadCloud
    },
    {
      id: 'settings',
      label: 'Settings & SMTP',
      icon: Settings
    }
  ];

  const handleNavClick = (id) => {
    setActiveTab(id);
    if (onCloseMobile) onCloseMobile();
  };

  const ownerName = user?.user_metadata?.full_name || (user?.email ? user.email.split('@')[0] : 'Admin');

  return (
    <>
      {isMobileOpen && (
        <div
          className="sidebar-mobile-backdrop"
          onClick={onCloseMobile}
          aria-hidden="true"
        />
      )}

      <aside className={`theme-sidebar ${isCollapsed ? 'collapsed' : ''} ${isMobileOpen ? 'mobile-open' : ''}`}>
        {/* User Account Row */}
        <div className="theme-user-row">
          <div className="theme-user-avatar">
            <svg width="15" height="15" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6">
              <circle cx="10" cy="7" r="3.2" />
              <path d="M4 17c0-3.2 2.7-5 6-5s6 1.8 6 5" />
            </svg>
          </div>
          {!isCollapsed && <span className="theme-user-name">{ownerName}</span>}
        </div>

        {/* Workspace Brand / Business Row */}
        <div className="theme-business-stack">
          <div className="theme-business-active">
            <svg width="17" height="17" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ flexShrink: 0 }}>
              <path d="M3 7.5 4.5 4h11L17 7.5M3.5 7.5h13V16h-13z" />
              <path d="M3.5 7.5h13" />
            </svg>
            {!isCollapsed && (
              <>
                <span className="theme-business-name">Sangeeta Infotech</span>
                <ChevronDown size={14} color="#8a8f98" style={{ marginLeft: 'auto', flexShrink: 0 }} />
              </>
            )}
          </div>
          {!isCollapsed && (
            <div className="theme-business-alt" title="Lead Generation Pipeline">
              <span className={`theme-status-dot ${backendOnline ? 'online' : 'standby'}`}></span>
              <span className="theme-business-sub">{backendOnline ? 'Python DB Online' : 'Python Standby'}</span>
            </div>
          )}
        </div>

        {/* Favorites & Quick Navigation (when expanded) */}
        {!isCollapsed && (
          <div className="theme-favorites-section">
            <div className="theme-favorites-header">
              <span className="theme-fav-title">Favorites</span>
              <span className="theme-fav-tab" onClick={onRefreshLeads}>
                {isRefreshing ? 'Refreshing...' : 'Refresh DB'}
              </span>
            </div>
            <div className="theme-favorites-list">
              <div 
                className={`theme-fav-item ${activeTab === 'leads' ? 'active' : ''}`}
                onClick={() => handleNavClick('leads')}
              >
                <span className="theme-fav-dot"></span>
                <span>Active Leads Queue</span>
              </div>
              <div 
                className={`theme-fav-item ${activeTab === 'scraper' ? 'active' : ''}`}
                onClick={() => handleNavClick('scraper')}
              >
                <span className="theme-fav-dot"></span>
                <span>Scraper Console</span>
              </div>
            </div>
          </div>
        )}

        {/* Main Navigation Menu */}
        <nav className="theme-nav-list" role="navigation">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;

            return (
              <div
                key={item.id}
                id={`nav-item-${item.id}`}
                onClick={() => handleNavClick(item.id)}
                className={`theme-nav-item ${isActive ? 'active' : ''}`}
                title={isCollapsed ? item.label : undefined}
              >
                <Icon size={17} strokeWidth={1.6} style={{ flexShrink: 0 }} />
                {!isCollapsed && (
                  <>
                    <span className="theme-nav-label">{item.label}</span>
                    {item.badge && (
                      <span className={`theme-nav-badge ${item.badge === 'RUNNING' ? 'running' : ''}`}>
                        {item.badge}
                      </span>
                    )}
                  </>
                )}
              </div>
            );
          })}
        </nav>

        {/* Quick Actions Shortcuts (when expanded) */}
        {!isCollapsed && (
          <div className="theme-sidebar-quick-actions">
            <div className="theme-quick-label">QUICK ACTIONS</div>
            <button
              onClick={onTriggerQuickScraper}
              disabled={isScraperRunning}
              className="theme-quick-btn primary"
            >
              <Play size={12} fill="currentColor" />
              <span>{isScraperRunning ? 'Scraper Active...' : 'Run Quick Scraper'}</span>
            </button>
            <button
              onClick={onSyncSupabase}
              className="theme-quick-btn"
            >
              <Send size={12} />
              <span>Sync with Supabase</span>
            </button>
          </div>
        )}

        {/* Sidebar Brand Footer */}
        <div className="theme-sidebar-footer">
          <div className="theme-footer-brand">
            <Zap size={14} fill="currentColor" color="#1a6dff" style={{ flexShrink: 0 }} />
            {!isCollapsed && <span className="theme-footer-brand-name">LeadPro</span>}
          </div>
          {user && !isCollapsed && onSignOut && (
            <button 
              onClick={onSignOut} 
              className="theme-logout-btn" 
              title="Sign Out"
              aria-label="Sign Out"
            >
              <LogOut size={14} />
            </button>
          )}
        </div>
      </aside>
    </>
  );
}
