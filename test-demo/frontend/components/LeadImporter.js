'use client';

import React, { useState, useRef } from 'react';
import { 
  Search, MessageSquare, FileText, Upload, Plus, CheckCircle2, 
  AlertTriangle, ArrowRight, Loader2, Database, Send, Sparkles, FileArchive
} from 'lucide-react';
import { importRawTextData, commitImportedLeads, importChatData } from '../lib/api';

export default function LeadImporter({ onImportSuccess, onLeadsImported, showToast, onNavigateToLeads = null, onOpenSearchEngine = null }) {
  // Live Query Search moved to Scraping / Mining -> Search Engines (SearchEngine.js)
  const [activeMode, setActiveMode] = useState('chat'); // 'chat' | 'raw'
  const afterImport = onImportSuccess || onLeadsImported;
  
  // Raw Text
  const [rawText, setRawText] = useState('');
  
  // Chat Text & File
  const [chatText, setChatText] = useState('');
  const [selectedChatFile, setSelectedChatFile] = useState(null);
  const fileInputRef = useRef(null);

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
  const handleParseChat = async (fileToParse = null) => {
    const file = fileToParse || selectedChatFile;
    if (!file && !chatText.trim()) {
      showToast('Please upload a WhatsApp export file (.zip / .txt) or paste chat messages', 'error');
      return;
    }
    setIsLoading(true);
    try {
      const payload = file || chatText;
      const res = await importChatData(payload);
      if (res && res.leads) {
        setParsedLeads(res.leads);
        showToast(`Extracted ${res.leads.length} leads from WhatsApp chat! Review below before saving.`, 'success');
      } else {
        showToast('No leads found in chat', 'info');
      }
    } catch (err) {
      showToast(err.message || 'Failed parsing WhatsApp chat', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileSelect = (file) => {
    if (!file) return;
    const name = file.name.toLowerCase();
    if (!name.endsWith('.zip') && !name.endsWith('.txt')) {
      showToast('Please select a WhatsApp .zip archive or .txt file', 'error');
      return;
    }
    setSelectedChatFile(file);
    handleParseChat(file);
  };

  // Commit Leads to Master
  const handleCommitLeads = async () => {
    if (!parsedLeads.length) return;
    setIsCommitting(true);
    try {
      const res = await commitImportedLeads(parsedLeads, sendOutreachUponImport);
      const emailNote = sendOutreachUponImport ? ' (Outreach emails dispatched)' : ' (No emails sent)';
      showToast(`Successfully saved ${parsedLeads.length} leads to Master Database!${emailNote}`, 'success');
      setParsedLeads([]);
      setSelectedChatFile(null);
      setChatText('');
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
          {/* Informational Workflow Card */}
          <div style={{
            background: 'rgba(99, 102, 241, 0.05)',
            border: '1px solid rgba(99, 102, 241, 0.2)',
            borderRadius: '8px',
            padding: '12px 14px',
            marginBottom: '1.25rem',
            fontSize: '0.78rem',
            color: 'var(--text-secondary)'
          }}>
            <div style={{ fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
              <Sparkles size={14} style={{ color: 'var(--primary-lavender, #6366f1)' }} />
              <span>WhatsApp Lead Import Workflow & Email Policy</span>
            </div>
            <ul style={{ margin: 0, paddingLeft: '1.2rem', lineHeight: '1.5' }}>
              <li><strong>Step 1 (Extract & Preview):</strong> Upload your WhatsApp export or paste chat text. Contacts and project requirements are extracted and checked for duplicates. <em>Leads are shown in Preview and are NOT stored in the database yet.</em></li>
              <li><strong>Step 2 (Email Policy):</strong> By default, <strong>NO cold emails are sent</strong>. If you want to automatically email them upon import, enable the <em>&quot;Dispatch Instant Cold Email Upon Import&quot;</em> toggle in the preview banner.</li>
              <li><strong>Step 3 (Save to DB):</strong> Click <strong>&quot;Commit to Master Database&quot;</strong> to permanently store candidate leads into <code>all_leads_master.csv</code> and sync with Supabase.</li>
            </ul>
          </div>

          {/* Option A: File Upload */}
          <div className="form-group" style={{ marginBottom: '1.25rem' }}>
            <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <FileArchive size={15} style={{ color: 'var(--primary-lavender)' }} />
              Upload WhatsApp Chat Export (.zip archive or _chat.txt)
            </label>
            <div
              style={{
                border: '2px dashed var(--border-light, #cbd5e1)',
                borderRadius: '8px',
                padding: '1.25rem',
                textAlign: 'center',
                background: selectedChatFile ? 'rgba(99, 102, 241, 0.04)' : 'var(--bg-subtle, #f8fafc)',
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                type="file"
                ref={fileInputRef}
                accept=".zip,.txt"
                style={{ display: 'none' }}
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    handleFileSelect(e.target.files[0]);
                  }
                }}
              />
              <Upload size={22} style={{ color: 'var(--primary-lavender, #6366f1)', margin: '0 auto 6px', display: 'block' }} />
              {selectedChatFile ? (
                <div>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                    Selected: {selectedChatFile.name} ({Math.round(selectedChatFile.size / 1024)} KB)
                  </div>
                  <div style={{ fontSize: '0.74rem', color: 'var(--success, #16a34a)', marginTop: '3px' }}>
                    Click &quot;Extract Leads from Chat&quot; or re-click to choose another file
                  </div>
                </div>
              ) : (
                <div>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                    Click to select WhatsApp Export File (.zip or _chat.txt)
                  </div>
                  <div style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', marginTop: '3px' }}>
                    Works with WhatsApp &quot;Export Chat (Without Media)&quot; .zip archives or extracted _chat.txt files
                  </div>
                </div>
              )}
            </div>
          </div>

          <div style={{ textAlign: 'center', margin: '1rem 0', color: 'var(--text-muted)', fontSize: '0.75rem', fontWeight: 600 }}>
            ─── OR PASTE CHAT LOG TEXT ───
          </div>

          {/* Option B: Raw Textarea */}
          <div className="form-group" style={{ marginBottom: '1.25rem' }}>
            <label className="form-label">
              Paste WhatsApp Group Messages / Snippets
            </label>
            <textarea
              className="form-input"
              rows={6}
              placeholder="Paste raw conversation logs here... e.g.
[23/10/26, 10:15:30 AM] Rahul Sharma: Looking for a Python developer for automation. Email me at rahul@techventures.io or call +919820011223"
              value={chatText}
              onChange={(e) => setChatText(e.target.value)}
            />
          </div>

          <button
            onClick={() => handleParseChat()}
            disabled={isLoading || (!selectedChatFile && !chatText.trim())}
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
              <label
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '0.78rem',
                  color: sendOutreachUponImport ? 'var(--primary-lavender, #6366f1)' : 'var(--text-secondary)',
                  fontWeight: sendOutreachUponImport ? 600 : 400,
                  cursor: 'pointer',
                  background: sendOutreachUponImport ? 'rgba(99, 102, 241, 0.08)' : 'transparent',
                  padding: '4px 8px',
                  borderRadius: '6px',
                  border: sendOutreachUponImport ? '1px solid var(--primary-lavender)' : '1px solid transparent',
                  transition: 'all 0.15s ease'
                }}
                title="If checked, AI-personalized cold outreach emails will be dispatched to valid emails immediately upon saving. Leave UNCHECKED to only store leads in DB."
              >
                <input
                  type="checkbox"
                  checked={sendOutreachUponImport}
                  onChange={(e) => setSendOutreachUponImport(e.target.checked)}
                  style={{ accentColor: 'var(--primary-lavender)' }}
                />
                <span>Send Cold Outreach Email (Default: Off)</span>
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
