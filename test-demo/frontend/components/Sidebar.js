'use client';

import React, { useEffect, useState } from 'react';
import {
  Database, Terminal, DownloadCloud, Settings,
  Send, Play, LogOut, ChevronDown, ChevronRight, Zap,
  LayoutDashboard, Briefcase, History, Building2, SearchCode, MapPin, Share2, Megaphone,
  ShoppingCart, Globe, MessageCircle, House, Network, Factory, Phone, Wrench, Ship, Store,
  Landmark, BadgeCheck, Receipt, Contact, Globe2, MailCheck, PhoneCall, FileUp, Bug, Link2, TextSearch, ListTree,
  FolderUp, Gauge, CalendarClock, MailSearch, Sparkles, CheckSquare, Eraser, Wand2, BarChart3, Laptop,
  Sun, Layers, Wrench as ToolsIcon, Gift
} from 'lucide-react';
import { REPORT_SECTIONS } from './Reports';

// ---------------------------------------------------------------------------------------------
// Page lists. The ids are the tab ids page.js opens, so they must not change.
// ---------------------------------------------------------------------------------------------

// Reports submenu: one entry per report section (ids rp-<section>, see Reports.js REPORT_SECTIONS)
export const REPORT_ITEMS = REPORT_SECTIONS.map(s => ({ id: `rp-${s.id}`, label: s.label, icon: s.icon }));

// Scraping / Mining sources
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

// Indian directories (IndianDirectory.js, tab 'dx-<source>') and company registries (CorporateRegistry.js, tab 'cr-<mode>')
export const EXTRACTION_ITEMS = [
  { id: 'dx-mlmdiary', label: 'MLMDiary', icon: Network, section: 'Indian Directories' },
  { id: 'dx-indiamart', label: 'IndiaMART', icon: Factory, section: 'Indian Directories' },
  { id: 'dx-justdial', label: 'Justdial', icon: Phone, section: 'Indian Directories', off: true }, // blocks automated access
  { id: 'dx-sulekha', label: 'Sulekha', icon: Wrench, section: 'Indian Directories' },
  { id: 'dx-tradeindia', label: 'TradeIndia', icon: Store, section: 'Indian Directories' },
  { id: 'dx-exportersindia', label: 'ExportersIndia', icon: Ship, section: 'Indian Directories' },
  { id: 'cr-company', label: 'Company Registry', icon: Landmark, section: 'Company Registries' },
  { id: 'cr-pvtltd', label: 'PVT LTD Companies', icon: BadgeCheck, section: 'Company Registries' },
  { id: 'cr-gst', label: 'GST Numbers', icon: Receipt, section: 'Company Registries' }
];

// Bulk Contacts: BulkContacts.js with tool 'websites' | 'emails' | 'phones' | 'import' (tab 'bc-<tool>')
export const BULK_ITEMS = [
  { id: 'bc-websites', label: 'Find Contacts on Websites', icon: Globe2 },
  { id: 'bc-emails', label: 'Verify Emails', icon: MailCheck },
  { id: 'bc-phones', label: 'Clean Phone Numbers', icon: PhoneCall },
  { id: 'bc-import', label: 'Import & Remove Duplicates', icon: FileUp }
];

// Web Crawler: WebCrawler.js with tool 'site' | 'links' | 'keywords' | 'sitemap' (tab 'wc-<tool>')
export const CRAWLER_ITEMS = [
  { id: 'wc-site', label: 'Site Crawler', icon: Bug },
  { id: 'wc-links', label: 'Link Harvester', icon: Link2 },
  { id: 'wc-keywords', label: 'Keyword Page Finder', icon: TextSearch },
  { id: 'wc-sitemap', label: 'Sitemap Explorer', icon: ListTree }
];

// Lead Care: tools that work on the saved leads (tab 'lc-<tool>')
export const LEADCARE_ITEMS = [
  { id: 'lc-cleanup', label: 'Clean Up Leads', icon: Eraser },
  { id: 'lc-enrich', label: 'Fill Missing Details', icon: Wand2 }
];

// Domain Tools: DomainTools.js with tool 'age' | 'dns' | 'new' | 'available' (tab 'dt-<tool>')
export const DOMAIN_ITEMS = [
  { id: 'dt-age', label: 'Domain Age & Expiry', icon: CalendarClock },
  { id: 'dt-dns', label: 'Email & DNS Checker', icon: MailSearch },
  { id: 'dt-new', label: 'New Domains Finder', icon: Sparkles },
  { id: 'dt-available', label: 'Domain Availability', icon: CheckSquare }
];

// Utilities (tab 'ut-<tool>')
export const UTILITY_ITEMS = [
  { id: 'ut-analyzer', label: 'Website Analyzer', icon: Gauge }
];

