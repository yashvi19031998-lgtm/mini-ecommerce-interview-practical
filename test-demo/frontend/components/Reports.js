'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  LayoutDashboard,
  BellRing,
  Cpu,
  Globe,
  TrendingUp,
  Send,
  ShieldAlert,
  Calendar,
  RotateCw,
  AlertCircle,
  Filter,
  UserPlus
} from 'lucide-react';
import { UntouchedPanel } from './FollowUpHistory';

import {
  fetchReportOptions,
  fetchReportSummary,
  fetchReportScrapers,
  fetchReportSources,
  fetchReportFollowups,
  fetchReportPipeline,
  fetchReportOutreach,
  fetchReportDataHealth,
  fetchReportActivity
} from '../lib/api';

import OverviewTab from './reports/OverviewTab';
import FollowupsTab from './reports/FollowupsTab';
import ScrapersTab from './reports/ScrapersTab';
import SourcesTab from './reports/SourcesTab';
import PipelineTab from './reports/PipelineTab';
import OutreachTab from './reports/OutreachTab';
import DataHealthTab from './reports/DataHealthTab';
import DailyLogTab from './reports/DailyLogTab';

// Report sections. Shown as the Reports submenu in the sidebar (Sidebar.js imports this list).
export const REPORT_SECTIONS = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'not-contacted', label: 'New Leads - Not Contacted', icon: UserPlus, noFilters: true },
  { id: 'followups', label: 'Follow-up Watchlist', icon: BellRing },
  { id: 'scrapers', label: 'Scrapers', icon: Cpu },
  { id: 'sources', label: 'Sources', icon: Globe },
  { id: 'pipeline', label: 'Pipeline', icon: TrendingUp },
  { id: 'outreach', label: 'Outreach', icon: Send },
  { id: 'data-health', label: 'Data Health', icon: ShieldAlert, noFilters: true },
  { id: 'daily-log', label: 'Daily Log', icon: Calendar, noFilters: true },
];
const TABS = REPORT_SECTIONS;

