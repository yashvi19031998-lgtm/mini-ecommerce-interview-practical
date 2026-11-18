'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { AuthProvider, useAuth } from '../lib/auth-context';
import AuthScreen from '../components/AuthScreen';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import SearchEngine from '../components/SearchEngine';
import MiningComingSoon from '../components/MiningComingSoon';
import GlobalDirectories from '../components/GlobalDirectories';
import GoogleMaps from '../components/GoogleMaps';
import Ecommerce from '../components/Ecommerce';
import RealEstate from '../components/RealEstate';
import WhatsAppGroups from '../components/WhatsAppGroups';
import AdLibrary from '../components/AdLibrary';
import SocialMedia from '../components/SocialMedia';
import IndianDirectory from '../components/IndianDirectory';
import CorporateRegistry from '../components/CorporateRegistry';
import BulkContacts from '../components/BulkContacts';
import WebCrawler from '../components/WebCrawler';
import FileUploads from '../components/FileUploads';
import WebsiteAnalyzer from '../components/WebsiteAnalyzer';
import DomainTools from '../components/DomainTools';
import LeadCleanup from '../components/LeadCleanup';
import LeadEnrichment from '../components/LeadEnrichment';
import LeadsPage, { DEFAULT_FILTERS } from '../components/leads/LeadsPage';
import LeadPanel from '../components/leads/LeadPanel';
import TodayPage from '../components/today/TodayPage';
import SingleEmailModal from '../components/SingleEmailModal';
import BulkEmailModal from '../components/BulkEmailModal';
import WhatsAppModal from '../components/WhatsAppModal';
import ScraperConsole from '../components/ScraperConsole';
import LeadImporter from '../components/LeadImporter';
import SettingsView from '../components/SettingsView';
import Reports from '../components/Reports';
import JobPortalScraper from '../components/JobPortalScraper';
import FreelanceScraper from '../components/FreelanceScraper';
import AutoScheduler from '../components/AutoScheduler';
import FollowUpHistory from '../components/FollowUpHistory';
import CrmSources from '../components/CrmSources';
import Toast from '../components/Toast';
import ChatAssistant from '../components/ChatAssistant';
import { Loader2 } from 'lucide-react';

import {
  fetchLeads,
  patchLeadStatus,
  sendSingleEmail,
  sendBulkEmail,
  fetchScraperStatus,
  startScraper,
  stopScraper,
  fetchSettings,
  triggerSupabaseSync
} from '../lib/api';

// Every page has its own address: #/today, #/leads?action=call_pending&band=hot, #/settings ...
// so refresh, Back and bookmarks work. Old ids keep working ('dashboard' opens Today).
const TAB_ALIASES = { dashboard: 'today', 'rp-lead-status': 'today', 'rp-reply-today': 'today' };
const FILTER_KEYS = Object.keys(DEFAULT_FILTERS);

