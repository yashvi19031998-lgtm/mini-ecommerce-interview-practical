'use client';

import React, { useState, useMemo } from 'react';
import { 
  Search, ExternalLink, Mail, MessageSquare, 
  ChevronLeft, ChevronRight, Download, Globe, MapPin, Phone, Copy, Check
} from 'lucide-react';

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
  globalSearch = ''
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [statusMenuOpen, setStatusMenuOpen] = useState(false);
  const [actionsMenuOpen, setActionsMenuOpen] = useState(false);
  
  // Selection
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [copiedId, setCopiedId] = useState(null);
  
  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  // Search effective
  const effectiveSearch = searchQuery || globalSearch;

  // Filtered Leads
  const filteredLeads = useMemo(() => {
    return leads.filter(item => {
      // Search text
      if (effectiveSearch.trim()) {
        const q = effectiveSearch.toLowerCase();
        const comp = String(item['Company Name'] || '').toLowerCase();
        const em = String(item.Email || '').toLowerCase();
        const loc = String(item.Address || '').toLowerCase();
        const src = String(item.Source || '').toLowerCase();
        const phone = String(item['Mobile Number'] || '').toLowerCase();
        if (!comp.includes(q) && !em.includes(q) && !loc.includes(q) && !src.includes(q) && !phone.includes(q)) {
          return false;
        }
      }

      // Status filter
      if (filterStatus === 'sent') {
        const emailStatus = String(item['Email Status'] || item.Status || '').toUpperCase();
        if (emailStatus !== 'SENT' && emailStatus !== 'EMAIL_SENT') return false;
      } else if (filterStatus === 'pending') {
        const emailStatus = String(item['Email Status'] || item.Status || '').toUpperCase();
        if (emailStatus === 'SENT' || emailStatus === 'EMAIL_SENT') return false;
      } else if (filterStatus === 'with_email') {
        const em = item.Email;
        if (!em || !em.includes('@') || em === 'N/A') return false;
      }

      return true;
    });
  }, [leads, effectiveSearch, filterStatus]);

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

  const toggleSelectOne = (id) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedIds(next);
  };

  const handleCopy = (text, id) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1800);
  };

  const allPageSelected = paginatedLeads.length > 0 && paginatedLeads.every(l => selectedIds.has(l.id));

  const filterLabels = {
    all: 'All Leads',
    sent: 'Sent Outreach',
    pending: 'Pending Outreach',
    with_email: 'Has Email'
  };

  return (
    <div className="theme-table-container">
      {/* Table Control Bar matching the theme */}
      <div className="theme-table-controls">
        {/* Search input pill */}
        <div className="theme-control-search">
          <svg width="15" height="15" viewBox="0 0 20 20" fill="none" stroke="#a3a7ae" strokeWidth="1.7">
            <circle cx="9" cy="9" r="5.2" />
            <path d="M13 13l3.2 3.2" />
          </svg>
          <input
            type="text"
            placeholder="Search leads..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setCurrentPage(1);
            }}
          />
        </div>

        {/* Status Dropdown Filter */}
        <div className="theme-pop-anchor">
          <button
            onClick={() => {
              setStatusMenuOpen(!statusMenuOpen);
              setActionsMenuOpen(false);
            }}
            className="theme-pill-btn"
          >
            <span>Status</span>
            <strong style={{ color: '#16181d', fontWeight: 600 }}>{filterLabels[filterStatus]}</strong>
          </button>

          {statusMenuOpen && (
            <div className="theme-dropdown-pop">
              {['all', 'sent', 'pending', 'with_email'].map((key) => (
                <div
                  key={key}
                  className="theme-dropdown-item"
                  onClick={() => {
                    setFilterStatus(key);
                    setStatusMenuOpen(false);
                    setCurrentPage(1);
                  }}
                >
                  <span>{filterLabels[key]}</span>
                  <span className={`theme-check-box ${filterStatus === key ? 'checked' : ''}`}>
                    {filterStatus === key ? '✓' : ''}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ flex: 1 }}></div>

        {/* Action: Quick Outreach Buttons */}
        <button
          onClick={onTriggerQuickScraper}
          className="theme-pill-btn primary"
        >
          + Quick Scraper
        </button>

        {/* Actions Dropdown */}
        <div className="theme-pop-anchor">
          <button
            onClick={() => {
              setActionsMenuOpen(!actionsMenuOpen);
              setStatusMenuOpen(false);
            }}
            className="theme-pill-btn neutral"
          >
            Actions
            <svg width="13" height="13" viewBox="0 0 20 20" fill="none" stroke="#5b5f67" strokeWidth="1.8">
              <path d="M6 8.5l4 4 4-4" />
            </svg>
          </button>

          {actionsMenuOpen && (
            <div className="theme-dropdown-pop right">
              <div 
                className="theme-dropdown-item" 
                onClick={() => {
                  onNavigateToImport && onNavigateToImport();
                  setActionsMenuOpen(false);
                }}
              >
                Import Leads
              </div>
              <a
                href="/api/export-csv"
                download
                className="theme-dropdown-item"
                onClick={() => setActionsMenuOpen(false)}
              >
                Export Master CSV
              </a>
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

      {/* Floating Bulk Action Bar when items selected */}
      {selectedIds.size > 0 && (
        <div className="theme-bulk-bar">
          <span className="theme-bulk-count">{selectedIds.size} selected</span>
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
            WhatsApp
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

      {/* Data Table with clean minimalist aesthetic */}
      <div className="theme-table-scroll">
        {/* Table Header Row */}
        <div className="theme-table-header-row">
          <div 
            onClick={toggleSelectAll} 
            className={`theme-checkbox ${allPageSelected ? 'checked' : ''}`}
            title="Select all on this page"
          >
            {allPageSelected ? '✓' : ''}
          </div>
          <span style={{ width: '32px', flexShrink: 0 }}></span>
          <span style={{ flex: '1 1 200px', minWidth: '180px' }}>Company & Website</span>
          <span style={{ width: '220px', flexShrink: 0 }}>Verified Email</span>
          <span style={{ width: '150px', flexShrink: 0 }}>Phone / Mobile</span>
          <span style={{ width: '120px', flexShrink: 0 }}>Status</span>
          <span style={{ width: '130px', flexShrink: 0 }}>Lead Source</span>
          <span style={{ width: '100px', flexShrink: 0, textAlign: 'right' }}>Outreach</span>
        </div>

        {/* Rows */}
        {paginatedLeads.length === 0 ? (
          <div className="theme-empty-notice">
            <span>No leads found matching current filters.</span>
          </div>
        ) : (
          paginatedLeads.map((item, idx) => {
            const isSelected = selectedIds.has(item.id);
            const email = item.Email || item.email || '';
            const hasEmail = email && email.includes('@') && email !== 'N/A';
            const phone = item['Mobile Number'] || item.mobile_number || '';
            const status = String(item['Email Status'] || item.Status || 'NEW').toUpperCase();
            const isSent = status === 'SENT' || status === 'EMAIL_SENT';
            const compName = item['Company Name'] || item.company_name || 'Anonymous Business';
            const website = item['Website URL'] || item.website || '';
            const src = item.Source || item.source || 'Scraper';

            return (
              <div 
                key={item.id || idx}
                className={`theme-table-row ${isSelected ? 'selected' : ''}`}
              >
                {/* Checkbox */}
                <div 
                  onClick={() => toggleSelectOne(item.id)} 
                  className={`theme-checkbox ${isSelected ? 'checked' : ''}`}
                >
                  {isSelected ? '✓' : ''}
                </div>

                {/* Company Initials Avatar */}
                <div className="theme-row-avatar">
                  {compName[0].toUpperCase()}
                </div>

                {/* Company Name & Canonical Website */}
                <div className="theme-col-company">
                  <div className="theme-comp-title">{compName}</div>
                  {website ? (
                    <a
                      href={website.startsWith('http') ? website : `https://${website}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="theme-comp-url"
                    >
                      <Globe size={11} />
                      <span>{website.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '')}</span>
                      <ExternalLink size={10} />
                    </a>
                  ) : (
                    <span className="theme-comp-empty">No website available</span>
                  )}
                </div>

                {/* Email Address */}
                <div className="theme-col-email">
                  {hasEmail ? (
                    <div className="theme-email-wrap">
                      <span className="theme-email-text" title={email}>{email}</span>
                      <button
                        onClick={() => handleCopy(email, `em-${item.id}`)}
                        className="theme-inline-copy"
                        title="Copy email address"
                      >
                        {copiedId === `em-${item.id}` ? <Check size={12} color="#1f7a45" /> : <Copy size={12} />}
                      </button>
                    </div>
                  ) : (
                    <span className="theme-cell-empty">—</span>
                  )}
                </div>

                {/* Mobile / Phone Number */}
                <div className="theme-col-phone">
                  {phone && phone !== 'N/A' ? (
                    <div className="theme-phone-wrap">
                      <span className="theme-phone-text">{phone}</span>
                    </div>
                  ) : (
                    <span className="theme-cell-empty">—</span>
                  )}
                </div>

                {/* Outreach Status Badge */}
                <div className="theme-col-status">
                  <span className={`theme-status-tag ${isSent ? 'sent' : 'pending'}`}>
                    {isSent ? 'Sent' : 'Pending'}
                  </span>
                </div>

                {/* Lead Source */}
                <div className="theme-col-source">
                  <span className="theme-source-badge" title={src}>
                    {src.length > 16 ? src.substring(0, 15) + '…' : src}
                  </span>
                </div>

                {/* 1-Click Outreach Action Buttons */}
                <div className="theme-col-actions">
                  {hasEmail && (
                    <button
                      onClick={() => onSelectLeadForEmail && onSelectLeadForEmail(item)}
                      className="theme-action-circle"
                      title="Send cold email via Gmail SMTP"
                    >
                      <Mail size={13} />
                    </button>
                  )}
                  {phone && phone !== 'N/A' && (
                    <button
                      onClick={() => onSelectLeadForWhatsApp && onSelectLeadForWhatsApp(item)}
                      className="theme-action-circle green"
                      title="Send WhatsApp message"
                    >
                      <MessageSquare size={13} />
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Pagination Footer matching clean theme */}
      <div className="theme-pagination-footer">
        <span className="theme-pagination-info">
          Showing {paginatedLeads.length} of {filteredLeads.length} leads
        </span>
        <div className="theme-pagination-controls">
          <button
            onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
            disabled={currentPage === 1}
            className="theme-page-btn"
          >
            <ChevronLeft size={14} />
          </button>
          <span className="theme-page-current">Page {currentPage} of {totalPages}</span>
          <button
            onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
            disabled={currentPage === totalPages}
            className="theme-page-btn"
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
