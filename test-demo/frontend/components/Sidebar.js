'use client';

import React, { useEffect, useState } from 'react';
import { 
  Database, Terminal, DownloadCloud, Settings, 
  Send, RefreshCw, Play, Download, LogOut, ChevronDown, ChevronRight, Zap,
  LayoutDashboard, Briefcase, History, Building2, Pickaxe, SearchCode, MapPin, Share2, Megaphone,
  ShoppingCart, Globe, MessageCircle, House, FileSearch, Network, Factory, Phone, Wrench, Ship, Store,
  Landmark, BadgeCheck, Receipt, Contact, Globe2, MailCheck, PhoneCall, FileUp, Bug, Network as NetworkIcon, Link2, TextSearch, ListTree, FolderUp, Wrench as WrenchIcon, Gauge, Globe as GlobeIcon, CalendarClock, MailSearch, Sparkles, CheckSquare, HeartPulse, Eraser, Wand2
} from 'lucide-react';

// Scraping / Mining submenu (order as requested). soon = planned module (MiningComingSoon.js)
export const MINING_ITEMS = [
  { id: 'searchengines', label: 'Search Engines', icon: SearchCode },
  { id: 'mining-maps', label: 'Google Maps', icon: MapPin },
  { id: 'mining-social', label: 'Social Media', icon: Share2 },
  { id: 'mining-adlibrary', label: 'Ad Library', icon: Megaphone },
  { id: 'mining-ecommerce', label: 'Ecommerce Platforms', icon: ShoppingCart },
  { id: 'jobportal', label: 'Job Portals', icon: Briefcase },
  { id: 'mining-directories', label: 'Global Directories', icon: Globe },
  { id: 'mining-whatsapp', label: 'WhatsApp Groups', icon: MessageCircle },
  { id: 'mining-realestate', label: 'Real Estate', icon: House }
];

// Data Extraction submenu. section = sub-heading inside the group (more sections can be added later).
// Each Indian Directories item opens IndianDirectory.js with its own source (tab id 'dx-<source id>').
export const EXTRACTION_ITEMS = [
  { id: 'dx-mlmdiary', label: 'MLMDiary Scraper', icon: Network, section: 'Indian Directories' },
  { id: 'dx-indiamart', label: 'IndiaMART Scraper', icon: Factory, section: 'Indian Directories' },
  { id: 'dx-justdial', label: 'Justdial Scraper', icon: Phone, section: 'Indian Directories' },
  { id: 'dx-sulekha', label: 'Sulekha Scraper', icon: Wrench, section: 'Indian Directories' },
  { id: 'dx-tradeindia', label: 'TradeIndia Scraper', icon: Store, section: 'Indian Directories' },
  { id: 'dx-exportersindia', label: 'ExportersIndia Scraper', icon: Ship, section: 'Indian Directories' },
  // Corporate Registries: CorporateRegistry.js with mode 'company' | 'pvtltd' | 'gst' (tab id 'cr-<mode>')
  { id: 'cr-company', label: 'Company Scraper', icon: Landmark, section: 'Corporate Registries' },
  { id: 'cr-pvtltd', label: 'PVT LTD Scraper', icon: BadgeCheck, section: 'Corporate Registries' },
  { id: 'cr-gst', label: 'GST No Scraper', icon: Receipt, section: 'Corporate Registries' }
];

// Bulk Contacts submenu: BulkContacts.js with tool 'websites' | 'emails' | 'phones' | 'import' (tab id 'bc-<tool>')
export const BULK_ITEMS = [
  { id: 'bc-websites', label: 'Bulk Website Contacts', icon: Globe2 },
  { id: 'bc-emails', label: 'Bulk Email Verifier', icon: MailCheck },
  { id: 'bc-phones', label: 'Bulk Phone Cleaner', icon: PhoneCall },
  { id: 'bc-import', label: 'Contact Import & Dedupe', icon: FileUp }
];

// Web Crawler submenu: WebCrawler.js with tool 'site' | 'links' | 'keywords' | 'sitemap' (tab id 'wc-<tool>')
export const CRAWLER_ITEMS = [
  { id: 'wc-site', label: 'Site Crawler', icon: Bug },
  { id: 'wc-links', label: 'Link Harvester', icon: Link2 },
  { id: 'wc-keywords', label: 'Keyword Page Finder', icon: TextSearch },
  { id: 'wc-sitemap', label: 'Sitemap Explorer', icon: ListTree }
];

// Lead Care submenu: tools that work on the saved leads (tab id 'lc-<tool>')
export const LEADCARE_ITEMS = [
  { id: 'lc-cleanup', label: 'Data Cleanup', icon: Eraser },
  { id: 'lc-enrich', label: 'Lead Enrichment', icon: Wand2 }
];

// Domain Tools submenu: DomainTools.js with tool 'age' | 'dns' | 'new' | 'available' (tab id 'dt-<tool>')
export const DOMAIN_ITEMS = [
  { id: 'dt-age', label: 'Domain Age & Expiry', icon: CalendarClock },
  { id: 'dt-dns', label: 'Email & DNS Checker', icon: MailSearch },
  { id: 'dt-new', label: 'New Domains Finder', icon: Sparkles },
  { id: 'dt-available', label: 'Domain Availability', icon: CheckSquare }
];

