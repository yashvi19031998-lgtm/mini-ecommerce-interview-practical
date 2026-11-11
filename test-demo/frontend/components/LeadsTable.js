'use client';

import React, { useState, useMemo } from 'react';
import { downloadLeadsCsv } from '../lib/api';
import { 
  Search, ExternalLink, Mail, MessageSquare, 
  ChevronLeft, ChevronRight, Download, Globe, MapPin, Phone, Copy, Check,
  Sparkles, Award, DollarSign, ArrowUpRight, Flame, Zap, Filter
} from 'lucide-react';
import AILeadDossierModal from './AILeadDossierModal';

const HOT_CATEGORIES = ['client_project', 'hiring_developer', 'prospect_signal'];
const HOT_SCORE = 7;
const CATEGORY_LABELS = {
  client_project: 'Client Project',
  hiring_developer: 'Hiring Devs',
  prospect_signal: 'Prospect Signal',
  service_provider: 'Service Provider',
  job_seeker: 'Job Seeker',
  job_board_or_directory: 'Job Board',
  irrelevant: 'Not Relevant'
};

const PIPELINE_STAGES = ['NEW', 'CONTACTED', 'REPLIED', 'MEETING', 'WON', 'LOST', 'DISQUALIFIED'];

const aiScoreOf = (item) => {
  const n = parseFloat(item.ai_score);
  return Number.isFinite(n) ? n : null;
};

const isHotLead = (item) => {
  const score = aiScoreOf(item);
  return score !== null && score >= HOT_SCORE;
};

const postedAgo = (item) => {
  const stamp = item.posted_at || item.first_seen_at;
  if (!stamp) return '';
  const then = new Date(String(stamp).replace(' ', 'T'));
  if (Number.isNaN(then.getTime())) return '';
  const days = Math.floor((Date.now() - then.getTime()) / 86400000);
  if (days <= 0) return 'today';
  return days === 1 ? '1 day ago' : `${days}d ago`;
};

