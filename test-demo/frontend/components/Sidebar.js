'use client';

import React, { useState } from 'react';
import { 
  Database, Terminal, DownloadCloud, Settings, 
  Send, RefreshCw, Play, ShieldCheck, Activity,
  ChevronLeft, ChevronRight, Sparkles, Layers, Download, CheckCircle2, LogOut
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
  onCloseMobile = null
}) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  const menuSections = [
    {
      title: 'CORE PLATFORM',
      items: [
        {
          id: 'leads',
          label: 'Leads Database',
          icon: Database,
          count: totalLeads > 0 ? totalLeads.toLocaleString() : '157',
          badgeType: 'lavender'
        },
        {
          id: 'scraper',
          label: 'Live Scraper Console',
          icon: Terminal,
          statusBadge: isScraperRunning ? 'RUNNING' : 'READY',
          badgeType: isScraperRunning ? 'green' : 'slate'
        }
      ]
    },
    {
      title: 'GROWTH ENGINES',
      items: [
        {
          id: 'import',
          label: 'Import & Harvester',
          icon: DownloadCloud,
          tag: 'Multi-Source',
          badgeType: 'pink'
        }
      ]
    },
    {
      title: 'PREFERENCES',
      items: [
        {
          id: 'settings',
          label: 'Company & SMTP',
          icon: Settings
        }
      ]
    }
  ];

  const handleNavClick = (id) => {
    setActiveTab(id);
    if (onCloseMobile) onCloseMobile();
  };

  return (
    <>
      {/* Mobile Drawer Overlay Backdrop */}
      {isMobileOpen && (
        <div
          className="sidebar-mobile-backdrop"
          onClick={onCloseMobile}
          aria-hidden="true"
        />
      )}

      <aside className={`saas-sidebar ${isCollapsed ? 'collapsed' : ''} ${isMobileOpen ? 'mobile-open' : ''}`}>
        {/* Brand Header */}
        <div className="sidebar-header">
          <div className="sidebar-brand-wrapper">
            <div className="brand-logo-glow">S</div>
            {!isCollapsed && (
              <div className="brand-text">
                <div className="brand-title-row">
                  <span className="brand-name">Sangeeta Infotech</span>
                  <span className="brand-pro-tag">PRO</span>
                </div>
                <div className="brand-sub">Lead & Outreach Engine</div>
              </div>
            )}
          </div>
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="collapse-toggle"
            title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-label="Toggle sidebar collapse"
          >
            {isCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
          </button>
        </div>

        {/* Navigation Sections */}
        <div className="sidebar-body">
          {menuSections.map((sec, sIdx) => (
            <div key={sIdx} className="nav-section">
              {!isCollapsed && <div className="nav-section-title">{sec.title}</div>}
              <nav className="nav-items-list" role="navigation">
                {sec.items.map((item) => {
                  const Icon = item.icon;
                  const isActive = activeTab === item.id;

                  return (
                    <button
                      key={item.id}
                      id={`nav-item-${item.id}`}
                      onClick={() => handleNavClick(item.id)}
                      className={`nav-item-btn ${isActive ? 'active' : ''}`}
                      title={isCollapsed ? item.label : undefined}
                      data-tooltip={item.label}
                    >
                      <div className="nav-item-left">
                        <div className={`nav-icon-container ${isActive ? 'icon-active' : ''}`}>
                          <Icon size={18} />
                        </div>
                        {!isCollapsed && <span className="nav-label">{item.label}</span>}
                      </div>

                      {!isCollapsed && (
                        <div className="nav-item-right">
                          {item.count && (
                            <span className={`pill-counter pill-${item.badgeType}`}>
                              {item.count}
                            </span>
                          )}
                          {item.statusBadge && (
                            <span className={`pill-status pill-${item.badgeType}`}>
                              {item.id === 'scraper' && isScraperRunning && (
                                <span className="live-dot-pulse"></span>
                              )}
                              {item.statusBadge}
                            </span>
                          )}
                          {item.tag && (
                            <span className="pill-tag">{item.tag}</span>
                          )}
                        </div>
                      )}
                    </button>
                  );
                })}
              </nav>
            </div>
          ))}

        {/* Quick Actions Shortcuts Panel */}
        {!isCollapsed && (
          <div className="sidebar-actions-card">
            <div className="actions-card-title">
              <Sparkles size={13} style={{ color: 'var(--primary-lavender)' }} />
              Quick Automations
            </div>
            <div className="actions-button-stack">
              <button
                onClick={onTriggerQuickScraper}
                disabled={isScraperRunning}
                className="btn-quick btn-quick-primary"
              >
                <Play size={13} />
                {isScraperRunning ? 'Scraper Busy...' : 'Run Quick Scraper'}
              </button>

              <button
                onClick={onSyncSupabase}
                className="btn-quick btn-quick-secondary"
              >
                <Send size={13} />
                Sync to Supabase
              </button>

              <a
                href="/api/export-csv"
                download
                className="btn-quick btn-quick-secondary"
              >
                <Download size={13} />
                Export Leads CSV
              </a>
            </div>
          </div>
        )}
      </div>

      {/* Footer System Connectivity & User Profile */}
      <div className="sidebar-bottom">
        <div className={`system-health-pill ${backendOnline ? 'online' : 'standby'}`}>
          <div className="health-left">
            <span className={`pulse-dot ${backendOnline ? 'pulse-emerald' : 'pulse-amber'}`}></span>
            {!isCollapsed && (
              <div className="health-info">
                <span className="health-title">
                  {backendOnline ? 'Python DB Connected' : 'Python Standby'}
                </span>
                <span className="health-desc">
                  {backendOnline ? 'Port 5000 Active' : 'Run python app.py'}
                </span>
              </div>
            )}
          </div>
          {!isCollapsed && (
            <button
              onClick={onRefreshLeads}
              disabled={isRefreshing}
              className="refresh-btn"
              title="Refresh leads database"
            >
              <RefreshCw size={13} className={isRefreshing ? 'animate-spin' : ''} />
            </button>
          )}
        </div>

        {/* User Account & Logout */}
        {user && !isCollapsed && (
          <div className="sidebar-user-strip">
            <div className="user-avatar-circle">
              {(user.email || 'A')[0].toUpperCase()}
            </div>
            <div className="user-details">
              <span className="user-name">{user.user_metadata?.full_name || 'Admin'}</span>
              <span className="user-email" title={user.email}>{user.email}</span>
            </div>
            {onSignOut && (
              <button
                onClick={onSignOut}
                className="user-logout-btn"
                title="Sign out of workspace"
              >
                <LogOut size={14} />
              </button>
            )}
          </div>
        )}
      </div>
    </aside>
  </>
  );
}