// Utilities submenu (tab id 'ut-<tool>')
export const UTILITY_ITEMS = [
  { id: 'ut-analyzer', label: 'Website Analyzer', icon: Gauge }
];

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
      id: 'dashboard',
      label: 'Dashboard',
      icon: LayoutDashboard
    },
    {
      id: 'mining',
      label: 'Scraping / Mining',
      icon: Pickaxe,
      children: MINING_ITEMS
    },
    {
      id: 'extraction',
      label: 'Data Extraction',
      icon: FileSearch,
      children: EXTRACTION_ITEMS
    },
    {
      id: 'bulk',
      label: 'Bulk Contacts',
      icon: Contact,
      children: BULK_ITEMS
    },
    {
      id: 'crawler',
      label: 'Web Crawler',
      icon: NetworkIcon,
      children: CRAWLER_ITEMS
    },
    {
      id: 'domains',
      label: 'Domain Tools',
      icon: GlobeIcon,
      children: DOMAIN_ITEMS
    },
    {
      id: 'utilities',
      label: 'Utilities',
      icon: WrenchIcon,
      children: UTILITY_ITEMS
    },
    {
      id: 'fileuploads',
      label: 'File Uploads',
      icon: FolderUp
    },
    {
      id: 'followups',
      label: 'FollowUp History',
      icon: History
    },
    {
      id: 'crmsources',
      label: 'CRM Sources',
      icon: Building2
    },
    {
      id: 'leadcare',
      label: 'Lead Care',
      icon: HeartPulse,
      children: LEADCARE_ITEMS
    },
    {
      id: 'leads',
      label: 'Leads Intelligence',
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

  // Groups with a submenu: open by default (main work areas); the group of the active page always opens
  const [openGroups, setOpenGroups] = useState({ mining: true, extraction: true, bulk: true, crawler: true, utilities: true, domains: true, leadcare: true });
  const activeGroup = navItems.find(i => i.children && i.children.some(c => c.id === activeTab))?.id;
  useEffect(() => { if (activeGroup) setOpenGroups(prev => (prev[activeGroup] ? prev : { ...prev, [activeGroup]: true })); }, [activeGroup]);
  const toggleGroup = (id) => setOpenGroups(prev => ({ ...prev, [id]: !prev[id] }));

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
            <Zap size={17} color="#2563eb" style={{ flexShrink: 0 }} />
            {!isCollapsed && (
              <>
                <span className="theme-business-name" style={{ fontWeight: 700, letterSpacing: '-0.02em' }}>LeadsGen AI</span>
                <span style={{ fontSize: '10px', background: '#dbeafe', color: '#1e40af', padding: '1px 6px', borderRadius: '999px', fontWeight: 600, marginLeft: 'auto' }}>PRO</span>
              </>
            )}
          </div>
          {!isCollapsed && (
            <div className="theme-business-alt" title="Autonomous B2B Prospecting & Intelligence">
              <span className={`theme-status-dot ${backendOnline ? 'online' : 'standby'}`}></span>
              <span className="theme-business-sub">{backendOnline ? 'Autonomous Engine Online' : 'Engine Standby'}</span>
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

            if (item.children) {
              // Collapsed sidebar: show the submenu icons directly (no room for a group header)
              if (isCollapsed) {
                return item.children.map(child => {
                  const ChildIcon = child.icon;
                  return (
                    <div key={child.id} id={`nav-item-${child.id}`} onClick={() => handleNavClick(child.id)}
                      className={`theme-nav-item ${activeTab === child.id ? 'active' : ''}`} title={`${item.label}: ${child.label}${child.soon ? ' (soon)' : ''}`}>
                      <ChildIcon size={17} strokeWidth={1.6} style={{ flexShrink: 0 }} />
                    </div>
                  );
                });
              }
              const groupOpen = !!openGroups[item.id];
              const groupActive = activeGroup === item.id;
              return (
                <div key={item.id} className="theme-nav-group">
                  <div
                    id={`nav-group-${item.id}`}
                    role="button"
                    tabIndex={0}
                    aria-expanded={groupOpen}
                    onClick={() => toggleGroup(item.id)}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleGroup(item.id); } }}
                    className={`theme-nav-item ${groupActive && !groupOpen ? 'active' : ''}`}
                  >
                    <Icon size={17} strokeWidth={1.6} style={{ flexShrink: 0 }} />
                    <span className="theme-nav-label">{item.label}</span>
                    {groupOpen ? <ChevronDown size={14} className="theme-nav-chevron" /> : <ChevronRight size={14} className="theme-nav-chevron" />}
                  </div>
                  {groupOpen && (
                    <div className="theme-nav-sub" role="group" aria-label={item.label}>
                      {item.children.map((child, idx) => {
                        const ChildIcon = child.icon;
                        const newSection = child.section && child.section !== item.children[idx - 1]?.section;
                        return (
                          <React.Fragment key={child.id}>
                          {newSection && <div className="theme-nav-section" role="presentation">{child.section}</div>}
                          <div key={child.id} id={`nav-item-${child.id}`} onClick={() => handleNavClick(child.id)}
                            className={`theme-nav-item theme-nav-subitem ${activeTab === child.id ? 'active' : ''}`}>
                            <ChildIcon size={15} strokeWidth={1.6} style={{ flexShrink: 0 }} />
                            <span className="theme-nav-label">{child.label}</span>
                            {child.soon && <span className="theme-nav-badge soon">Soon</span>}
                          </div>
                          </React.Fragment>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            }

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