// section / onSectionChange: when given (sidebar submenu), the sidebar picks the section and the tab bar is hidden.
export default function Reports({ onOpenLeads, onOpenFollowups, onOpenScraper, section = null, onSectionChange = null }) {
  // Load saved active tab or default to 'overview'
  const [ownTab, setActiveTab] = useState(() => {
    try {
      return localStorage.getItem('reports_active_tab') || 'overview';
    } catch {
      return 'overview';
    }
  });

  // Filter state
  const [filters, setFilters] = useState(() => {
    try {
      const saved = localStorage.getItem('reports_filters');
      if (saved) {
        return JSON.parse(saved);
      }
    } catch {}
    return {
      preset: '30d',
      date_from: '',
      date_to: '',
      source: 'all',
      status: 'all',
    };
  });

  // Available options
  const [options, setOptions] = useState({
    presets: [
      { id: 'today', label: 'Today' },
      { id: 'yesterday', label: 'Yesterday' },
      { id: '7d', label: 'Last 7 Days' },
      { id: '30d', label: 'Last 30 Days' },
      { id: 'this_month', label: 'This Month' },
      { id: 'last_month', label: 'Last Month' },
      { id: 'all', label: 'All Time' },
    ],
    source_families: [],
    statuses: ['NEW', 'CONTACTED', 'EMAIL_SENT', 'REPLIED', 'MEETING', 'WON', 'LOST', 'DISQUALIFIED'],
  });

  // Tab Data States
  const [summaryData, setSummaryData] = useState(null);
  const [followupsData, setFollowupsData] = useState(null);
  const [scrapersData, setScrapersData] = useState(null);
  const [sourcesData, setSourcesData] = useState(null);
  const [pipelineData, setPipelineData] = useState(null);
  const [outreachData, setOutreachData] = useState(null);
  const [dataHealthData, setDataHealthData] = useState(null);
  const [dailyData, setDailyData] = useState(null);
  const [selectedDay, setSelectedDay] = useState(() => new Date().toISOString().slice(0, 10));

  // Loading & Error States
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const activeTab = section && TABS.some(t => t.id === section) ? section : ownTab;
  const current = TABS.find(t => t.id === activeTab) || TABS[0];

  // Overdue count badge
  const overdueCount = summaryData?.attention_counts?.overdue_followups || summaryData?.cards_by_id?.overdue_followups?.value || 0;

  // Persist tab changes
  const handleTabChange = (tabId) => {
    if (onSectionChange) onSectionChange(tabId);
    setActiveTab(tabId);
    try {
      localStorage.setItem('reports_active_tab', tabId);
    } catch {}
  };

  // Persist filter changes
  const updateFilters = (newFilters) => {
    setFilters((prev) => {
      const updated = { ...prev, ...newFilters };
      try {
        localStorage.setItem('reports_filters', JSON.stringify(updated));
      } catch {}
      return updated;
    });
  };

  // Load options on mount
  useEffect(() => {
    let mounted = true;
    fetchReportOptions()
      .then((res) => {
        if (mounted && res) {
          setOptions((prev) => ({
            ...prev,
            presets: res.presets || prev.presets,
            source_families: res.source_families || [],
            statuses: res.statuses || prev.statuses,
          }));
        }
      })
      .catch((err) => {
        console.warn('Failed to load report options:', err);
      });
    return () => {
      mounted = false;
    };
  }, []);

  // Fetch data for the active tab
  const loadActiveTabData = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      switch (activeTab) {
        case 'overview': {
          const res = await fetchReportSummary(filters);
          setSummaryData(res);
          break;
        }
        case 'followups': {
          const res = await fetchReportFollowups(filters);
          setFollowupsData(res);
          break;
        }
        case 'scrapers': {
          const res = await fetchReportScrapers(filters);
          setScrapersData(res);
          break;
        }
        case 'sources': {
          const res = await fetchReportSources(filters);
          setSourcesData(res);
          break;
        }
        case 'pipeline': {
          const res = await fetchReportPipeline(filters);
          setPipelineData(res);
          break;
        }
        case 'outreach': {
          const res = await fetchReportOutreach(filters);
          setOutreachData(res);
          break;
        }
        case 'data-health': {
          const res = await fetchReportDataHealth();
          setDataHealthData(res);
          break;
        }
        case 'daily-log': {
          const res = await fetchReportActivity(selectedDay);
          setDailyData(res);
          break;
        }
        default:
          break;
      }
    } catch (err) {
      console.error(`Error loading report tab [${activeTab}]:`, err);
      setError(err.message || 'Failed to load report data. Please check connection and retry.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [activeTab, filters, selectedDay]);

  // Trigger data load when activeTab or filters change
  useEffect(() => {
    loadActiveTabData(false);
  }, [loadActiveTabData]);

  // Initial summary load to populate overdue badge if not starting on overview
  useEffect(() => {
    if (activeTab !== 'overview' && !summaryData) {
      fetchReportSummary(filters)
        .then((res) => {
          setSummaryData(res);
          // If overdue leads exist and user has not set an explicit active tab, auto-open followups
          try {
            const explicitlySaved = localStorage.getItem('reports_active_tab');
            if (!section && !explicitlySaved && (res?.attention_counts?.overdue_followups > 0 || res?.cards_by_id?.overdue_followups?.value > 0)) {
              setActiveTab('followups');
            }
          } catch {}
        })
        .catch(() => {});
    }
  }, []);

  // Handle Preset Change
  const handlePresetChange = (presetId) => {
    if (presetId === 'custom') {
      updateFilters({ preset: '' });
    } else {
      updateFilters({ preset: presetId, date_from: '', date_to: '' });
    }
  };

  return (
    <div className="rp-container">
      {/* Page Title & Subtitle */}
      <div className="rp-page-header">
        <div className="rp-page-header-text">
          <h1 className="rp-page-title">{section ? `Reports - ${current.label}` : 'Executive Reports & Analytics'}</h1>
          <p className="rp-page-subtitle">
            Lead generation pipeline health, scraper reliability, outreach performance, and follow-up tracking.
          </p>
        </div>
        <div className="rp-page-header-actions">
          <button
            type="button"
            className="rp-btn rp-btn-secondary"
            onClick={() => loadActiveTabData(true)}
            disabled={loading || refreshing}
            title="Refresh current report"
          >
            <RotateCw size={14} className={refreshing ? 'rp-spin' : ''} />
            <span>{refreshing ? 'Refreshing...' : 'Refresh'}</span>
          </button>
        </div>
      </div>

      {/* Filter Control Bar (hidden for sections that do not use the period / source / stage filters) */}
      {!current.noFilters && (
      <div className="rp-filter-bar">
        {/* Preset Selector */}
        <div className="rp-filter-group">
          <label className="rp-filter-label" htmlFor="rp-preset-select">
            <Filter size={12} />
            <span>Period:</span>
          </label>
          <select
            id="rp-preset-select"
            className="rp-select"
            value={filters.preset || (filters.date_from ? 'custom' : '30d')}
            onChange={(e) => handlePresetChange(e.target.value)}
          >
            {options.presets.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
            <option value="custom">Custom Date Range...</option>
          </select>
        </div>

        {/* Custom Date Pickers (if custom or preset cleared) */}
        {(!filters.preset || filters.preset === 'custom') && (
          <div className="rp-filter-group rp-date-range-group">
            <label className="rp-filter-label" htmlFor="rp-date-from">From:</label>
            <input
              id="rp-date-from"
              type="date"
              className="rp-input-date"
              value={filters.date_from || ''}
              onChange={(e) => updateFilters({ preset: '', date_from: e.target.value })}
            />
            <label className="rp-filter-label" htmlFor="rp-date-to">To:</label>
            <input
              id="rp-date-to"
              type="date"
              className="rp-input-date"
              value={filters.date_to || ''}
              onChange={(e) => updateFilters({ preset: '', date_to: e.target.value })}
            />
          </div>
        )}

        {/* Source Dropdown */}
        <div className="rp-filter-group">
          <label className="rp-filter-label" htmlFor="rp-source-select">Source:</label>
          <select
            id="rp-source-select"
            className="rp-select"
            value={filters.source || 'all'}
            onChange={(e) => updateFilters({ source: e.target.value })}
          >
            <option value="all">All Sources</option>
            {options.source_families.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        {/* Status Dropdown */}
        <div className="rp-filter-group">
          <label className="rp-filter-label" htmlFor="rp-status-select">Stage:</label>
          <select
            id="rp-status-select"
            className="rp-select"
            value={filters.status || 'all'}
            onChange={(e) => updateFilters({ status: e.target.value })}
          >
            <option value="all">All Stages</option>
            {options.statuses.map((st) => (
              <option key={st} value={st}>
                {st}
              </option>
            ))}
          </select>
        </div>
      </div>
      )}

      {/* Tabs Navigation Bar (only when the sidebar submenu is not driving the section) */}
      {!section && (
      <div className="rp-tabs-nav" role="tablist" aria-label="Report sections">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          const isFollowups = tab.id === 'followups';

          return (
            <button
              key={tab.id}
              role="tab"
              aria-selected={isActive}
              aria-controls={`rp-panel-${tab.id}`}
              id={`rp-tab-${tab.id}`}
              className={`rp-tab-btn ${isActive ? 'rp-tab-btn-active' : ''}`}
              onClick={() => handleTabChange(tab.id)}
            >
              <Icon size={16} />
              <span>{tab.label}</span>
              {isFollowups && overdueCount > 0 && (
                <span className="rp-tab-badge-alert" title={`${overdueCount} overdue follow-up items`}>
                  {overdueCount}
                </span>
              )}
            </button>
          );
        })}
      </div>
      )}

      {/* Error Alert */}
      {error && (
        <div className="jp-alert jp-alert-error" role="alert" style={{ marginTop: '1rem' }}>
          <AlertCircle size={18} />
          <div style={{ flex: 1 }}>
            <strong>Unable to load report:</strong> {error}
          </div>
          <button
            type="button"
            className="rp-btn rp-btn-secondary"
            onClick={() => loadActiveTabData(true)}
            style={{ marginLeft: '1rem' }}
          >
            Retry
          </button>
        </div>
      )}

      {/* Active Tab Panel */}
      <div
        id={`rp-panel-${activeTab}`}
        role="tabpanel"
        aria-labelledby={`rp-tab-${activeTab}`}
        className="rp-tab-content-wrapper"
      >
        {activeTab === 'overview' && (
          <OverviewTab
            data={summaryData}
            loading={loading}
            onSwitchTab={handleTabChange}
            onOpenLeads={onOpenLeads}
            onOpenFollowups={onOpenFollowups}
            onOpenScraper={onOpenScraper}
          />
        )}

        {activeTab === 'not-contacted' && (
          <UntouchedPanel onOpen={onOpenFollowups ? () => onOpenFollowups() : null} onNotice={(_, msg) => setError(msg)} />
        )}

        {activeTab === 'followups' && (
          <FollowupsTab
            data={followupsData}
            loading={loading}
            onOpenLeads={onOpenLeads}
            onOpenFollowups={onOpenFollowups}
          />
        )}

        {activeTab === 'scrapers' && (
          <ScrapersTab
            data={scrapersData}
            loading={loading}
            onOpenScraper={onOpenScraper}
          />
        )}

        {activeTab === 'sources' && (
          <SourcesTab
            data={sourcesData}
            loading={loading}
            onOpenLeads={onOpenLeads}
          />
        )}

        {activeTab === 'pipeline' && (
          <PipelineTab
            data={pipelineData}
            loading={loading}
            onOpenLeads={onOpenLeads}
          />
        )}

        {activeTab === 'outreach' && (
          <OutreachTab
            data={outreachData}
            loading={loading}
            onOpenFollowups={onOpenFollowups}
          />
        )}

        {activeTab === 'data-health' && (
          <DataHealthTab
            data={dataHealthData}
            loading={loading}
            onOpenLeads={onOpenLeads}
          />
        )}

        {activeTab === 'daily-log' && (
          <DailyLogTab
            data={dailyData}
            loading={loading}
            selectedDay={selectedDay}
            onDayChange={(day) => setSelectedDay(day)}
            onOpenLeads={onOpenLeads}
            onOpenScraper={onOpenScraper}
          />
        )}
      </div>
    </div>
  );
}