// Report pages pulled up into "Today" are left out of the Reports group so nothing shows twice.
// Lead Status and Reply Today live on Today / Leads now, so the Reports group leaves them out.
// Not Contacted and Follow-up Watchlist are filters on Leads now (Next step chips).
const TODAY_REPORTS = ['rp-lead-status', 'rp-reply-today', 'rp-not-contacted', 'rp-followups'];
const withSection = (items, section) => items.map(i => ({ ...i, section }));

/**
 * Sidebar menu, ordered by how often the page is used:
 *   Work          - Today (what to do now), Leads (all leads, filters, board), Follow-ups
 *   Find Leads    - running scrapers; the 18 single sources sit in one folded group
 *   Contacts      - importing and fixing lead data
 *   Insights      - reports
 *   Tools         - occasional website / domain tools, folded
 * Groups start folded; the group of the open page unfolds by itself.
 */
function buildMenu({ totalLeads, isScraperRunning }) {
  return [
    {
      title: 'Work',
      items: [
        { id: 'today', label: 'Today', icon: Sun },
        { id: 'pipeline', label: 'CRM Pipeline', icon: LayoutDashboard },
        { id: 'offers', label: 'Special Offers', icon: Gift },
        { id: 'whatsapp', label: 'WhatsApp', icon: MessageCircle },
        { id: 'leads', label: 'Leads', icon: Database, badge: totalLeads > 0 ? totalLeads.toLocaleString() : null },
        { id: 'followups', label: 'Follow-ups', icon: History }
      ]
    },
    {
      title: 'Find Leads',
      items: [
        { id: 'freelance', label: 'Freelance Projects', icon: Laptop },
        { id: 'scraper', label: 'Run Scrapers', icon: Terminal, badge: isScraperRunning ? 'RUNNING' : null },
        { id: 'autoscheduler', label: 'Auto Scraper', icon: CalendarClock },
        {
          id: 'sources', label: 'Lead Sources', icon: Layers,
          children: [...withSection(MINING_ITEMS, 'Web & Social'), ...EXTRACTION_ITEMS]
        }
      ]
    },
    {
      title: 'Contacts',
      items: [
        { id: 'import', label: 'Import Leads', icon: DownloadCloud },
        { id: 'fileuploads', label: 'Uploaded Files', icon: FolderUp },
        { id: 'crmsources', label: 'CRM Sources', icon: Building2 },
        {
          id: 'contacttools', label: 'Contact Tools', icon: Contact,
          children: [...withSection(LEADCARE_ITEMS, 'Saved Leads'), ...withSection(BULK_ITEMS, 'Bulk Lists')]
        }
      ]
    },
    {
      title: 'Insights',
      items: [
        { id: 'reports', label: 'Reports', icon: BarChart3, children: REPORT_ITEMS.filter(r => !TODAY_REPORTS.includes(r.id)) }
      ]
    },
    {
      title: 'Tools',
      items: [
        {
          id: 'tools', label: 'Web Tools', icon: ToolsIcon,
          children: [
            ...withSection(UTILITY_ITEMS, 'Website'),
            ...withSection(CRAWLER_ITEMS, 'Crawler'),
            ...withSection(DOMAIN_ITEMS, 'Domain')
          ]
        },
        { id: 'settings', label: 'Settings & Email', icon: Settings }
      ]
    }
  ];
}

