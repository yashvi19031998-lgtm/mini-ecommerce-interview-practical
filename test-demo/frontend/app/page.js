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

function DashboardContent() {
  const { user, signOut, loading: authLoading } = useAuth();

  const [activeTab, setActiveTab] = useState('leads'); // 'leads' | 'scraper' | 'import' | 'settings'
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
          onToggleCollapse={() => setIsSidebarCollapsed(prev => !prev)}
          searchQuery={globalSearch}
          onSearchChange={setGlobalSearch}
        />

        <div className="theme-scrollable-content">
          <div className="theme-content-padding">
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
                globalSearch={globalSearch}
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

            {/* TAB 3: Importer & Raw Extraction */}
            {activeTab === 'import' && (
              <LeadImporter
                onLeadsImported={() => loadLeads(true)}
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

      {/* Global Toast Container */}
      <div className="toast-container">
        {toasts.map(t => (
          <Toast
            key={t.id}
            id={t.id}
            message={t.message}
            type={t.type}
            onClose={() => dismissToast(t.id)}
          />
        ))}
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
