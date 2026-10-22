'use client';

import React, { useState, useMemo } from 'react';
import { 
  Search, X, ExternalLink, Mail, MessageSquare, 
  ChevronLeft, ChevronRight, CheckSquare, Square, 
  Sparkles, CheckCircle2, Clock, Globe, Download,
  MapPin, Phone, Copy, Check
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
  onNavigateToImport
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [filterOutreach, setFilterOutreach] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterContact, setFilterContact] = useState('');
  const [filterSource, setFilterSource] = useState('');
  const [filterIntent, setFilterIntent] = useState('');
  
  // Selection
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [copiedId, setCopiedId] = useState(null);
  
  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  const hasActiveFilters = Boolean(
    searchQuery.trim() || filterOutreach || filterStatus || filterContact || filterSource || filterIntent
  );

  const clearAllFilters = () => {
    setSearchQuery('');
    setFilterOutreach('');
    setFilterStatus('');
    setFilterContact('');
    setFilterSource('');
    setFilterIntent('');
    setCurrentPage(1);
  };

  // Extract unique sources for dynamic dropdown
  const uniqueSources = useMemo(() => {
    const s = new Set();
    leads.forEach(l => {
      const src = l.Source || l.source;
      if (src) s.add(src);
    });
    return Array.from(s).sort();
  }, [leads]);

  // Filtered Leads
  const filteredLeads = useMemo(() => {
    return leads.filter(item => {
      // Search text
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const comp = String(item['Company Name'] || '').toLowerCase();
        const em = String(item.Email || '').toLowerCase();
        const loc = String(item.Address || '').toLowerCase();
        const src = String(item.Source || '').toLowerCase();
        const phone = String(item['Mobile Number'] || '').toLowerCase();
        if (!comp.includes(q) && !em.includes(q) && !loc.includes(q) && !src.includes(q) && !phone.includes(q)) {
          return false;
        }
      }

      // Outreach status
      if (filterOutreach) {
        const emailStatus = String(item['Email Status'] || '').toUpperCase();
        if (filterOutreach === 'SENT' && emailStatus !== 'SENT') return false;
        if (filterOutreach === 'PENDING' && emailStatus === 'SENT') return false;
      }

      // Lead status
      if (filterStatus) {
        const status = String(item.Status || '').toUpperCase();
        if (filterStatus === 'EMAIL_SENT' && status !== 'EMAIL_SENT') return false;
        if (filterStatus === 'PENDING' && (status === 'EMAIL_SENT' || item['Email Status'] === 'SENT')) return false;
        if (filterStatus === 'NEW' && status !== 'NEW') return false;
        if (filterStatus === 'APPROVED' && status !== 'APPROVED') return false;
      }

      // Contact availability
      if (filterContact === 'has_email') {
        const em = item.Email;
        if (!em || !em.includes('@') || em === 'N/A') return false;
      } else if (filterContact === 'has_phone') {
        const ph = item['Mobile Number'];
        if (!ph || ph === 'N/A' || ph.length < 5) return false;
      } else if (filterContact === 'both') {
        const em = item.Email;
        const ph = item['Mobile Number'];
        if (!em || !em.includes('@') || !ph || ph.length < 5) return false;
      }

      // Source filter
      if (filterSource && item.Source !== filterSource) {
        return false;
      }

      // Intent filter
      if (filterIntent) {
        const intent = String(item.Intent || '').toLowerCase();
        if (filterIntent.toLowerCase() !== intent) return false;
      }

      return true;
    });
  }, [leads, searchQuery, filterOutreach, filterStatus, filterContact, filterSource, filterIntent]);

  // Paginated data
  const totalPages = Math.max(1, Math.ceil(filteredLeads.length / pageSize));
  const paginatedLeads = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredLeads.slice(start, start + pageSize);
  }, [filteredLeads, currentPage, pageSize]);

  // Selection handlers
  const handleSelectAllOnPage = () => {
    const newSet = new Set(selectedIds);
    const allSelected = paginatedLeads.every(l => newSet.has(l.id));
    if (allSelected) {
      paginatedLeads.forEach(l => newSet.delete(l.id));
    } else {
      paginatedLeads.forEach(l => newSet.add(l.id));
    }
    setSelectedIds(newSet);
  };

  const handleToggleSelect = (id) => {
    const newSet = new Set(selectedIds);
    if (newSet.has(id)) {
      newSet.delete(id);
    } else {
      newSet.add(id);
    }
    setSelectedIds(newSet);
  };

  const handleSelectAllMatching = () => {
    setSelectedIds(new Set(filteredLeads.map(l => l.id)));
  };

  const handleClearSelection = () => {
    setSelectedIds(new Set());
  };

  const handleCopyEmail = (email, id) => {
    if (!email) return;
    navigator.clipboard.writeText(email);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // Export CSV of currently filtered leads
  const exportFilteredCsv = () => {
    if (!filteredLeads.length) return;
    const headers = ["Company Name", "Website URL", "Email", "Mobile Number", "Address", "Intent", "Lead Type", "Status", "Email Status", "Email Sent At", "Source"];
    const rows = filteredLeads.map(l => headers.map(h => `"${String(l[h] || '').replace(/"/g, '""')}"`).join(","));
    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `filtered_leads_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const allPageSelected = paginatedLeads.length > 0 && paginatedLeads.every(l => selectedIds.has(l.id));

  // Count email and phone in selection
  const selectedLeadsList = leads.filter(l => selectedIds.has(l.id));
  const selectedWithEmail = selectedLeadsList.filter(l => l.Email && l.Email.includes('@')).length;
  const selectedWithPhone = selectedLeadsList.filter(l => l['Mobile Number'] && l['Mobile Number'].length > 5).length;

  return (
    <div className="crm-container">
      {/* Top Filter & Toolbar Bar */}
      <div className="crm-action-bar">
        <div className="crm-filters-left">
          {/* Search Input */}
          <div className="crm-search-wrapper">
            <Search size={15} className="crm-search-icon" />
            <input
              type="text"
              className="crm-search-input"
              placeholder="Search company, email, location..."
              value={searchQuery}
              onChange={(e) => { setSearchQuery(e.target.value); setCurrentPage(1); }}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="crm-search-clear"
                title="Clear search"
              >
                <X size={14} />
              </button>
            )}
          </div>

          {/* Outreach Status */}
          <select
            className="crm-select"
            value={filterOutreach}
            onChange={(e) => { setFilterOutreach(e.target.value); setCurrentPage(1); }}
          >
            <option value="">All Outreach (Sent & Pending)</option>
            <option value="SENT">📬 Email Sent</option>
            <option value="PENDING">⏳ Email Pending</option>
          </select>

          {/* Lead Status */}
          <select
            className="crm-select"
            value={filterStatus}
            onChange={(e) => { setFilterStatus(e.target.value); setCurrentPage(1); }}
          >
            <option value="">All Lead Statuses</option>
            <option value="NEW">Status: NEW</option>
            <option value="APPROVED">Status: APPROVED</option>
            <option value="EMAIL_SENT">Status: EMAIL_SENT</option>
          </select>

          {/* Contact Details */}
          <select
            className="crm-select"
            value={filterContact}
            onChange={(e) => { setFilterContact(e.target.value); setCurrentPage(1); }}
          >
            <option value="">All Contacts</option>
            <option value="has_email">Has Email Only ✉️</option>
            <option value="has_phone">Has WhatsApp / Phone 💬</option>
            <option value="both">Has Both Email & Phone ✨</option>
          </select>

          {/* Sources */}
          <select
            className="crm-select"
            value={filterSource}
            onChange={(e) => { setFilterSource(e.target.value); setCurrentPage(1); }}
          >
            <option value="">All Sources ({uniqueSources.length})</option>
            {uniqueSources.map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>

          {/* Intent */}
          <select
            className="crm-select"
            value={filterIntent}
            onChange={(e) => { setFilterIntent(e.target.value); setCurrentPage(1); }}
          >
            <option value="">All Intent Scores</option>
            <option value="High">High Intent</option>
            <option value="Medium">Medium Intent</option>
          </select>
        </div>

        {/* Action Buttons Right */}
        <div className="crm-actions-right">
          <button
            onClick={() => {
              const eligible = filteredLeads.filter(l => l['Mobile Number'] && l['Mobile Number'].length > 5).map(l => l.id);
              onBulkWhatsAppOpen(eligible);
            }}
            className="btn-toolbar btn-toolbar-pink"
            title="Batch WhatsApp outreach"
          >
            <MessageSquare size={14} />
            Bulk WhatsApp
          </button>

          <button
            onClick={() => {
              const eligible = filteredLeads.filter(l => l.Email && l.Email.includes('@')).map(l => l.id);
              onBulkEmailOpen(eligible);
            }}
            className="btn-toolbar btn-toolbar-lavender"
            title="Batch email outreach"
          >
            <Mail size={14} />
            Bulk Outreach Email
          </button>

          <button
            onClick={exportFilteredCsv}
            className="btn-toolbar btn-toolbar-secondary"
            title="Export filtered records as CSV"
          >
            <Download size={14} />
            Export CSV
          </button>
        </div>
      </div>

      {/* Active Filter Chips Bar */}
      {hasActiveFilters && (
        <div className="crm-active-filters">
          <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Active Filters:</span>
          {searchQuery.trim() && (
            <span className="active-filter-chip">
              Search: "{searchQuery}"
              <button onClick={() => setSearchQuery('')} className="active-filter-remove"><X size={12} /></button>
            </span>
          )}
          {filterOutreach && (
            <span className="active-filter-chip">
              Outreach: {filterOutreach}
              <button onClick={() => setFilterOutreach('')} className="active-filter-remove"><X size={12} /></button>
            </span>
          )}
          {filterStatus && (
            <span className="active-filter-chip">
              Status: {filterStatus}
              <button onClick={() => setFilterStatus('')} className="active-filter-remove"><X size={12} /></button>
            </span>
          )}
          {filterContact && (
            <span className="active-filter-chip">
              Contact: {filterContact}
              <button onClick={() => setFilterContact('')} className="active-filter-remove"><X size={12} /></button>
            </span>
          )}
          {filterSource && (
            <span className="active-filter-chip">
              Source: {filterSource}
              <button onClick={() => setFilterSource('')} className="active-filter-remove"><X size={12} /></button>
            </span>
          )}
          {filterIntent && (
            <span className="active-filter-chip">
              Intent: {filterIntent}
              <button onClick={() => setFilterIntent('')} className="active-filter-remove"><X size={12} /></button>
            </span>
          )}
          <button onClick={clearAllFilters} className="clear-all-filters-btn">
            Clear all filters
          </button>
        </div>
      )}

      {/* Bulk Selection Notification Bar */}
      {selectedIds.size > 0 && (
        <div className="crm-selection-banner">
          <div className="banner-left">
            <span className="banner-count">
              {selectedIds.size} Leads Selected
            </span>
            <span className="banner-pill">
              ✉️ {selectedWithEmail} Email | 💬 {selectedWithPhone} WhatsApp
            </span>
            <button onClick={handleSelectAllMatching} className="banner-link-btn">
              Select All {filteredLeads.length} Matching
            </button>
            <button onClick={handleClearSelection} className="banner-link-btn">
              Clear Selection
            </button>
          </div>

          <div className="banner-right">
            <button
              onClick={() => onBulkWhatsAppOpen(Array.from(selectedIds))}
              className="btn-banner-action btn-banner-pink"
            >
              <MessageSquare size={13} />
              Bulk WhatsApp ({selectedWithPhone})
            </button>
            <button
              onClick={() => onBulkEmailOpen(Array.from(selectedIds))}
              className="btn-banner-action btn-banner-lavender"
            >
              <Mail size={13} />
              Bulk Email ({selectedWithEmail})
            </button>
          </div>
        </div>
      )}

      {/* Main Table Card */}
      <div className="crm-table-card">
        <div className="crm-table-responsive">
          <table className="crm-table">
            <thead>
              <tr>
                <th style={{ width: '42px', textAlign: 'center' }}>
                  <button
                    onClick={handleSelectAllOnPage}
                    className="checkbox-btn"
                    title={allPageSelected ? "Deselect page" : "Select page"}
                  >
                    {allPageSelected ? <CheckSquare size={16} className="checked-icon" /> : <Square size={16} />}
                  </button>
                </th>
                <th>Company / Domain</th>
                <th>Contact Details (Email & Phone)</th>
                <th>Location / Region</th>
                <th>Intent & Type</th>
                <th>Lead Source</th>
                <th>Workflow Status</th>
                <th>Outreach</th>
                <th style={{ textAlign: 'right', paddingRight: '1.25rem' }}>Outreach Action</th>
              </tr>
            </thead>
            <tbody>
              {paginatedLeads.length === 0 ? (
                <tr>
                  <td colSpan={9} className="empty-table-cell">
                    <div className="empty-wrap">
                      <Search size={36} style={{ color: 'var(--text-muted)', opacity: 0.5 }} />
                      <div className="empty-title">
                        {hasActiveFilters ? 'No leads match current filter criteria' : 'No leads found in database'}
                      </div>
                      <div className="empty-sub">
                        {hasActiveFilters
                          ? 'Try clearing active search terms or category filters to expand results.'
                          : 'Launch our multi-harvester scrapers or import lead records to populate your CRM.'}
                      </div>
                      <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.75rem', flexWrap: 'wrap', justifyContent: 'center' }}>
                        {hasActiveFilters ? (
                          <button
                            onClick={clearAllFilters}
                            className="btn btn-secondary btn-sm"
                          >
                            Reset All Filters
                          </button>
                        ) : (
                          <>
                            {onNavigateToScraper && (
                              <button
                                onClick={onNavigateToScraper}
                                className="btn btn-primary btn-sm"
                              >
                                Launch Web Scraper
                              </button>
                            )}
                            {onNavigateToImport && (
                              <button
                                onClick={onNavigateToImport}
                                className="btn btn-secondary btn-sm"
                              >
                                Import Lead List
                              </button>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                  </td>
                </tr>
              ) : (
                paginatedLeads.map((item) => {
                  const isSelected = selectedIds.has(item.id);
                  const hasEmail = item.Email && item.Email.includes('@') && item.Email !== 'N/A';
                  const hasPhone = item['Mobile Number'] && item['Mobile Number'] !== 'N/A';
                  const isEmailSent = String(item['Email Status']).toUpperCase() === 'SENT' || String(item.Status).toUpperCase() === 'EMAIL_SENT';
                  const isHighIntent = String(item.Intent).toLowerCase() === 'high' || String(item.intent_score) === '10';

                  return (
                    <tr key={item.id} className={isSelected ? 'row-selected' : ''}>
                      {/* Checkbox */}
                      <td style={{ textAlign: 'center' }}>
                        <button
                          onClick={() => handleToggleSelect(item.id)}
                          className="checkbox-btn"
                        >
                          {isSelected ? <CheckSquare size={15} className="checked-icon" /> : <Square size={15} />}
                        </button>
                      </td>

                      {/* Company / Domain */}
                      <td>
                        <div className="company-cell">
                          <div className="company-name-row">
                            <span className="company-title">{item['Company Name'] || 'Unknown Business'}</span>
                            {item['Website URL'] && (
                              <a
                                href={item['Website URL'].startsWith('http') ? item['Website URL'] : `https://${item['Website URL']}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="external-link-btn"
                                title={item['Website URL']}
                              >
                                <ExternalLink size={12} />
                              </a>
                            )}
                          </div>
                          <div className="company-id-tag">ID: {item.id}</div>
                        </div>
                      </td>

                      {/* Contacts (Email & Phone) */}
                      <td>
                        <div className="contacts-cell">
                          {hasEmail ? (
                            <div className="email-line">
                              <span className="email-text">{item.Email}</span>
                              <button
                                onClick={() => handleCopyEmail(item.Email, item.id)}
                                className="copy-btn"
                                title="Copy email address"
                              >
                                {copiedId === item.id ? <Check size={11} style={{ color: 'var(--success)' }} /> : <Copy size={11} />}
                              </button>
                            </div>
                          ) : (
                            <div className="no-contact-text">No verified email</div>
                          )}

                          {hasPhone ? (
                            <div className="phone-line">
                              <Phone size={11} style={{ color: 'var(--success)' }} />
                              <span className="phone-text">{item['Mobile Number']}</span>
                            </div>
                          ) : (
                            <div className="no-contact-text">No phone number</div>
                          )}
                        </div>
                      </td>

                      {/* Location */}
                      <td>
                        <div className="location-cell">
                          <MapPin size={13} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                          <span className="location-text">{item.Address || 'India / Remote'}</span>
                        </div>
                      </td>

                      {/* Intent & Type */}
                      <td>
                        <div className="intent-cell">
                          <span className={`badge-pill ${isHighIntent ? 'badge-high-intent' : 'badge-med-intent'}`}>
                            {isHighIntent && <Sparkles size={11} />}
                            {item.Intent || 'High'} Intent
                          </span>
                          {item['Lead Type'] && (
                            <span className="lead-type-text">{item['Lead Type']}</span>
                          )}
                        </div>
                      </td>

                      {/* Source */}
                      <td>
                        <span className="source-pill" title={item.Source}>
                          <Globe size={11} />
                          {item.Source ? (item.Source.length > 20 ? item.Source.substring(0, 19) + '…' : item.Source) : 'Web Search'}
                        </span>
                      </td>

                      {/* Workflow Status Dropdown */}
                      <td>
                        <select
                          value={item.Status || 'NEW'}
                          onChange={(e) => onStatusChange(item.id, e.target.value)}
                          className="status-dropdown"
                        >
                          <option value="NEW">Status: NEW</option>
                          <option value="APPROVED">Status: APPROVED</option>
                          <option value="EMAIL_SENT">Status: EMAIL_SENT</option>
                          <option value="REJECTED">Status: REJECTED</option>
                        </select>
                      </td>

                      {/* Outreach Badge */}
                      <td>
                        {isEmailSent ? (
                          <span className="outreach-badge badge-sent" title={item['Email Sent At'] ? `Sent: ${item['Email Sent At']}` : 'Completed'}>
                            <CheckCircle2 size={11} />
                            SENT
                          </span>
                        ) : (
                          <span className="outreach-badge badge-pending">
                            <Clock size={11} />
                            PENDING
                          </span>
                        )}
                      </td>

                      {/* Actions */}
                      <td style={{ textAlign: 'right', paddingRight: '1.25rem' }}>
                        <div className="actions-cell">
                          <button
                            onClick={() => onSelectLeadForEmail(item)}
                            disabled={!hasEmail}
                            className="btn-row-action btn-row-email"
                            title={hasEmail ? "Compose outreach email" : "No email available"}
                          >
                            <Mail size={12} />
                            Email
                          </button>

                          <button
                            onClick={() => onSelectLeadForWhatsApp(item)}
                            disabled={!hasPhone}
                            className="btn-row-action btn-row-wa"
                            title={hasPhone ? "Open in WhatsApp" : "No phone available"}
                          >
                            <MessageSquare size={12} />
                            WhatsApp
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="crm-pagination-bar">
          <div className="pagination-left">
            <span>
              Showing <strong>{filteredLeads.length === 0 ? 0 : (currentPage - 1) * pageSize + 1}</strong> to{' '}
              <strong>{Math.min(currentPage * pageSize, filteredLeads.length)}</strong> of{' '}
              <strong>{filteredLeads.length.toLocaleString()}</strong> leads
            </span>
            <div className="page-size-selector">
              <span>Per page:</span>
              <select
                value={pageSize}
                onChange={(e) => { setPageSize(Number(e.target.value)); setCurrentPage(1); }}
                className="select-page-size"
              >
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </div>
          </div>

          <div className="pagination-right">
            <button
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage <= 1}
              className="btn-page-nav"
            >
              <ChevronLeft size={14} />
              Previous
            </button>

            <span className="page-counter">
              Page <strong>{currentPage}</strong> of <strong>{totalPages}</strong>
            </span>

            <button
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
              disabled={currentPage >= totalPages}
              className="btn-page-nav"
            >
              Next
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