/** Breadcrumb for a page id, from the menu itself so the names always match: { root, leaf }. */
export function menuPath(id) {
  for (const section of buildMenu({ totalLeads: 0, isScraperRunning: false })) {
    for (const item of section.items) {
      if (item.id === id) return { root: section.title, leaf: item.label };
      const child = item.children?.find(c => c.id === id);
      if (child) return { root: item.label, leaf: child.label };
    }
  }
  return null;
}

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
  const menu = buildMenu({ totalLeads, isScraperRunning });
  const groups = menu.flatMap(s => s.items).filter(i => i.children);
  const activeGroup = groups.find(g => g.children.some(c => c.id === activeTab))?.id;

  // Folded by default; the group of the open page unfolds by itself.
  const [openGroups, setOpenGroups] = useState({});
  useEffect(() => {
    if (activeGroup) setOpenGroups(prev => (prev[activeGroup] ? prev : { ...prev, [activeGroup]: true }));
  }, [activeGroup]);
  const toggleGroup = (id) => setOpenGroups(prev => ({ ...prev, [id]: !prev[id] }));

  const handleNavClick = (id) => {
    setActiveTab(id);
    if (onCloseMobile) onCloseMobile();
  };

  // Save to the database, then reload the list on screen.
  const refreshData = async () => {
    if (onSyncSupabase) await onSyncSupabase();
    if (onRefreshLeads) onRefreshLeads();
  };

  const ownerName = user?.user_metadata?.full_name || (user?.email ? user.email.split('@')[0] : 'Admin');

  const renderItem = (item) => {
    const Icon = item.icon;

    if (item.children) {
      const groupActive = activeGroup === item.id;
      // Narrow sidebar: one icon per group; it opens the group's first page.
      if (isCollapsed) {
        const target = groupActive ? activeTab : item.children[0].id;
        return (
          <div key={item.id} id={`nav-group-${item.id}`} onClick={() => handleNavClick(target)}
            className={`theme-nav-item ${groupActive ? 'active' : ''}`} title={item.label}>
            <Icon size={17} strokeWidth={1.6} style={{ flexShrink: 0 }} />
          </div>
        );
      }
      const groupOpen = !!openGroups[item.id];
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
                    <div id={`nav-item-${child.id}`} onClick={() => handleNavClick(child.id)}
                      className={`theme-nav-item theme-nav-subitem ${activeTab === child.id ? 'active' : ''}`}>
                      <ChildIcon size={15} strokeWidth={1.6} style={{ flexShrink: 0 }} />
                      <span className="theme-nav-label">{child.label}</span>
                      {child.soon && <span className="theme-nav-badge soon">Soon</span>}
                      {child.off && <span className="theme-nav-badge soon" title="Not available: the site blocks automated access">Off</span>}
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
        className={`theme-nav-item ${activeTab === item.id ? 'active' : ''}`}
        title={isCollapsed ? item.label : undefined}
      >
        <Icon size={17} strokeWidth={1.6} style={{ flexShrink: 0 }} />
        {!isCollapsed && (
          <>
            <span className="theme-nav-label">{item.label}</span>
            {item.badge && (
              <span className={`theme-nav-badge ${item.badge === 'RUNNING' ? 'running' : ''}`}>{item.badge}</span>
            )}
          </>
        )}
      </div>
    );
  };

  return (
    <>
      {isMobileOpen && (
        <div className="sidebar-mobile-backdrop" onClick={onCloseMobile} aria-hidden="true" />
      )}

      <aside className={`theme-sidebar ${isCollapsed ? 'collapsed' : ''} ${isMobileOpen ? 'mobile-open' : ''}`}>
        {/* Brand + engine status */}
        <div className="theme-business-stack">
          <div className="theme-business-active">
            <Zap size={17} color="#2563eb" style={{ flexShrink: 0 }} />
            {!isCollapsed && (
              <span className="theme-business-name" style={{ fontWeight: 700, letterSpacing: '-0.02em' }}>LeadsGen AI</span>
            )}
          </div>
          {!isCollapsed && (
            <div className="theme-business-alt" title={backendOnline ? 'Backend is running' : 'Backend is not reachable'}>
              <span className={`theme-status-dot ${backendOnline ? 'online' : 'standby'}`}></span>
              <span className="theme-business-sub">{backendOnline ? 'System online' : 'System offline'}</span>
            </div>
          )}
        </div>

        {/* Main menu */}
        <nav className="theme-nav-list" role="navigation">
          {menu.map(section => (
            <div key={section.title} className="theme-nav-block">
              {!isCollapsed && <div className="theme-nav-heading">{section.title}</div>}
              {section.items.map(renderItem)}
            </div>
          ))}
        </nav>

        {/* Quick actions */}
        {!isCollapsed && (
          <div className="theme-sidebar-quick-actions">
            <button onClick={onTriggerQuickScraper} disabled={isScraperRunning} className="theme-quick-btn primary">
              <Play size={12} fill="currentColor" />
              <span>{isScraperRunning ? 'Scraper running...' : 'Find New Leads Now'}</span>
            </button>
            <button onClick={refreshData} className="theme-quick-btn" disabled={isRefreshing}>
              <Send size={12} />
              <span>{isRefreshing ? 'Refreshing...' : 'Refresh Data'}</span>
            </button>
          </div>
        )}

        {/* Account */}
        <div className="theme-sidebar-footer">
          <div className="theme-footer-brand" title={user?.email || ownerName}>
            <div className="theme-user-avatar">
              <svg width="15" height="15" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6">
                <circle cx="10" cy="7" r="3.2" />
                <path d="M4 17c0-3.2 2.7-5 6-5s6 1.8 6 5" />
              </svg>
            </div>
            {!isCollapsed && <span className="theme-footer-brand-name">{ownerName}</span>}
          </div>
          {user && !isCollapsed && onSignOut && (
            <button onClick={onSignOut} className="theme-logout-btn" title="Sign Out" aria-label="Sign Out">
              <LogOut size={14} />
            </button>
          )}
        </div>
      </aside>
    </>
  );
}