export default function LeadsTable({
  leads = [],
  onSelectLeadForEmail,
  onSelectLeadForWhatsApp,
  onBulkEmailOpen,
  onBulkWhatsAppOpen,
  onStatusChange,
  onTriggerQuickScraper,
  onNavigateToScraper,
  onNavigateToImport,
  globalSearch = '',
  externalFilter = null
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [actionsMenuOpen, setActionsMenuOpen] = useState(false);
  
  // Selection
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [copiedId, setCopiedId] = useState(null);
  
  // AI Dossier Drawer state
  const [dossierLead, setDossierLead] = useState(null);

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  // Sort
  const [sortByScore, setSortByScore] = useState(true);

  // Sync external filter from KPI cards if provided
  const activeFilter = externalFilter || filterStatus;

  // Search effective
  const effectiveSearch = searchQuery || globalSearch;

  // Filtered Leads
  const filteredLeads = useMemo(() => {
    const result = leads.filter(item => {
      // Search text
      if (effectiveSearch.trim()) {
        const q = effectiveSearch.toLowerCase();
        const comp = String(item['Company Name'] || item.company_name || '').toLowerCase();
        const em = String(item.Email || item.email || '').toLowerCase();
        const loc = String(item.Address || item.location || '').toLowerCase();
        const src = String(item.Source || item.source || '').toLowerCase();
        const phone = String(item['Mobile Number'] || item.mobile_number || '').toLowerCase();
        const tech = String(item.ai_tech_stack || '').toLowerCase();
        const title = String(item.decision_maker_title || '').toLowerCase();
        const ai = `${item.ai_summary || ''} ${item.ai_requirement || ''}`.toLowerCase();
        
        if (!comp.includes(q) && !em.includes(q) && !loc.includes(q) && !src.includes(q) && 
            !phone.includes(q) && !tech.includes(q) && !title.includes(q) && !ai.includes(q)) {
          return false;
        }
      }

      // Filter modes
      if (activeFilter === 'hot') {
        if (!isHotLead(item)) return false;
      } else if (activeFilter === 'senior') {
        const fit = String(item.seniority_fit || '').toLowerCase();
        if (!fit.includes('senior') && !fit.includes('lead')) return false;
      } else if (activeFilter === 'wa_ready') {
        const hasWa = item.whatsapp_status === 'READY' || (item['Mobile Number'] && item['Mobile Number'] !== 'N/A');
        if (!hasWa) return false;
      } else if (activeFilter === 'with_email') {
        const em = item.Email || item.email;
        if (!em || !em.includes('@') || em === 'N/A') return false;
      } else if (activeFilter === 'ready') {
        const hasEmail = item.Email && item.Email.includes('@') && item.Email !== 'N/A';
        const hasWa = item.whatsapp_status === 'READY' || (item['Mobile Number'] && item['Mobile Number'] !== 'N/A');
        if (!hasEmail && !hasWa) return false;
      } else if (activeFilter === 'deal_budget') {
        if (!item.deal_size_estimate && !item.ai_budget) return false;
      } else if (activeFilter === 'sent') {
        const emailStatus = String(item['Email Status'] || item.Status || '').toUpperCase();
        if (emailStatus !== 'SENT' && emailStatus !== 'EMAIL_SENT') return false;
      } else if (activeFilter === 'pending') {
        const emailStatus = String(item['Email Status'] || item.Status || '').toUpperCase();
        if (emailStatus === 'SENT' || emailStatus === 'EMAIL_SENT') return false;
      }

      return true;
    });

    if (sortByScore) {
      return [...result].sort((a, b) => (aiScoreOf(b) ?? -1) - (aiScoreOf(a) ?? -1));
    }
    return result;
  }, [leads, effectiveSearch, activeFilter, sortByScore]);

  // Pagination calculation
  const totalPages = Math.ceil(filteredLeads.length / pageSize) || 1;
  const paginatedLeads = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredLeads.slice(start, start + pageSize);
  }, [filteredLeads, currentPage, pageSize]);

  // Selection toggle
  const toggleSelectAll = () => {
    if (selectedIds.size === paginatedLeads.length && paginatedLeads.length > 0) {
      setSelectedIds(new Set());
    } else {
      const next = new Set();
      paginatedLeads.forEach(l => next.add(l.id));
      setSelectedIds(next);
    }
  };

  const toggleSelectOne = (id, e) => {
    if (e) e.stopPropagation();
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedIds(next);
  };

  const handleCopy = (text, id, e) => {
    if (e) e.stopPropagation();
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1800);
  };

  const allPageSelected = paginatedLeads.length > 0 && paginatedLeads.every(l => selectedIds.has(l.id));

  // Quick Filter Pill definitions
  const filterPills = [
    { id: 'all', label: 'All Leads', icon: null, count: leads.length },
    { id: 'hot', label: '🔥 Hot AI Leads', icon: Flame, count: leads.filter(l => isHotLead(l)).length },
    { id: 'senior', label: '💼 Senior Matches', icon: Award, count: leads.filter(l => (l.seniority_fit || '').includes('Senior')).length },
    { id: 'wa_ready', label: '📱 WhatsApp Ready', icon: MessageSquare, count: leads.filter(l => l.whatsapp_status === 'READY' || (l['Mobile Number'] && l['Mobile Number'] !== 'N/A')).length },
    { id: 'with_email', label: '✉️ Verified Emails', icon: Mail, count: leads.filter(l => l.Email && l.Email.includes('@') && l.Email !== 'N/A').length },
    { id: 'deal_budget', label: '💵 High Deal Fit', icon: DollarSign, count: leads.filter(l => l.deal_size_estimate).length },
  ];

  return (
    <div className="leadsgen-table-wrapper">
      {/* 1. LeadsGen AI Quick-Filter Pills Bar */}
      <div className="leadsgen-filter-bar">
        <div className="leadsgen-pills-scroll">
          {filterPills.map(pill => {
            const isActive = activeFilter === pill.id;
            return (
              <button
                key={pill.id}
                onClick={() => {
                  setFilterStatus(pill.id);
                  setCurrentPage(1);
                }}
                className={`leadsgen-filter-pill ${isActive ? 'active' : ''}`}
              >
                <span>{pill.label}</span>
                <span className="pill-count">{pill.count}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* 2. Search & Table Controls */}
      <div className="theme-table-controls">
        <div className="theme-control-search">
          <Search size={15} color="#8a8f98" />
          <input
            type="text"
            placeholder="Search company, tech stack, email, title..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setCurrentPage(1);
            }}
          />
        </div>

        <button
          onClick={() => {
            setSortByScore(!sortByScore);
            setCurrentPage(1);
          }}
          className={`theme-pill-btn ${sortByScore ? 'active' : ''}`}
          title="Toggle sorting by AI Score"
        >
          <Sparkles size={14} color={sortByScore ? '#2563eb' : '#8a8f98'} />
          <span>Sort: AI Score {sortByScore ? 'High → Low' : 'Default'}</span>
        </button>

        <div style={{ flex: 1 }}></div>

        <button
          onClick={onTriggerQuickScraper}
          className="theme-pill-btn primary"
        >
          <Zap size={14} />
          <span>+ Quick Scraper</span>
        </button>

        {/* Actions Dropdown */}
        <div className="theme-pop-anchor">
          <button
            onClick={() => setActionsMenuOpen(!actionsMenuOpen)}
            className="theme-pill-btn"
          >
            <span>Actions ▾</span>
          </button>

          {actionsMenuOpen && (
            <div className="theme-dropdown-pop">
              <div 
                className="theme-dropdown-item" 
                onClick={() => {
                  downloadLeadsCsv();
                  setActionsMenuOpen(false);
                }}
              >
                <Download size={13} />
                <span>Export Master CSV</span>
              </div>
              <div 
                className="theme-dropdown-item" 
                onClick={() => {
                  onNavigateToImport && onNavigateToImport();
                  setActionsMenuOpen(false);
                }}
              >
                Import Leads
              </div>
              <div 
                className="theme-dropdown-item" 
                onClick={() => {
                  onNavigateToScraper && onNavigateToScraper();
                  setActionsMenuOpen(false);
                }}
              >
                Open Scraper Console
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 3. Floating Bulk Action Bar */}
      {selectedIds.size > 0 && (
        <div className="theme-bulk-bar">
          <span className="theme-bulk-count">{selectedIds.size} leads selected</span>
          <div style={{ flex: 1 }}></div>
          <button
            onClick={() => onBulkEmailOpen && onBulkEmailOpen(Array.from(selectedIds))}
            className="theme-bulk-chip"
          >
            <Mail size={13} />
            Bulk Email
          </button>
          <button
            onClick={() => onBulkWhatsAppOpen && onBulkWhatsAppOpen(Array.from(selectedIds))}
            className="theme-bulk-chip"
          >
            <MessageSquare size={13} />
            Bulk WhatsApp
          </button>
          <button
            onClick={() => {
              selectedIds.forEach(id => onStatusChange && onStatusChange(id, 'DISQUALIFIED'));
              setSelectedIds(new Set());
            }}
            className="theme-bulk-chip danger"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* 4. LeadsGen AI Modern Table */}
      <div className="theme-table-scroll">
        <div className="leadsgen-table-header-row">
          <div 
            onClick={toggleSelectAll} 
            className={`theme-checkbox ${allPageSelected ? 'checked' : ''}`}
            title="Select all on this page"
          >
            {allPageSelected ? '✓' : ''}
          </div>
          <span style={{ width: '32px', flexShrink: 0 }}></span>
          <span style={{ flex: '1 1 240px', minWidth: '220px' }}>Company & Decision Maker</span>
          <span style={{ width: '130px', flexShrink: 0 }}>AI Fit & Seniority</span>
          <span style={{ width: '160px', flexShrink: 0 }}>Deal Size & Tech Stack</span>
          <span style={{ width: '180px', flexShrink: 0 }}>Contact Coordinates</span>
          <span style={{ width: '120px', flexShrink: 0 }}>Pipeline Stage</span>
          <span style={{ width: '130px', flexShrink: 0, textAlign: 'right' }}>Intelligence & Actions</span>
        </div>

        {paginatedLeads.length === 0 ? (
          <div className="theme-empty-notice">
            <Sparkles size={24} color="#8a8f98" />
            <span>No leads found matching current filters.</span>
          </div>
        ) : (
          paginatedLeads.map((item, idx) => {
            const isSelected = selectedIds.has(item.id);
            const compName = item['Company Name'] || item.company_name || 'Anonymous Business';
            const website = item['Website URL'] || item.website || '';
            const email = item.Email || item.email || '';
            const hasEmail = email && email.includes('@') && email !== 'N/A';
            const phone = item['Mobile Number'] || item.mobile_number || '';
            const hasPhone = phone && phone !== 'N/A';
            const status = String(item['Email Status'] || item.Status || 'NEW').toUpperCase();
            const isSent = status === 'SENT' || status === 'EMAIL_SENT';
            const score = aiScoreOf(item);
            const isHot = score !== null && score >= 7;
            const seniority = item.seniority_fit || (score >= 7 ? 'Senior / Lead' : 'Standard Web');
            const dealSize = item.deal_size_estimate || (isHot ? '$3,000 - $8,000' : '');
            const decisionTitle = item.decision_maker_title || (item.lead_type === 'Job Posting' ? 'Hiring Lead' : 'Founder / CEO');
            const linkedinUrl = item.linkedin_url || (compName ? `https://www.linkedin.com/search/results/all/?keywords=${encodeURIComponent(compName)}` : '');
            const techStack = item.ai_tech_stack ? item.ai_tech_stack.split(/[,;/|]+/).slice(0, 2).join(', ') : '';
            const pipelineStatus = String(item.Status || item.status || 'NEW').toUpperCase();
            const ago = postedAgo(item);

            return (
              <div
                key={item.id || idx}
                className={`leadsgen-table-row ${isSelected ? 'selected' : ''}`}
                onClick={() => setDossierLead(item)}
              >
                {/* Checkbox */}
                <div 
                  onClick={(e) => toggleSelectOne(item.id, e)} 
                  className={`theme-checkbox ${isSelected ? 'checked' : ''}`}
                >
                  {isSelected ? '✓' : ''}
                </div>

                {/* Avatar */}
                <div className={`leadsgen-avatar ${isHot ? 'avatar-hot' : ''}`}>
                  {compName[0]?.toUpperCase() || 'C'}
                </div>

                {/* Company & Decision Maker */}
                <div className="leadsgen-col-comp">
                  <div className="comp-name-row">
                    <span className="comp-name">{compName}</span>
                    {ago && <span className="comp-ago">{ago}</span>}
                  </div>

                  <div className="comp-meta-row">
                    {website ? (
                      <a
                        href={website.startsWith('http') ? website : `https://${website}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="comp-link"
                      >
                        <Globe size={11} />
                        <span>{website.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '')}</span>
                        <ExternalLink size={9} />
                      </a>
                    ) : (
                      <span className="text-dim text-xs">No website</span>
                    )}

                    {decisionTitle && (
                      <span className="decision-title-tag">
                        {decisionTitle}
                      </span>
                    )}
                  </div>

                  {item.ai_summary && (
                    <div className="comp-summary" title={item.ai_summary}>
                      {item.ai_summary}
                    </div>
                  )}
                </div>

                {/* AI Fit & Seniority */}
                <div className="leadsgen-col-score">
                  <div className="score-badge-row">
                    {score !== null ? (
                      <span className={`leadsgen-score-badge ${isHot ? 'hot' : 'warm'}`}>
                        {score}/10 {isHot ? '🔥' : ''}
                      </span>
                    ) : (
                      <span className="text-dim text-xs">—</span>
                    )}
                  </div>
                  <span className={`seniority-pill ${seniority.includes('Senior') ? 'senior-fit' : ''}`}>
                    {seniority}
                  </span>
                </div>

                {/* Deal Size & Tech Stack */}
                <div className="leadsgen-col-deal">
                  {dealSize ? (
                    <div className="deal-estimate-badge">
                      <DollarSign size={11} />
                      <span>{dealSize}</span>
                    </div>
                  ) : (
                    <span className="text-dim text-xs">—</span>
                  )}
                  {techStack && (
                    <div className="tech-stack-preview" title={item.ai_tech_stack}>
                      {techStack}
                    </div>
                  )}
                </div>

                {/* Contact Coordinates */}
                <div className="leadsgen-col-contact">
                  {hasEmail ? (
                    <div className="contact-item">
                      <Mail size={12} color="#2563eb" />
                      <span className="contact-text" title={email}>{email}</span>
                      <button
                        onClick={(e) => handleCopy(email, `em-${item.id}`, e)}
                        className="copy-mini-btn"
                        title="Copy email"
                      >
                        {copiedId === `em-${item.id}` ? <Check size={11} color="#10b981" /> : <Copy size={11} />}
                      </button>
                    </div>
                  ) : (
                    <span className="text-dim text-xs">No email</span>
                  )}

                  {hasPhone ? (
                    <div className="contact-item">
                      <Phone size={12} color="#059669" />
                      <span className="contact-text">{phone}</span>
                      {item.whatsapp_status === 'READY' && (
                        <span className="wa-mini-tag">WA</span>
                      )}
                    </div>
                  ) : null}
                </div>

                {/* Pipeline Stage */}
                <div className="leadsgen-col-stage" onClick={(e) => e.stopPropagation()}>
                  <select
                    value={pipelineStatus}
                    onChange={(e) => onStatusChange && onStatusChange(item.id, e.target.value)}
                    className="stage-selector"
                  >
                    {PIPELINE_STAGES.map(st => (
                      <option key={st} value={st}>{st}</option>
                    ))}
                  </select>
                </div>

                {/* Action Buttons */}
                <div className="leadsgen-col-actions" onClick={(e) => e.stopPropagation()}>
                  <button
                    onClick={() => setDossierLead(item)}
                    className="leadsgen-action-btn dossier"
                    title="Open AI Dossier"
                  >
                    <Sparkles size={13} />
                    <span>Dossier</span>
                  </button>

                  <button
                    onClick={() => onSelectLeadForEmail && onSelectLeadForEmail(item)}
                    className={`leadsgen-action-btn email ${isSent ? 'sent' : ''}`}
                    disabled={!hasEmail}
                    title={hasEmail ? 'Draft Email Outreach' : 'No email'}
                  >
                    <Mail size={13} />
                  </button>

                  <button
                    onClick={() => onSelectLeadForWhatsApp && onSelectLeadForWhatsApp(item)}
                    className="leadsgen-action-btn whatsapp"
                    disabled={!hasPhone}
                    title={hasPhone ? 'Direct WhatsApp' : 'No phone'}
                  >
                    <MessageSquare size={13} />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* 5. Pagination Footer */}
      <div className="theme-pagination-footer">
        <div className="theme-page-info">
          Showing {paginatedLeads.length > 0 ? (currentPage - 1) * pageSize + 1 : 0} - {Math.min(currentPage * pageSize, filteredLeads.length)} of {filteredLeads.length} leads
        </div>

        <div className="theme-page-controls">
          <button
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={currentPage === 1}
            className="theme-page-btn"
          >
            <ChevronLeft size={16} />
            <span>Prev</span>
          </button>

          <span className="theme-page-indicator">
            Page {currentPage} of {totalPages}
          </span>

          <button
            onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
            className="theme-page-btn"
          >
            <span>Next</span>
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      {/* AI Lead Dossier Slide-Over Modal */}
      {dossierLead && (
        <AILeadDossierModal
          lead={dossierLead}
          isOpen={true}
          onClose={() => setDossierLead(null)}
          onSendEmail={(lead) => {
            setDossierLead(null);
            onSelectLeadForEmail && onSelectLeadForEmail(lead);
          }}
          onOpenWhatsApp={(lead) => {
            setDossierLead(null);
            onSelectLeadForWhatsApp && onSelectLeadForWhatsApp(lead);
          }}
          onStatusChange={(id, newStatus) => {
            onStatusChange && onStatusChange(id, newStatus);
            setDossierLead(prev => prev ? { ...prev, Status: newStatus, status: newStatus } : null);
          }}
        />
      )}
    </div>
  );
}
