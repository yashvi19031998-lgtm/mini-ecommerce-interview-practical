'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { AuthProvider, useAuth } from '../lib/auth-context';
import AuthScreen from '../components/AuthScreen';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import StatsCards from '../components/StatsCards';
import LeadsTable from '../components/LeadsTable';
import SingleEmailModal from '../components/SingleEmailModal';
import BulkEmailModal from '../components/BulkEmailModal';
import WhatsAppModal from '../components/WhatsAppModal';
import ScraperConsole from '../components/ScraperConsole';
import LeadImporter from '../components/LeadImporter';
import SettingsView from '../components/SettingsView';
import Toast from '../components/Toast';
import { Loader2, ChevronRight } from 'lucide-react';

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

function DashboardContent() {
  const { user, signOut, loading: authLoading } = useAuth();

  const [activeTab, setActiveTab] = useState('leads'); // 'leads' | 'scraper' | 'import' | 'settings'
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [leads, setLeads] = useState([]);
  const [backendOnline, setBackendOnline] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

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

  // If Auth is loading
  if (authLoading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-main)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem', color: 'var(--primary-lavender)' }}>
          <Loader2 size={32} className="animate-spin" />
          <span style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Connecting to Supabase Auth...</span>
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
    setLeads(prev => prev.map(l => l.id === leadId ? { ...l, Status: newStatus } : l));
    try {
      await patchLeadStatus(leadId, newStatus);
      showToast(`Lead #${leadId} status set to ${newStatus}`, 'success');
    } catch {
      showToast('Status update saved locally', 'info');
    }
  };

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

  const handleSendBulkEmail = async ({ lead_ids, subject, message, delay_ms }) => {
    try {
      const res = await sendBulkEmail({ lead_ids, subject, message, delay_ms });
      setLeads(prev => prev.map(l => lead_ids.includes(l.id) ? {
        ...l,
        Status: 'EMAIL_SENT',
        'Email Status': 'SENT',
        'Email Sent At': new Date().toISOString().replace('T', ' ').substring(0, 19)
      } : l));
      showToast(`Campaign finished! ${res.sent || lead_ids.length} emails dispatched.`, 'success');
      return res;
    } catch (err) {
      showToast(err.message || 'Bulk outreach error', 'error');
      throw err;
    }
  };

  const handleStartScraperMode = async (mode) => {
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
    <div className="app-layout">
      {/* Enterprise Left-Side Navigation Sidebar */}
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
      />

      {/* Main Content Area */}
      <div className="main-content-area">
        {/* Dynamic Top Bar Header */}
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
          onToggleMobileMenu={() => setIsMobileOpen(prev => !prev)}
        />

        <div className="content-body-wrap">
          {/* Interactive Pipeline Journey Bar */}
          <div className="workflow-pipeline-banner" role="navigation" aria-label="Lead Growth Lifecycle">
            <button
              onClick={() => setActiveTab('scraper')}
              className={`pipeline-step-item ${activeTab === 'scraper' ? 'active' : ''}`}
              title="Step 1: Automated deep web search & social harvesters"
            >
              <div className="pipeline-step-num">1</div>
              <div className="pipeline-step-meta">
                <span className="pipeline-step-title">Discover & Scrape</span>
                <span className="pipeline-step-sub">12 Public Harvesters</span>
              </div>
            </button>

            <div className="pipeline-divider">
              <ChevronRight size={14} />
            </div>

            <button
              onClick={() => setActiveTab('import')}
              className={`pipeline-step-item ${activeTab === 'import' ? 'active' : ''}`}
              title="Step 2: Parse raw job posts & WhatsApp client groups"
            >
              <div className="pipeline-step-num">2</div>
              <div className="pipeline-step-meta">
                <span className="pipeline-step-title">Import & Parse</span>
                <span className="pipeline-step-sub">WhatsApp & Raw Text</span>
              </div>
            </button>

            <div className="pipeline-divider">
              <ChevronRight size={14} />
            </div>

            <button
              onClick={() => setActiveTab('leads')}
              className={`pipeline-step-item ${activeTab === 'leads' ? 'active' : ''}`}
              title="Step 3: Review qualified leads and trigger outreach"
            >
              <div className="pipeline-step-num">3</div>
              <div className="pipeline-step-meta">
                <span className="pipeline-step-title">Qualify & Outreach</span>
                <span className="pipeline-step-sub">{leads.length} Leads Active</span>
              </div>
            </button>

            <div className="pipeline-divider">
              <ChevronRight size={14} />
            </div>

            <button
              onClick={() => setActiveTab('settings')}
              className={`pipeline-step-item ${activeTab === 'settings' ? 'active' : ''}`}
              title="Step 4: Configure company branding and Gmail SMTP"
            >
              <div className="pipeline-step-num">4</div>
              <div className="pipeline-step-meta">
                <span className="pipeline-step-title">Scale & SMTP</span>
                <span className="pipeline-step-sub">Company Signature</span>
              </div>
            </button>
          </div>

          {/* Real-time KPI Metric Summary */}
          <StatsCards leads={leads} />

          {/* TAB 1: Leads CRM & Database */}
          {activeTab === 'leads' && (
            <LeadsTable
              leads={leads}
              onSelectLeadForEmail={(lead) => setSelectedLeadForEmail(lead)}
              onSelectLeadForWhatsApp={(lead) => setSelectedLeadForWhatsApp(lead)}
              onBulkEmailOpen={(ids) => {
                setBulkEmailLeadIds(ids);
                setBulkEmailOpen(true);
              }}
              onBulkWhatsAppOpen={(ids) => {
                if (ids.length) {
                  const first = leads.find(l => l.id === ids[0]);
                  if (first) setSelectedLeadForWhatsApp(first);
                }
              }}
              onStatusChange={handleLeadStatusChange}
              onTriggerQuickScraper={() => handleStartScraperMode('quick')}
              onNavigateToScraper={() => setActiveTab('scraper')}
              onNavigateToImport={() => setActiveTab('import')}
            />
          )}

          {/* TAB 2: Live Scraper Console */}
          {activeTab === 'scraper' && (
            <ScraperConsole
              isRunning={isScraperRunning}
              logs={scraperLogs}
              onStartScraper={handleStartScraperMode}
              onStopScraper={handleStopScraper}
              onClearLogs={() => setScraperLogs([])}
              autoScroll={autoScrollLogs}
              setAutoScroll={setAutoScrollLogs}
              onNavigateToLeads={() => setActiveTab('leads')}
            />
          )}

          {/* TAB 3: Lead Importer & Extraction Engine */}
          {activeTab === 'import' && (
            <LeadImporter
              onImportSuccess={() => loadLeads(true)}
              showToast={showToast}
              onNavigateToLeads={() => setActiveTab('leads')}
            />
          )}

          {/* TAB 4: Company & SMTP Settings */}
          {activeTab === 'settings' && (
            <SettingsView
              showToast={showToast}
              onNavigateToLeads={() => setActiveTab('leads')}
            />
          )}
        </div>
      </div>

      {/* Single Email Composer Modal */}
      <SingleEmailModal
        lead={selectedLeadForEmail}
        isOpen={!!selectedLeadForEmail}
        onClose={() => setSelectedLeadForEmail(null)}
        onSend={handleSendSingleEmail}
        signature={signature}
      />

      {/* Bulk Email Outreach Modal */}
      <BulkEmailModal
        selectedLeadIds={bulkEmailLeadIds}
        leads={leads}
        isOpen={bulkEmailOpen}
        onClose={() => setBulkEmailOpen(false)}
        onBulkSend={handleSendBulkEmail}
      />

      {/* WhatsApp Outreach Modal */}
      <WhatsAppModal
        lead={selectedLeadForWhatsApp}
        isOpen={!!selectedLeadForWhatsApp}
        onClose={() => setSelectedLeadForWhatsApp(null)}
      />

      {/* Global Toast Notification Shelf */}
      <Toast toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}

export default function LeadHubPage() {
  return (
    <AuthProvider>
      <DashboardContent />
    </AuthProvider>
  );
}
