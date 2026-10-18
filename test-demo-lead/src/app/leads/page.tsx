'use client';

import React, { useState, useEffect } from 'react';
import { 
  RefreshCw, 
  Search, 
  ExternalLink, 
  Mail, 
  CheckCircle, 
  XCircle, 
  Filter, 
  CheckSquare, 
  Square, 
  Send, 
  Layers, 
  AlertCircle,
  Sparkles,
  Building2,
  FileCheck2,
  Clock
} from 'lucide-react';
import { getStoredSettings, formatSignature } from '@/lib/settings';

const STATUS_COLORS: Record<string, string> = {
  NEW: 'bg-yellow-100 text-yellow-800 border border-yellow-200',
  APPROVED: 'bg-green-100 text-green-800 border border-green-200',
  REJECTED: 'bg-red-100 text-red-800 border border-red-200',
  EMAIL_SENT: 'bg-purple-100 text-purple-800 border border-purple-200 font-semibold',
  FAILED: 'bg-rose-100 text-rose-800 border border-rose-200',
};

const QUALITY_COLORS: Record<string, string> = {
  HIGH: 'bg-green-100 text-green-800',
  MEDIUM: 'bg-blue-100 text-blue-800',
  LOW: 'bg-gray-100 text-gray-800',
};

export default function LeadsPage() {
  const [leads, setLeads] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterQuality, setFilterQuality] = useState('');
  const [filterHasEmail, setFilterHasEmail] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Selected lead IDs for bulk actions
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Single Email modal state
  const [emailModal, setEmailModal] = useState<any>(null);
  const [emailTo, setEmailTo] = useState('');
  const [emailSubject, setEmailSubject] = useState('');
  const [emailMessage, setEmailMessage] = useState('');
  const [sendingEmail, setSendingEmail] = useState(false);

  // Bulk Email modal state
  const [bulkEmailModalOpen, setBulkEmailModalOpen] = useState(false);
  const [bulkSubject, setBulkSubject] = useState('');
  const [bulkMessage, setBulkMessage] = useState('');
  const [bulkSending, setBulkSending] = useState(false);
  const [bulkProgress, setBulkProgress] = useState<{ current: number; total: number; sent: number; failed: number } | null>(null);
  const [bulkResultSummary, setBulkResultSummary] = useState<any | null>(null);

  const fetchLeads = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filterStatus) params.set('status', filterStatus);
      if (filterQuality) params.set('quality', filterQuality);
      const res = await fetch(`/api/leads?${params}`);
      const data = await res.json();
      if (data.success) {
        setLeads(data.leads || []);
      }
    } catch (e) {
      console.error('Failed to fetch leads:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLeads();
  }, [filterStatus, filterQuality]);

  const updateStatus = async (id: string, lead_status: string) => {
    setActionLoading(id + lead_status);
    try {
      const res = await fetch('/api/leads', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, lead_status })
      });
      const data = await res.json();
      if (data.success) {
        setLeads(prev => prev.map(l => l.id === id ? { ...l, lead_status } : l));
      }
    } finally {
      setActionLoading(null);
    }
  };

  const handleBulkStatusUpdate = async (newStatus: string) => {
    if (selectedIds.size === 0) return;
    if (!confirm(`Are you sure you want to change status to "${newStatus}" for ${selectedIds.size} selected leads?`)) return;
    
    setActionLoading('bulk-' + newStatus);
    try {
      for (const id of Array.from(selectedIds)) {
        await fetch('/api/leads', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id, lead_status: newStatus })
        });
      }
      setLeads(prev => prev.map(l => selectedIds.has(l.id) ? { ...l, lead_status: newStatus } : l));
      setSelectedIds(new Set());
    } finally {
      setActionLoading(null);
    }
  };

  // Toggle single selection
  const toggleSelectLead = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  // Toggle select all visible
  const toggleSelectAll = () => {
    const visibleWithEmail = filtered.filter(l => l.email && l.email !== 'N/A');
    if (selectedIds.size >= visibleWithEmail.length && visibleWithEmail.length > 0) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(visibleWithEmail.map(l => l.id)));
    }
  };

  // Open Single Email Modal
  const openEmailModal = (lead: any) => {
    const settings = getStoredSettings();
    const signature = formatSignature(settings);

    setEmailModal(lead);
    setEmailTo(lead.email || '');
    setEmailSubject(`Re: ${lead.project_title || lead.company_name || 'Collaboration'} - Sangeeta Infotech`);
    
    const introMsg = `Hi ${lead.full_name || lead.company_name || 'there'},\n\nI came across your business (${lead.company_name || 'your company'}) and wanted to reach out regarding your software and development requirements.\n\nAt Sangeeta Infotech, we build scalable web and mobile solutions to help businesses accelerate their growth.\n\nWould you be available for a brief 10-minute call this week?\n\n---\n${signature}`;
    
    setEmailMessage(introMsg);
  };

  const sendSingleEmail = async () => {
    if (!emailModal) return;
    setSendingEmail(true);
    try {
      const res = await fetch(`/api/leads/${emailModal.id}/send-email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ to: emailTo, subject: emailSubject, message: emailMessage })
      });
      const data = await res.json();
      if (data.success) {
        alert(data.testMode ? 'Test mode: Email logged to server console.' : 'Email sent successfully via Gmail SMTP!');
        setLeads(prev => prev.map(l => l.id === emailModal.id ? { ...l, lead_status: 'EMAIL_SENT' } : l));
        setEmailModal(null);
      } else {
        alert('Failed to send email: ' + (data.error?.message || data.error || 'Unknown error'));
      }
    } finally {
      setSendingEmail(false);
    }
  };

  // Open Bulk Email Modal
  const openBulkEmailModal = () => {
    const settings = getStoredSettings();
    const signature = formatSignature(settings);

    setBulkSubject(settings.defaultSubject);
    setBulkMessage(`${settings.defaultMessage}\n\n---\n${signature}`);
    setBulkResultSummary(null);
    setBulkProgress(null);
    setBulkEmailModalOpen(true);
  };

  const sendBulkEmail = async () => {
    const selectedLeadsList = leads.filter(l => selectedIds.has(l.id) && l.email && l.email.includes('@'));
    if (selectedLeadsList.length === 0) {
      alert('No valid leads with email selected.');
      return;
    }

    setBulkSending(true);
    setBulkProgress({ current: 0, total: selectedLeadsList.length, sent: 0, failed: 0 });

    try {
      const settings = getStoredSettings();
      const res = await fetch('/api/leads/bulk-email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          leads: selectedLeadsList,
          subject: bulkSubject,
          message: bulkMessage,
          signature: formatSignature(settings),
          delayMs: settings.delayBetweenEmailsMs || 1500
        })
      });

      const data = await res.json();
      if (data.success) {
        setBulkResultSummary(data);
        // Update statuses in local state for all successfully sent leads
        const successfulIds = new Set(
          (data.results || []).filter((r: any) => r.success).map((r: any) => r.id)
        );
        setLeads(prev => prev.map(l => successfulIds.has(l.id) ? { ...l, lead_status: 'EMAIL_SENT' } : l));
        setSelectedIds(new Set());
      } else {
        alert('Bulk send encountered an issue: ' + (data.error || 'Failed to dispatch batch'));
      }
    } catch (e: any) {
      alert('Error during bulk email process: ' + e.message);
    } finally {
      setBulkSending(false);
    }
  };

  // Filter leads
  const filtered = leads.filter(l => {
    if (filterHasEmail && (!l.email || l.email === 'N/A' || !l.email.includes('@'))) return false;
    if (!searchTerm) return true;
    const s = searchTerm.toLowerCase();
    return (
      (l.full_name || '').toLowerCase().includes(s) ||
      (l.company_name || '').toLowerCase().includes(s) ||
      (l.project_title || '').toLowerCase().includes(s) ||
      (l.email || '').toLowerCase().includes(s) ||
      (l.location || '').toLowerCase().includes(s)
    );
  });

  const selectedCount = selectedIds.size;
  const eligibleSelectedCount = leads.filter(l => selectedIds.has(l.id) && l.email && l.email.includes('@')).length;
  const visibleWithEmailCount = filtered.filter(l => l.email && l.email.includes('@')).length;

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <span>Business Leads</span>
            <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-blue-100 text-blue-800">
              {leads.length} Total
            </span>
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Review qualified leads, track outreach statuses, and dispatch single or bulk proposal emails.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchLeads}
            disabled={loading}
            className="flex items-center gap-2 px-3.5 py-2 text-sm bg-white border border-gray-300 rounded-lg hover:bg-gray-50 shadow-sm transition-colors"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin text-blue-600' : 'text-gray-500'}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Bulk Action Banner (when >= 1 lead selected) */}
      {selectedCount > 0 && (
        <div className="bg-blue-900 text-white p-4 rounded-xl shadow-md flex flex-wrap items-center justify-between gap-4 animate-fade-in">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-800 rounded-lg">
              <Layers className="h-5 w-5 text-blue-200" />
            </div>
            <div>
              <span className="font-bold text-sm">{selectedCount} Leads Selected</span>
              <span className="text-xs text-blue-200 ml-2">
                ({eligibleSelectedCount} have valid email addresses)
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={openBulkEmailModal}
              disabled={eligibleSelectedCount === 0}
              className="flex items-center gap-2 px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-bold rounded-lg shadow transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Send className="h-3.5 w-3.5" />
              Send Bulk Email ({eligibleSelectedCount})
            </button>

            <button
              onClick={() => handleBulkStatusUpdate('APPROVED')}
              disabled={!!actionLoading}
              className="flex items-center gap-1.5 px-3 py-2 bg-blue-700 hover:bg-blue-600 text-white text-xs font-medium rounded-lg transition-colors"
            >
              <CheckCircle className="h-3.5 w-3.5" />
              Approve Selected
            </button>

            <button
              onClick={() => handleBulkStatusUpdate('REJECTED')}
              disabled={!!actionLoading}
              className="flex items-center gap-1.5 px-3 py-2 bg-red-700/80 hover:bg-red-700 text-white text-xs font-medium rounded-lg transition-colors"
            >
              <XCircle className="h-3.5 w-3.5" />
              Reject Selected
            </button>

            <button
              onClick={() => setSelectedIds(new Set())}
              className="px-3 py-2 bg-blue-950 text-blue-200 hover:text-white text-xs rounded-lg transition-colors"
            >
              Clear
            </button>
          </div>
        </div>
      )}

      {/* Filter & Search Bar */}
      <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm space-y-3">
        <div className="flex flex-col md:flex-row gap-3">
          {/* Search Box */}
          <div className="relative flex-1">
            <Search className="h-4 w-4 absolute left-3 top-3 text-gray-400" />
            <input
              type="text"
              placeholder="Search by company, name, email, project, location..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Status Filter */}
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          >
            <option value="">All Statuses</option>
            <option value="NEW">Status: NEW</option>
            <option value="APPROVED">Status: APPROVED</option>
            <option value="EMAIL_SENT">Status: EMAIL SENT 📬</option>
            <option value="REJECTED">Status: REJECTED</option>
          </select>

          {/* Quality Filter */}
          <select
            value={filterQuality}
            onChange={(e) => setFilterQuality(e.target.value)}
            className="px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          >
            <option value="">All Qualities</option>
            <option value="HIGH">High Quality</option>
            <option value="MEDIUM">Medium Quality</option>
            <option value="LOW">Low Quality</option>
          </select>

          {/* Has Email Only Toggle */}
          <button
            onClick={() => setFilterHasEmail(!filterHasEmail)}
            className={`flex items-center gap-2 px-3 py-2 text-sm rounded-lg border transition-colors ${
              filterHasEmail
                ? 'bg-blue-50 border-blue-300 text-blue-700 font-medium'
                : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
            }`}
          >
            <Mail className="h-4 w-4" />
            <span>Has Email ({visibleWithEmailCount})</span>
          </button>
        </div>
      </div>

      {/* Leads Table */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-gray-500 space-y-3">
            <RefreshCw className="h-8 w-8 animate-spin mx-auto text-blue-600" />
            <p className="text-sm">Loading leads from database...</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-12 text-center text-gray-500 space-y-2">
            <Building2 className="h-10 w-10 mx-auto text-gray-300" />
            <p className="font-medium text-gray-700">No leads match your current filter.</p>
            <p className="text-xs text-gray-400">Try adjusting search query or status filter.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200 text-[11px] font-semibold text-gray-500 uppercase tracking-wider">
                  {/* Select All Checkbox */}
                  <th className="p-4 w-10">
                    <button
                      type="button"
                      onClick={toggleSelectAll}
                      className="text-gray-500 hover:text-blue-600 focus:outline-none"
                      title="Select / Deselect all visible with email"
                    >
                      {selectedCount > 0 && selectedCount >= visibleWithEmailCount && visibleWithEmailCount > 0 ? (
                        <CheckSquare className="h-4 w-4 text-blue-600" />
                      ) : (
                        <Square className="h-4 w-4" />
                      )}
                    </button>
                  </th>
                  <th className="px-4 py-3">Company / Contact</th>
                  <th className="px-4 py-3">Project / Requirement</th>
                  <th className="px-4 py-3">Email & Phone</th>
                  <th className="px-4 py-3">Quality</th>
                  <th className="px-4 py-3">Source</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 text-sm">
                {filtered.map((lead) => {
                  const isSelected = selectedIds.has(lead.id);
                  const hasEmail = lead.email && lead.email !== 'N/A' && lead.email.includes('@');

                  return (
                    <tr 
                      key={lead.id} 
                      className={`hover:bg-blue-50/40 transition-colors ${isSelected ? 'bg-blue-50/70' : ''}`}
                    >
                      {/* Checkbox */}
                      <td className="p-4">
                        <button
                          type="button"
                          onClick={() => toggleSelectLead(lead.id)}
                          className="focus:outline-none"
                        >
                          {isSelected ? (
                            <CheckSquare className="h-4 w-4 text-blue-600" />
                          ) : (
                            <Square className="h-4 w-4 text-gray-300 hover:text-gray-500" />
                          )}
                        </button>
                      </td>

                      {/* Company & Name */}
                      <td className="px-4 py-3.5">
                        <div className="font-semibold text-gray-900">
                          {lead.company_name || lead.full_name || 'Anonymous Business'}
                        </div>
                        {lead.full_name && lead.full_name !== lead.company_name && (
                          <div className="text-xs text-gray-500">
                            Contact: {lead.full_name}
                          </div>
                        )}
                        {lead.location && (
                          <div className="text-[11px] text-gray-400 mt-0.5">
                            📍 {lead.location}
                          </div>
                        )}
                      </td>

                      {/* Project / Requirement */}
                      <td className="px-4 py-3.5 max-w-xs">
                        <div className="text-xs font-medium text-gray-900 line-clamp-2" title={lead.project_description || lead.project_title}>
                          {lead.project_description || lead.project_title || 'Software / Web Development Inquiry'}
                        </div>
                        {lead.technologies && lead.technologies.length > 0 && (
                          <div className="text-[11px] text-blue-600 font-mono truncate mt-1">
                            {Array.isArray(lead.technologies) ? lead.technologies.join(', ') : lead.technologies}
                          </div>
                        )}
                      </td>

                      {/* Email & Phone */}
                      <td className="px-4 py-3.5">
                        {hasEmail ? (
                          <div className="flex items-center gap-1.5 text-xs font-medium text-gray-900">
                            <Mail className="h-3.5 w-3.5 text-blue-600 flex-shrink-0" />
                            <span className="font-mono">{lead.email}</span>
                          </div>
                        ) : (
                          <span className="text-xs text-gray-400 italic">No email found</span>
                        )}
                        {lead.phone && lead.phone !== 'N/A' && (
                          <div className="text-[11px] text-gray-500 mt-0.5 font-mono">
                            📞 {lead.phone}
                          </div>
                        )}
                      </td>

                      {/* Quality */}
                      <td className="px-4 py-3.5">
                        <span className={`px-2 py-0.5 text-xs font-semibold rounded-full ${QUALITY_COLORS[lead.lead_quality] || 'bg-gray-100 text-gray-800'}`}>
                          {lead.lead_quality || 'High'}
                        </span>
                      </td>

                      {/* Source */}
                      <td className="px-4 py-3.5">
                        <div className="text-xs text-gray-600">
                          {lead.source_platform || 'Web Scraper'}
                        </div>
                        {lead.source_url && (
                          <a
                            href={lead.source_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-[11px] text-blue-600 hover:underline flex items-center gap-1 mt-0.5"
                          >
                            <ExternalLink className="h-3 w-3" /> Link
                          </a>
                        )}
                      </td>

                      {/* Status */}
                      <td className="px-4 py-3.5">
                        <span className={`inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-full ${STATUS_COLORS[lead.lead_status] || 'bg-gray-100 text-gray-700'}`}>
                          {lead.lead_status === 'EMAIL_SENT' && <CheckCircle className="h-3 w-3 text-purple-600" />}
                          {lead.lead_status || 'NEW'}
                        </span>
                      </td>

                      {/* Actions */}
                      <td className="px-4 py-3.5 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {/* Send Single Email */}
                          {hasEmail && (
                            <button
                              onClick={() => openEmailModal(lead)}
                              className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200 rounded-md hover:bg-blue-100 transition-colors"
                              title="Send customized proposal email with Sangeeta Infotech signature"
                            >
                              <Mail className="h-3 w-3" />
                              Email
                            </button>
                          )}

                          {/* Quick Approve / Reject */}
                          {lead.lead_status === 'NEW' && (
                            <>
                              <button
                                onClick={() => updateStatus(lead.id, 'APPROVED')}
                                disabled={actionLoading === lead.id + 'APPROVED'}
                                className="p-1 text-green-600 hover:bg-green-50 rounded border border-transparent hover:border-green-200"
                                title="Approve"
                              >
                                <CheckCircle className="h-4 w-4" />
                              </button>
                              <button
                                onClick={() => updateStatus(lead.id, 'REJECTED')}
                                disabled={actionLoading === lead.id + 'REJECTED'}
                                className="p-1 text-red-500 hover:bg-red-50 rounded border border-transparent hover:border-red-200"
                                title="Reject"
                              >
                                <XCircle className="h-4 w-4" />
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Single Email Modal */}
      {emailModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 animate-fade-in">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col border border-gray-100 overflow-hidden">
            <div className="p-5 border-b border-gray-100 flex items-center justify-between bg-gray-50/80">
              <div className="flex items-center gap-2">
                <div className="p-1.5 bg-blue-600 text-white rounded-lg">
                  <Mail className="h-4 w-4" />
                </div>
                <div>
                  <h2 className="font-bold text-gray-900 text-sm">Send Proposal Email</h2>
                  <p className="text-xs text-gray-500">
                    To: {emailModal.company_name || emailModal.full_name} ({emailModal.email})
                  </p>
                </div>
              </div>
              <button 
                onClick={() => setEmailModal(null)}
                className="text-gray-400 hover:text-gray-700 text-lg font-bold p-1"
              >
                ✕
              </button>
            </div>

            <div className="p-6 overflow-y-auto space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-gray-700 mb-1">Recipient Email</label>
                <input
                  type="email"
                  value={emailTo}
                  onChange={(e) => setEmailTo(e.target.value)}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block font-semibold text-gray-700 mb-1">Email Subject</label>
                <input
                  type="text"
                  value={emailSubject}
                  onChange={(e) => setEmailSubject(e.target.value)}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block font-semibold text-gray-700 mb-1">
                  Email Message & Signature
                </label>
                <textarea
                  rows={10}
                  value={emailMessage}
                  onChange={(e) => setEmailMessage(e.target.value)}
                  className="w-full border rounded-lg p-3 text-xs font-mono bg-gray-50 focus:bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none leading-relaxed"
                />
              </div>

              <div className="p-3 rounded-lg bg-blue-50 border border-blue-200 text-blue-800 text-[11px] flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-blue-600 flex-shrink-0" />
                <span>Includes Sangeeta Infotech signature configured in your Settings page.</span>
              </div>
            </div>

            <div className="p-4 border-t border-gray-100 flex items-center justify-end gap-3 bg-gray-50/50">
              <button
                onClick={() => setEmailModal(null)}
                className="px-4 py-2 text-xs font-medium text-gray-700 border rounded-lg hover:bg-gray-100 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={sendSingleEmail}
                disabled={sendingEmail || !emailTo}
                className="flex items-center gap-2 px-5 py-2 text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors shadow disabled:opacity-50"
              >
                <Send className="h-3.5 w-3.5" />
                {sendingEmail ? 'Dispatching...' : 'Send via Gmail SMTP'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Bulk Email Modal */}
      {bulkEmailModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 animate-fade-in">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[92vh] flex flex-col border border-gray-100 overflow-hidden">
            <div className="p-5 border-b border-gray-100 flex items-center justify-between bg-blue-900 text-white">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-blue-800 text-blue-200 rounded-lg">
                  <Layers className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="font-bold text-sm">Bulk Email Dispatch</h2>
                  <p className="text-xs text-blue-200">
                    Sending personalized proposals to {eligibleSelectedCount} selected businesses
                  </p>
                </div>
              </div>
              {!bulkSending && (
                <button 
                  onClick={() => setBulkEmailModalOpen(false)}
                  className="text-blue-300 hover:text-white text-lg font-bold p-1"
                >
                  ✕
                </button>
              )}
            </div>

            <div className="p-6 overflow-y-auto space-y-4 text-xs">
              {/* Summary of batch */}
              {bulkResultSummary ? (
                <div className="space-y-4 py-2">
                  <div className="p-5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 space-y-2 text-center">
                    <CheckCircle className="h-10 w-10 text-emerald-600 mx-auto" />
                    <h3 className="font-bold text-base">Bulk Email Process Completed!</h3>
                    <p className="text-xs text-emerald-700">
                      Successfully delivered {bulkResultSummary.sent} out of {bulkResultSummary.total} emails.
                    </p>
                    {bulkResultSummary.failed > 0 && (
                      <p className="text-xs text-rose-600 font-medium">
                        ({bulkResultSummary.failed} failed due to invalid address or SMTP response)
                      </p>
                    )}
                  </div>

                  <div className="max-h-48 overflow-y-auto border rounded-lg p-3 divide-y divide-gray-100 font-mono text-[11px]">
                    {bulkResultSummary.results?.map((res: any, idx: number) => (
                      <div key={idx} className="py-1.5 flex items-center justify-between">
                        <span className="truncate max-w-xs text-gray-700">{res.email}</span>
                        {res.success ? (
                          <span className="text-emerald-600 font-bold flex items-center gap-1">
                            <CheckCircle className="h-3 w-3" /> Sent
                          </span>
                        ) : (
                          <span className="text-rose-600 flex items-center gap-1" title={res.error}>
                            <AlertCircle className="h-3 w-3" /> Failed
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ) : bulkSending ? (
                /* Live progress view */
                <div className="py-8 space-y-5 text-center">
                  <RefreshCw className="h-10 w-10 text-blue-600 animate-spin mx-auto" />
                  <div>
                    <h3 className="font-bold text-gray-900 text-sm">Dispatching Bulk Emails...</h3>
                    <p className="text-xs text-gray-500 mt-1">
                      Applying polite delay between emails to protect Gmail SMTP health.
                    </p>
                  </div>
                </div>
              ) : (
                /* Edit template view */
                <>
                  <div className="p-3 rounded-lg bg-gray-50 border border-gray-200 text-gray-600 space-y-1">
                    <div className="font-semibold text-gray-800 flex items-center gap-1.5">
                      <FileCheck2 className="h-4 w-4 text-blue-600" />
                      <span>Dynamic Tags Supported:</span>
                    </div>
                    <div className="flex gap-2 text-[11px] font-mono text-blue-700 flex-wrap">
                      <code className="bg-white px-2 py-0.5 rounded border border-gray-200">&#123;name&#125;</code>
                      <code className="bg-white px-2 py-0.5 rounded border border-gray-200">&#123;company&#125;</code>
                      <code className="bg-white px-2 py-0.5 rounded border border-gray-200">&#123;project&#125;</code>
                    </div>
                  </div>

                  <div>
                    <label className="block font-semibold text-gray-700 mb-1">Subject Template</label>
                    <input
                      type="text"
                      value={bulkSubject}
                      onChange={(e) => setBulkSubject(e.target.value)}
                      className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none font-mono"
                    />
                  </div>

                  <div>
                    <label className="block font-semibold text-gray-700 mb-1">
                      Message Body & Sangeeta Infotech Signature
                    </label>
                    <textarea
                      rows={11}
                      value={bulkMessage}
                      onChange={(e) => setBulkMessage(e.target.value)}
                      className="w-full border rounded-lg p-3 text-xs font-mono bg-gray-50 focus:bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none leading-relaxed"
                    />
                  </div>
                </>
              )}
            </div>

            <div className="p-4 border-t border-gray-100 flex items-center justify-end gap-3 bg-gray-50/50">
              {bulkResultSummary ? (
                <button
                  onClick={() => setBulkEmailModalOpen(false)}
                  className="px-5 py-2 text-xs font-bold bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Close & View Updated Leads
                </button>
              ) : (
                <>
                  <button
                    onClick={() => setBulkEmailModalOpen(false)}
                    disabled={bulkSending}
                    className="px-4 py-2 text-xs font-medium text-gray-700 border rounded-lg hover:bg-gray-100 transition-colors disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={sendBulkEmail}
                    disabled={bulkSending || eligibleSelectedCount === 0}
                    className="flex items-center gap-2 px-5 py-2 text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors shadow disabled:opacity-50"
                  >
                    <Send className="h-3.5 w-3.5" />
                    {bulkSending ? 'Sending in Progress...' : `Start Dispatch (${eligibleSelectedCount} Emails)`}
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
