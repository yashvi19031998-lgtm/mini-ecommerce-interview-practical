'use client';

import React, { useRef, useEffect } from 'react';
import { 
  Play, Square, Terminal, RefreshCw, Trash2, Download,
  Search, MapPin, Send, Globe, MessageSquare, ShieldCheck, CheckCircle2, Database
} from 'lucide-react';

const HARVESTERS = [
  { name: 'Google Search & Deep Crawler', desc: 'Direct organic search crawl & high-intent filtering', icon: Search, file: 'scraper.py' },
  { name: 'Google Maps Places & Directory', desc: 'Local business listings, ratings & phone directories', icon: MapPin, file: 'google_maps_scraper.py' },
  { name: 'Telegram Public Freelance Groups', desc: 'Direct client project posts & developer requests', icon: Send, file: 'telegram_scraper.py' },
  { name: 'Reddit Freelance & Hiring Boards', desc: 'r/forhire, r/freelance, r/jobbit live RSS feeds', icon: MessageSquare, file: 'reddit_rss_scraper.py' },
  { name: 'B2B & Indian Business Portals', desc: 'Justdial & directory company profiles extraction', icon: Globe, file: 'b2b_portal_scraper.py' },
  { name: 'Deep Website Contact Extractor', desc: 'Crawls about/contact pages, WHOIS & social links', icon: ShieldCheck, file: 'website_contact_extractor.py' },
  { name: 'LinkedIn Public Hiring Harvester', desc: 'Public job listings and talent hunt announcements', icon: Globe, file: 'linkedin_scraper.py' },
  { name: 'DuckDuckGo Bulk Scraper', desc: 'Anonymous high-throughput search queries', icon: Search, file: 'ddgs_bulk_scraper.py' }
];

export default function ScraperConsole({
  isRunning,
  logs = [],
  onStartScraper,
  onStopScraper,
  onClearLogs,
  autoScroll = true,
  setAutoScroll,
  onNavigateToLeads = null
}) {
  const terminalEndRef = useRef(null);

  useEffect(() => {
    if (autoScroll && terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const downloadLogs = () => {
    const blob = new Blob([logs.join('\n')], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `scraper_logs_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Banner Alert when Scraper is running */}
      {isRunning && (
        <div className="scraper-alert-bar">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span className="live-dot-pulse"></span>
            <div>
              <strong style={{ color: 'var(--text-primary)', fontSize: '0.9rem' }}>Harvester Engine Active & Processing Leads</strong>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                You can browse other tabs; the scraper and deduplication normalizer run persistently in the background.
              </div>
            </div>
          </div>
          <button
            onClick={onStopScraper}
            className="btn btn-danger btn-sm"
          >
            <Square size={13} />
            Halt Process
          </button>
        </div>
      )}

      {/* Control Actions & Trigger Cards */}
      <div className="glass-panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.25rem' }}>
          <div>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Multi-Source Harvester Engine
            </h2>
            <p style={{ fontSize: '0.76rem', color: 'var(--text-secondary)' }}>
              Coordinate parallel scraping channels with atomic deduplication and automatic Supabase cloud sync.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <button
              onClick={() => onStartScraper('quick')}
              disabled={isRunning}
              className="btn btn-secondary btn-sm"
              title="Runs main keyword-based web scraper (scraper.py)"
            >
              <Play size={14} />
              Quick Search Run
            </button>

            <button
              onClick={() => onStartScraper('all')}
              disabled={isRunning}
              className="btn btn-primary btn-sm"
              title="Executes unified master runner across all 12 channels (run_all_scrapers.py)"
            >
              <Play size={14} />
              Master Run (All 12 Sources)
            </button>

            {onNavigateToLeads && (
              <button
                onClick={onNavigateToLeads}
                className="btn btn-secondary btn-sm"
                title="Open leads CRM to inspect and outreach"
              >
                <Database size={14} />
                View Leads Database
              </button>
            )}

            {isRunning ? (
              <button
                onClick={onStopScraper}
                className="btn btn-danger btn-sm"
              >
                <Square size={14} />
                Stop Engine
              </button>
            ) : null}
          </div>
        </div>

        {/* Harvesters Grid */}
        <div className="harvester-grid">
          {HARVESTERS.map((h, i) => {
            const Icon = h.icon;
            return (
              <div key={i} className="harvester-card">
                <div className="harvester-icon-box">
                  <Icon size={18} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: '0.84rem', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span>{h.name}</span>
                    <span className="harvester-ready-tag">
                      <CheckCircle2 size={11} /> Ready
                    </span>
                  </div>
                  <div style={{ fontSize: '0.73rem', color: 'var(--text-secondary)', marginTop: '3px' }}>
                    {h.desc}
                  </div>
                  <div style={{ fontSize: '0.67rem', color: 'var(--text-muted)', fontFamily: 'var(--font-code)', marginTop: '4px' }}>
                    {h.file}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Live Terminal Console */}
      <div className="console-window">
        <div className="console-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div className="console-dots">
              <span className="console-dot" style={{ background: '#C65F70' }}></span>
              <span className="console-dot" style={{ background: '#B98240' }}></span>
              <span className="console-dot" style={{ background: '#47866A' }}></span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.78rem', color: 'var(--text-secondary)', fontWeight: 600 }}>
              <Terminal size={14} />
              <span>Harvester Execution Terminal</span>
              {isRunning && (
                <span className="badge" style={{ background: 'var(--success-bg)', color: 'var(--success)', fontSize: '0.65rem', padding: '2px 6px' }}>
                  STREAMING
                </span>
              )}
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '0.74rem', color: 'var(--text-secondary)', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
                style={{ accentColor: 'var(--primary-lavender)' }}
              />
              Auto-scroll
            </label>

            <button
              onClick={onClearLogs}
              className="btn btn-secondary btn-sm"
              style={{ padding: '0.25rem 0.55rem', fontSize: '0.72rem' }}
              title="Clear Terminal Output"
            >
              <Trash2 size={12} />
              Clear
            </button>

            <button
              onClick={downloadLogs}
              className="btn btn-secondary btn-sm"
              style={{ padding: '0.25rem 0.55rem', fontSize: '0.72rem' }}
              title="Download Logs"
            >
              <Download size={12} />
              Save Log
            </button>
          </div>
        </div>

        <div className="console-body">
          {logs.length === 0 ? (
            <span style={{ color: '#8A8294' }}>
              [SYSTEM] Standby. Click "Master Run (All 12 Sources)" or "Quick Search Run" to initiate lead discovery stream.
            </span>
          ) : (
            logs.map((line, idx) => {
              let color = '#E9E3F3';
              if (line.includes('[SUCCESS]') || line.includes('completed') || line.includes('Saved')) {
                color = '#7FD1A5';
              } else if (line.includes('[ERROR]') || line.includes('Failed') || line.includes('Exception')) {
                color = '#F48B9B';
              } else if (line.includes('[WARNING]') || line.includes('Duplicate') || line.includes('Skipped')) {
                color = '#F7C475';
              } else if (line.includes('[INFO]')) {
                color = '#C4B4E8';
              }

              return (
                <div key={idx} style={{ color }}>
                  {line}
                </div>
              );
            })
          )}
          <div ref={terminalEndRef} />
        </div>
      </div>
    </div>
  );
}
