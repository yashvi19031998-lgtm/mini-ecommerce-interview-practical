'use client';

import React, { useState } from 'react';
import { 
  Search, MessageSquare, FileText, Upload, Plus, CheckCircle2, 
  AlertTriangle, ArrowRight, Loader2, Database, Send, Sparkles
} from 'lucide-react';
import { importRawTextData, commitImportedLeads } from '../lib/api';

export default function LeadImporter({ onImportSuccess, onLeadsImported, showToast, onNavigateToLeads = null, onOpenSearchEngine = null }) {
  // Live Query Search moved to Scraping / Mining -> Search Engines (SearchEngine.js)
  const [activeMode, setActiveMode] = useState('chat'); // 'chat' | 'raw'
  const afterImport = onImportSuccess || onLeadsImported;
  
  // Raw Text
  const [rawText, setRawText] = useState('');
  
  // Chat Text
  const [chatText, setChatText] = useState('');

  // Results State
  const [isLoading, setIsLoading] = useState(false);
  const [parsedLeads, setParsedLeads] = useState([]);
  const [sendOutreachUponImport, setSendOutreachUponImport] = useState(false);
  const [isCommitting, setIsCommitting] = useState(false);

  // 2. Handle Raw Text / URLs
  const handleParseRaw = async () => {
    if (!rawText.trim()) {
      showToast('Please paste text or website URLs to parse', 'error');
      return;
    }
    setIsLoading(true);
    try {
      const res = await importRawTextData(rawText, true);
      if (res.leads) {
        setParsedLeads(res.leads);
        showToast(`Extracted ${res.leads.length} contact records!`, 'success');
      }
    } catch (err) {
      showToast(err.message || 'Failed parsing raw text', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  // 3. Handle Chat Upload or Text
  const handleParseChat = async () => {
    if (!chatText.trim()) {
      showToast('Please paste WhatsApp chat messages or load file', 'error');
      return;
    }
    setIsLoading(true);
    try {
      const res = await importRawTextData(chatText, false);
      if (res.leads) {
        setParsedLeads(res.leads);
        showToast(`Extracted ${res.leads.length} leads from chat log!`, 'success');
      }
    } catch (err) {
      showToast(err.message || 'Failed parsing chat', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  // Commit Leads to Master
  const handleCommitLeads = async () => {
    if (!parsedLeads.length) return;
    setIsCommitting(true);
    try {
      const res = await commitImportedLeads(parsedLeads, sendOutreachUponImport);
      showToast(`Successfully merged ${parsedLeads.length} leads into Master Database!`, 'success');
      setParsedLeads([]);
      if (afterImport) afterImport();
    } catch (err) {
      showToast(err.message || 'Failed saving leads', 'error');
    } finally {
      setIsCommitting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Mode Switcher Bar */}
      <div className="glass-panel" style={{ padding: '1rem 1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Lead Importer & Extraction Engine
            </h2>
            <p style={{ fontSize: '0.76rem', color: 'var(--text-secondary)' }}>
              Import custom datasets and parse WhatsApp chat logs or raw text / URLs. Live search is now in Scraping / Mining → Search Engines.
            </p>
          </div>

          <div className="importer-tab-bar">
            {onOpenSearchEngine && (
              <button
                onClick={onOpenSearchEngine}
                className="importer-tab-btn"
                title="Live Query Search moved to Scraping / Mining - Search Engines"
              >
                <Search size={15} />
                Live Search → Search Engines
              </button>
            )}
            <button
              onClick={() => setActiveMode('chat')}
              className={`importer-tab-btn ${activeMode === 'chat' ? 'active' : ''}`}
            >
              <MessageSquare size={15} />
              WhatsApp Chat Log
            </button>
            <button
              onClick={() => setActiveMode('raw')}
              className={`importer-tab-btn ${activeMode === 'raw' ? 'active' : ''}`}
            >
              <FileText size={15} />
              Raw Text / URLs
            </button>
          </div>

          {onNavigateToLeads && (
            <button
              onClick={onNavigateToLeads}
              className="btn btn-secondary btn-sm"
              style={{ marginLeft: 'auto' }}
              title="Return to qualified leads database"
            >
              <Database size={14} />
              View Leads Database
            </button>
          )}
        </div>
      </div>

      {/* Mode 2: WhatsApp Chat Log */}
      {activeMode === 'chat' && (
        <div className="glass-panel">
          <div className="form-group" style={{ marginBottom: '1.25rem' }}>
            <label className="form-label">
              Paste WhatsApp Group Chat History (or exported _chat.txt)
            </label>
            <textarea
              className="form-input"
              rows={8}
              placeholder="Paste raw conversation logs here... e.g.
[23/10/26, 10:15:30 AM] Rahul Sharma: Looking for a Python developer for automation. Email me at rahul@techventures.io or call +919820011223"
              value={chatText}
              onChange={(e) => setChatText(e.target.value)}
            />
          </div>

          <button
            onClick={handleParseChat}
            disabled={isLoading || !chatText.trim()}
            className="btn btn-primary btn-sm"
          >
            {isLoading ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                Parsing Phone Numbers & Emails...
              </>
            ) : (
              <>
                <MessageSquare size={14} />
                Extract Leads from Chat
              </>
            )}
          </button>
        </div>
      )}

      {/* Mode 3: Raw Text & URLs */}
      {activeMode === 'raw' && (
        <div className="glass-panel">
          <div className="form-group" style={{ marginBottom: '1.25rem' }}>
            <label className="form-label">
              Paste Unstructured Business Directory, Website URLs, or Raw Notes
            </label>
            <textarea
              className="form-input"
              rows={8}
              placeholder="Paste arbitrary text or URL lists...
https://example-agency.com
contact@innovatetech.com | +91 98765 43210
SleekApps Corp - Looking for Next.js engineers"
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
            />
          </div>

          <button
            onClick={handleParseRaw}
            disabled={isLoading || !rawText.trim()}
            className="btn btn-primary btn-sm"
          >
            {isLoading ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                Extracting Contacts...
              </>
            ) : (
              <>
                <FileText size={14} />
                Parse Text & Scrape URLs
              </>
            )}
          </button>
        </div>
      )}

      {/* Parsed Candidates Preview */}
      {parsedLeads.length > 0 && (
        <div className="crm-table-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1.25rem 1.5rem', borderBottom: '1px solid var(--border-light)', flexWrap: 'wrap', gap: '0.75rem', background: 'var(--bg-lavender-subtle)' }}>
            <div>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                Preview Extracted Candidates ({parsedLeads.length})
              </h3>
              <p style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
                Review candidate records before committing to the master database.
              </p>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.78rem', color: 'var(--text-primary)', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={sendOutreachUponImport}
                  onChange={(e) => setSendOutreachUponImport(e.target.checked)}
                  style={{ accentColor: 'var(--primary-lavender)' }}
                />
                Dispatch Instant Cold Email Upon Import
              </label>

              <button
                onClick={handleCommitLeads}
                disabled={isCommitting}
                className="btn btn-primary btn-sm"
              >
                {isCommitting ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    Committing to Master...
                  </>
                ) : (
                  <>
                    <Database size={14} />
                    Commit to Master Database ({parsedLeads.length})
                  </>
                )}
              </button>
            </div>
          </div>

          <div className="crm-table-responsive">
            <table className="crm-table">
              <thead>
                <tr>
                  <th>Company</th>
                  <th>Email</th>
                  <th>Phone / WhatsApp</th>
                  <th>Location</th>
                  <th>Source</th>
                  <th>Duplicate Status</th>
                </tr>
              </thead>
              <tbody>
                {parsedLeads.map((p, idx) => (
                  <tr key={idx}>
                    <td style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
                      {p.company_name || p['Company Name'] || 'Candidate'}
                    </td>
                    <td style={{ fontFamily: 'var(--font-code)', color: p.email ? 'var(--primary-lavender)' : 'var(--text-muted)' }}>
                      {p.email || p.Email || 'No Email'}
                    </td>
                    <td style={{ color: p.mobile_number ? 'var(--success)' : 'var(--text-muted)' }}>
                      {p.mobile_number || p['Mobile Number'] || 'No Phone'}
                    </td>
                    <td style={{ color: 'var(--text-secondary)' }}>
                      {p.location || p.Address || 'Remote'}
                    </td>
                    <td>
                      <span className="source-pill">
                        {p.source || p.Source || 'Harvester'}
                      </span>
                    </td>
                    <td>
                      {p.is_duplicate ? (
                        <span className="outreach-badge badge-pending">
                          <AlertTriangle size={11} /> Existing in Master
                        </span>
                      ) : (
                        <span className="outreach-badge badge-sent">
                          <CheckCircle2 size={11} /> Fresh Lead
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