function readHash() {
  if (typeof window === 'undefined') return { tab: 'today', filters: { ...DEFAULT_FILTERS } };
  const raw = window.location.hash.replace(/^#\/?/, '');
  const [path, query = ''] = raw.split('?');
  const params = new URLSearchParams(query);
  const filters = { ...DEFAULT_FILTERS };
  FILTER_KEYS.forEach(k => { if (params.get(k)) filters[k] = params.get(k); });
  const tab = TAB_ALIASES[path] || path || 'today';
  return { tab, filters };
}

function hashFor(tab, filters) {
  if (tab !== 'leads') return `#/${tab}`;
  const params = new URLSearchParams();
  FILTER_KEYS.forEach(k => { if (filters[k] && filters[k] !== DEFAULT_FILTERS[k]) params.set(k, filters[k]); });
  const q = params.toString();
  return `#/leads${q ? `?${q}` : ''}`;
}

function DashboardContent() {
  const { user, signOut, loading: authLoading } = useAuth();

  const [activeTab, setActiveTabRaw] = useState('today'); // 'today' | 'leads' | 'followups' | 'rp-*' | tool pages ...
  const [leadFilters, setLeadFilters] = useState(DEFAULT_FILTERS);
  const [panelLeadId, setPanelLeadId] = useState(null);
  const [todayReload, setTodayReload] = useState(0);
  const setActiveTab = useCallback((tab) => setActiveTabRaw(TAB_ALIASES[tab] || tab), []);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [leads, setLeads] = useState([]);
  const [backendOnline, setBackendOnline] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [globalSearch, setGlobalSearch] = useState('');

  // Scraper State
  const [isScraperRunning, setIsScraperRunning] = useState(false);
  const [scraperLogs, setScraperLogs] = useState([]);
  const [autoScrollLogs, setAutoScrollLogs] = useState(true);

  // Modals
  const [selectedLeadForEmail, setSelectedLeadForEmail] = useState(null);
  const [selectedLeadForWhatsApp, setSelectedLeadForWhatsApp] = useState(null);
  const [bulkEmailOpen, setBulkEmailOpen] = useState(false);
  const [bulkEmailLeadIds, setBulkEmailLeadIds] = useState([]);
  const [signature, setSignature] = useState('');

  // Toasts
  const [toasts, setToasts] = useState([]);

  const showToast = useCallback((message, type = 'info') => {
    const id = Date.now() + Math.random().toString(36).substring(2, 6);
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4500);
  }, []);

  const dismissToast = (id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  };

  // Load leads
  const loadLeads = useCallback(async (silent = false) => {
    if (!silent) setIsRefreshing(true);
    try {
      const res = await fetchLeads();
      if (res && res.leads) {
        setLeads(res.leads);
        setBackendOnline(!!res.backendOnline);
      }
    } catch (err) {
      if (!silent) showToast(err.message || 'Error loading leads', 'error');
    } finally {
      if (!silent) setIsRefreshing(false);
    }
  }, [showToast]);

  // Load settings & signature
  useEffect(() => {
    if (user) {
      fetchSettings().then(res => {
        if (res && res.formattedSignature) {
          setSignature(res.formattedSignature);
        }
      });
      loadLeads();
    }
  }, [user, loadLeads]);

  // Poll Scraper Status
  const scraperIntervalRef = useRef(null);

  useEffect(() => {
    if (!user) return;

    const pollStatus = async () => {
      try {
        const status = await fetchScraperStatus();
        setIsScraperRunning(!!status.running);
        if (status.logs && status.logs.length) {
          setScraperLogs(status.logs);
        }
      } catch {
        // Standby
      }
    };

    pollStatus();
    scraperIntervalRef.current = setInterval(pollStatus, 2000);
    return () => clearInterval(scraperIntervalRef.current);
  }, [user]);

  // Auto-refresh leads when scraper finishes
  const prevRunningRef = useRef(isScraperRunning);
  useEffect(() => {
    if (prevRunningRef.current && !isScraperRunning) {
      showToast('Scraper run completed! Auto-refreshing leads...', 'success');
      loadLeads(true);
    }
    prevRunningRef.current = isScraperRunning;
  }, [isScraperRunning, loadLeads, showToast]);

  // Address bar <-> page: read it on load and on Back/Forward, write it when the page or filters change
  const [routeReady, setRouteReady] = useState(false);
  useEffect(() => {
    const apply = () => {
      const { tab, filters } = readHash();
      setActiveTabRaw(tab);
      setLeadFilters(filters);
    };
    apply();
    setRouteReady(true);
    window.addEventListener('hashchange', apply);
    return () => window.removeEventListener('hashchange', apply);
  }, []);
  useEffect(() => {
    if (!routeReady) return; // the address bar is read first, never overwritten on load
    const next = hashFor(activeTab, leadFilters);
    if (window.location.hash !== next) window.history.pushState(null, '', next);
  }, [activeTab, leadFilters, routeReady]);

  // If Auth is loading
  if (authLoading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#fff' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem', color: '#1a6dff' }}>
          <Loader2 size={32} className="animate-spin" />
          <span style={{ fontSize: '0.88rem', fontWeight: 600, color: '#5b5f67' }}>Connecting to Workspace...</span>
        </div>
      </div>
    );
  }

  // If no user is logged in, show AuthScreen
  if (!user) {
    return <AuthScreen />;
  }

  // Handlers
  const handleLeadStatusChange = async (leadId, newStatus) => {
    setLeads(prev => prev.map(l => l.id === leadId ? { ...l, Status: newStatus, status: newStatus } : l));
    try {
      await patchLeadStatus(leadId, newStatus);
      showToast('Outcome saved', 'success');
      loadLeads(true); // next step changes with the outcome
    } catch (err) {
      showToast(`Could not save the outcome: ${err.message}`, 'error');
    }
  };

  const openLeads = (patch = {}) => {
    setLeadFilters({ ...DEFAULT_FILTERS, view: leadFilters.view, ...patch });
    setActiveTab('leads');
  };
  const panelLead = panelLeadId ? leads.find(l => l.id === panelLeadId || l.lead_id === panelLeadId) : null;


  const handleSendSingleEmail = async ({ id, to, subject, message }) => {
    try {
      const res = await sendSingleEmail({ id, to, subject, message });
      setLeads(prev => prev.map(l => l.id === id ? {
        ...l,
        Status: 'EMAIL_SENT',
        'Email Status': 'SENT',
        'Email Sent At': new Date().toISOString().replace('T', ' ').substring(0, 19)
      } : l));
      showToast(`Email dispatched to ${to}!`, 'success');
      return res;
    } catch (err) {
      showToast(err.message || 'SMTP Send error', 'error');
      throw err;
    }
  };

  const handleSendBulkEmail = async ({ lead_ids, subject, message, delay_ms }, onProgress = null) => {
    try {
      const res = await sendBulkEmail({ lead_ids, subject, message, delay_ms }, onProgress);
      // Only leads the server really e-mailed are marked as sent. Before, every selected lead was shown
      // as EMAIL_SENT and the message counted all of them, even when some (or all) were refused.
      const sentIds = new Set((res.results || []).filter(r => r.success).map(r => String(r.id)));
      const alreadySentIds = new Set((res.results || []).filter(r => r.reason === 'already_sent' || r.already_sent).map(r => String(r.id)));
      const sentCount = Number.isFinite(Number(res.sent)) ? Number(res.sent) : sentIds.size;
      const failedCount = Number(res.failed) || 0;
      setLeads(prev => prev.map(l => {
        const lid = String(l.id);
        if (sentIds.has(lid)) {
          return {
            ...l,
            Status: 'EMAIL_SENT',
            'Email Status': 'SENT',
            'Email Sent At': new Date().toISOString().replace('T', ' ').substring(0, 19)
          };
        }
        if (alreadySentIds.has(lid)) {
          return {
            ...l,
            Status: 'EMAIL_SENT',
            'Email Status': 'SENT'
          };
        }
        return l;
      }));
      const notSent = (Number(res.not_verified) || 0) + (Number(res.skipped) || 0) + failedCount;
      const firstError = res.stopped_reason || (res.results || []).find(r => !r.success)?.error;
      const allAlreadySent = alreadySentIds.size > 0 && sentCount === 0 && (res.results || []).every(r => r.reason === 'already_sent' || r.already_sent || !r.email);
      // Next step and pending channels are worked out on the server: reload so mailed leads leave "Email pending"
      loadLeads(true);
      setTodayReload(n => n + 1);
      if (sentCount === 0) {
        if (allAlreadySent) {
          showToast(`Selected leads were already contacted previously (Spam-prevention protected).`, 'info');
        } else {
          showToast(`No e-mails were sent. ${firstError || 'All selected leads were skipped.'}`, 'error');
        }
      } else if (notSent > 0) {
        showToast(`${sentCount} e-mail${sentCount === 1 ? '' : 's'} sent, ${notSent} not sent (see the list in the pop-up).`, 'info');
      } else {
        showToast(`Campaign finished! ${sentCount} e-mail${sentCount === 1 ? '' : 's'} dispatched.`, 'success');
      }
      return res;
    } catch (err) {
      showToast(err.message || 'Bulk outreach error', 'error');
      throw err;
    }
  };

  const handleStartScraperMode = async (mode) => {
    // Started from small icons in several places (top bar, sidebar, leads page): always ask first.
    const what = mode === 'all'
      ? 'Start the master run (all sources) now?\n\nIt runs in the background for several minutes and, when auto e-mail is on, also sends intro e-mails to new qualified leads.'
      : 'Start the quick scraper now?\n\nIt runs in the background for a few minutes and adds new leads to the list.';
    if (!window.confirm(what)) return;
    try {
      const res = await startScraper(mode);
      setIsScraperRunning(true);
      showToast(res.message || `Scraper (${mode}) initiated in background!`, 'info');
    } catch (err) {
      showToast(err.message || 'Failed starting scraper', 'error');
    }
  };

  const handleStopScraper = async () => {
    try {
      const res = await stopScraper();
      setIsScraperRunning(false);
      showToast(res.message || 'Scraper process stopped.', 'info');
    } catch (err) {
      showToast(err.message || 'Failed stopping scraper', 'error');
    }
  };

  const handleSyncSupabase = async () => {
    try {
      const res = await triggerSupabaseSync();
      showToast(res.message || 'Leads synchronized to Supabase Cloud!', 'success');
    } catch (err) {
      showToast(err.message || 'Supabase sync failed', 'error');
    }
  };

  return (
    <div className="theme-app-wrapper">
      {/* Sidebar with Theme Layout */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        isScraperRunning={isScraperRunning}
        backendOnline={backendOnline}
        totalLeads={leads.length}
        onTriggerQuickScraper={() => handleStartScraperMode('quick')}
        onSyncSupabase={handleSyncSupabase}
        onRefreshLeads={() => loadLeads(false)}
        isRefreshing={isRefreshing}
        user={user}
        onSignOut={signOut}
        isMobileOpen={isMobileOpen}
        onCloseMobile={() => setIsMobileOpen(false)}
        isCollapsed={isSidebarCollapsed}
      />

      {/* Main Content Pane */}
      <main className="theme-main-pane">
        {/* Header with Search and Breadcrumb */}
        <Header
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          isScraperRunning={isScraperRunning}
          backendOnline={backendOnline}
          onRefreshLeads={() => loadLeads(false)}
          isRefreshing={isRefreshing}
          onTriggerQuickScraper={() => handleStartScraperMode('quick')}
          onSyncSupabase={handleSyncSupabase}
          user={user}
          onSignOut={signOut}
          onToggleCollapse={() => {
            // Small screens: open/close the sidebar as a drawer. Desktop: collapse/expand it.
            if (typeof window !== 'undefined' && window.innerWidth <= 900) setIsMobileOpen(prev => !prev);
            else setIsSidebarCollapsed(prev => !prev);
          }}
          searchQuery={globalSearch}
          onSearchChange={(value) => {
            // The top search bar searches the leads list: typing on any other page opens that list,
            // otherwise nothing visible would happen.
            setGlobalSearch(value);
            if (value.trim()) openLeads({ q: value.trim() });
          }}
        />

        <div className="theme-scrollable-content">
          <div className="theme-content-padding">
            {/* Today: the landing page */}
            {activeTab === 'today' && (
              <TodayPage
                reloadKey={todayReload}
                onOpenLead={(id) => setPanelLeadId(id)}
                onOpenLeads={openLeads}
                onFindLeads={() => setActiveTab('scraper')}
                notify={showToast}
              />
            )}

            {/* Reports module */}
            {(activeTab === 'reports' || activeTab.startsWith('rp-')) && (
              <Reports
                section={activeTab.startsWith('rp-') ? activeTab.slice(3) : 'summary'}
                onOpenLeadsFiltered={openLeads}
                onSectionChange={(id) => setActiveTab(`rp-${id}`)}
                onOpenLeads={() => setActiveTab('leads')}
                onOpenFollowups={() => setActiveTab('followups')}
                onOpenScraper={() => setActiveTab('autoscheduler')}
              />
            )}

            {/* Scraping / Mining -> Search Engines */}
            {activeTab === 'searchengines' && (
              <SearchEngine onLeadsSaved={() => loadLeads(true)} />
            )}

            {/* Scraping / Mining -> planned modules */}
            {activeTab === 'mining-directories' && (
              <GlobalDirectories onLeadsSaved={() => loadLeads(true)} onOpenSearchEngine={() => setActiveTab('searchengines')} />
            )}
            {activeTab === 'mining-maps' && (
              <GoogleMaps onLeadsSaved={() => loadLeads(true)} />
            )}
            {activeTab === 'mining-ecommerce' && (
              <Ecommerce onLeadsSaved={() => loadLeads(true)} onOpenSearchEngine={() => setActiveTab('searchengines')} />
            )}
            {activeTab === 'mining-realestate' && (
              <RealEstate onLeadsSaved={() => loadLeads(true)} />
            )}
            {activeTab === 'mining-social' && (
              <SocialMedia onLeadsSaved={() => loadLeads(true)} onOpenSearchEngine={() => setActiveTab('searchengines')} />
            )}
            {activeTab === 'mining-adlibrary' && (
              <AdLibrary onLeadsSaved={() => loadLeads(true)} onOpenSearchEngine={() => setActiveTab('searchengines')} />
            )}
            {activeTab === 'mining-whatsapp' && (
              <WhatsAppGroups onLeadsSaved={() => loadLeads(true)} onOpenSearchEngine={() => setActiveTab('searchengines')} />
            )}
            {activeTab.startsWith('mining-') && !['mining-directories', 'mining-maps', 'mining-ecommerce', 'mining-realestate', 'mining-social', 'mining-adlibrary', 'mining-whatsapp'].includes(activeTab) && (
              <MiningComingSoon id={activeTab} onOpenSearchEngine={() => setActiveTab('searchengines')} />
            )}

            {/* CRM Sources */}
            {activeTab.startsWith('dx-') && (
              <IndianDirectory key={activeTab} sourceId={activeTab.slice(3)} onLeadsSaved={() => loadLeads(true)}
                onOpenSource={(id) => setActiveTab(`dx-${id}`)} />
            )}
            {activeTab.startsWith('cr-') && (
              <CorporateRegistry key={activeTab} mode={activeTab.slice(3)} onLeadsSaved={() => loadLeads(true)} />
            )}
            {activeTab.startsWith('bc-') && (
              <BulkContacts key={activeTab} tool={activeTab.slice(3)} onLeadsSaved={() => loadLeads(true)} />
            )}
            {activeTab.startsWith('wc-') && (
              <WebCrawler key={activeTab} tool={activeTab.slice(3)} onLeadsSaved={() => loadLeads(true)} />
            )}
            {activeTab === 'fileuploads' && (
              <FileUploads onLeadsSaved={() => loadLeads(true)} />
            )}
            {activeTab === 'ut-analyzer' && (
              <WebsiteAnalyzer onLeadsSaved={() => loadLeads(true)} />
            )}
            {activeTab.startsWith('dt-') && (
              <DomainTools key={activeTab} tool={activeTab.slice(3)} onLeadsSaved={() => loadLeads(true)} />
            )}
            {activeTab === 'lc-cleanup' && (
              <LeadCleanup onLeadsChanged={() => loadLeads(true)} />
            )}
            {activeTab === 'lc-enrich' && (
              <LeadEnrichment onLeadsChanged={() => loadLeads(true)} onOpenCleanup={() => setActiveTab('lc-cleanup')} />
            )}
            {activeTab === 'crmsources' && (
              <CrmSources onLeadsSaved={() => loadLeads(true)} />
            )}

            {/* FollowUp History */}
            {activeTab === 'followups' && (
              <FollowUpHistory leads={leads} showToast={showToast} />
            )}

            {/* Freelance Scraper: freelance / contract-work sources only */}
            {activeTab === 'freelance' && (
              <FreelanceScraper
                showToast={showToast}
                onLeadsSaved={() => loadLeads(true)}
                onOpenReplyToday={() => setActiveTab('rp-reply-today')}
              />
            )}

            {/* Job Portal Scraper */}
            {activeTab === 'jobportal' && (
              <JobPortalScraper
                showToast={showToast}
                onLeadsSaved={() => loadLeads(true)}
              />
            )}

            {/* TAB 1: Leads CRM & Database */}
            {activeTab === 'leads' && (
              <LeadsPage
                leads={leads}
                loading={isRefreshing}
                filters={leadFilters}
                onFiltersChange={setLeadFilters}
                onOpenLead={(id) => setPanelLeadId(id)}
                onBulkEmail={(ids) => { setBulkEmailLeadIds(ids); setBulkEmailOpen(true); }}
                onStatusChange={handleLeadStatusChange}
              />
            )}

            {/* TAB 2: Scraper Console */}
            {activeTab === 'scraper' && (
              <ScraperConsole
                isScraperRunning={isScraperRunning}
                scraperLogs={scraperLogs}
                autoScrollLogs={autoScrollLogs}
                setAutoScrollLogs={setAutoScrollLogs}
                onStartScraper={handleStartScraperMode}
                onStopScraper={handleStopScraper}
                onClearLogs={() => setScraperLogs([])}
                backendOnline={backendOnline}
              />
            )}

            {/* TAB: Auto Scraper (1-Hour) & Scheduler */}
            {activeTab === 'autoscheduler' && (
              <AutoScheduler
                onNavigateToSettings={() => setActiveTab('settings')}
                onNavigateToLeads={() => setActiveTab('leads')}
              />
            )}

            {/* TAB 3: Importer & Raw Extraction */}
            {activeTab === 'import' && (
              <LeadImporter
                onLeadsImported={() => loadLeads(true)}
                onOpenSearchEngine={() => setActiveTab('searchengines')}
                showToast={showToast}
              />
            )}

            {/* TAB 4: Settings & SMTP */}
            {activeTab === 'settings' && (
              <SettingsView
                onSettingsSaved={() => {
                  showToast('Company profile & SMTP configuration saved!', 'success');
                  fetchSettings().then(res => {
                    if (res && res.formattedSignature) {
                      setSignature(res.formattedSignature);
                    }
                  });
                }}
                showToast={showToast}
              />
            )}
          </div>
        </div>
      </main>

      {/* Lead panel (Today + Leads) */}
      {panelLead && (
        <LeadPanel
          lead={panelLead}
          onClose={() => setPanelLeadId(null)}
          onChanged={() => { loadLeads(true); setTodayReload(n => n + 1); }}
          onEmail={(l) => setSelectedLeadForEmail(l)}
          onWhatsApp={(l) => setSelectedLeadForWhatsApp(l)}
          notify={showToast}
        />
      )}

      {/* Outreach Modals */}
      {selectedLeadForEmail && (
        <SingleEmailModal
          isOpen={true}
          lead={selectedLeadForEmail}
          signature={signature}
          onClose={() => setSelectedLeadForEmail(null)}
          onSend={handleSendSingleEmail}
        />
      )}

      {bulkEmailOpen && (
        <BulkEmailModal
          isOpen={true}
          selectedLeadIds={bulkEmailLeadIds}
          leads={leads}
          signature={signature}
          onClose={() => {
            setBulkEmailOpen(false);
            setBulkEmailLeadIds([]);
          }}
          onBulkSend={handleSendBulkEmail}
        />
      )}

      {selectedLeadForWhatsApp && (
        <WhatsAppModal
          isOpen={true}
          lead={selectedLeadForWhatsApp}
          onClose={() => setSelectedLeadForWhatsApp(null)}
          showToast={showToast}
        />
      )}

      {/* In-app assistant: floating button, bottom right */}
      <ChatAssistant />

      {/* Global Toast Container */}
      <div className="toast-container" aria-live="polite">
        <Toast toasts={toasts} onDismiss={dismissToast} />
      </div>
    </div>
  );
}

export default function Home() {
  return (
    <AuthProvider>
      <DashboardContent />
    </AuthProvider>
  );
}
