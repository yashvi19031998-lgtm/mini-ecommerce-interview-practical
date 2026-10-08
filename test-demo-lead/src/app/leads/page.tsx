"use client";

import { useState, useEffect } from 'react';
import { Search, Filter, CheckCircle, XCircle, Mail, ExternalLink, RefreshCw } from 'lucide-react';

const STATUS_COLORS: Record<string, string> = {
  NEW: 'bg-blue-100 text-blue-800',
  REVIEWED: 'bg-yellow-100 text-yellow-800',
  APPROVED: 'bg-green-100 text-green-800',
  REJECTED: 'bg-red-100 text-red-800',
  EMAIL_SENT: 'bg-purple-100 text-purple-800',
  FAILED: 'bg-gray-100 text-gray-800',
};

const QUALITY_COLORS: Record<string, string> = {
  HIGH: 'bg-green-100 text-green-800',
  MEDIUM: 'bg-yellow-100 text-yellow-800',
  LOW: 'bg-red-100 text-red-800',
};

export default function LeadsPage() {
  const [leads, setLeads] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterQuality, setFilterQuality] = useState('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Email modal state
  const [emailModal, setEmailModal] = useState<any>(null);
  const [emailTo, setEmailTo] = useState('');
  const [emailSubject, setEmailSubject] = useState('');
  const [emailMessage, setEmailMessage] = useState('');
  const [sendingEmail, setSendingEmail] = useState(false);

  const fetchLeads = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filterStatus) params.set('status', filterStatus);
      if (filterQuality) params.set('quality', filterQuality);
      const res = await fetch(`/api/leads?${params}`);
      const data = await res.json();
      if (data.success) setLeads(data.leads || []);
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

  const openEmailModal = (lead: any) => {
    setEmailModal(lead);
    setEmailTo(lead.email || '');
    setEmailSubject(`Re: ${lead.project_title || 'Your Project'}`);
    setEmailMessage(
      `Hi ${lead.full_name || lead.company_name || 'there'},\n\n` +
      `I came across your project "${lead.project_title || 'your project'}" and I'm very interested in helping.\n\n` +
      `I have extensive experience in ${(lead.technologies || []).join(', ') || 'the required technologies'}.\n\n` +
      `Could we schedule a quick call to discuss your requirements?\n\n` +
      `Best regards`
    );
  };

  const sendEmail = async () => {
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
        alert(data.testMode ? '✅ Test mode: Email logged to console (add SMTP details in .env to send real emails)' : '✅ Email sent successfully!');
        setLeads(prev => prev.map(l => l.id === emailModal.id ? { ...l, lead_status: 'EMAIL_SENT' } : l));
        setEmailModal(null);
      } else {
        alert('❌ Failed: ' + (data.error?.message || 'Unknown error'));
      }
    } finally {
      setSendingEmail(false);
    }
  };

  const filtered = leads.filter(l => {
    if (!searchTerm) return true;
    const s = searchTerm.toLowerCase();
    return (
      (l.full_name || '').toLowerCase().includes(s) ||
      (l.company_name || '').toLowerCase().includes(s) ||
      (l.project_title || '').toLowerCase().includes(s) ||
      (l.email || '').toLowerCase().includes(s)
    );
  });

  return (
    <div>
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Leads</h1>
          <p className="text-sm text-gray-500 mt-1">{leads.length} leads from database</p>
        </div>
        <button onClick={fetchLeads} className="flex items-center gap-2 px-3 py-2 text-sm bg-white border rounded-md hover:bg-gray-50">
          <RefreshCw className="h-4 w-4" /> Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            className="pl-9 pr-4 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Search leads..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="px-3 py-2 border rounded-md text-sm focus:outline-none"
        >
          <option value="">All Statuses</option>
          <option value="NEW">New</option>
          <option value="APPROVED">Approved</option>
          <option value="REJECTED">Rejected</option>
          <option value="EMAIL_SENT">Email Sent</option>
        </select>
        <select
          value={filterQuality}
          onChange={(e) => setFilterQuality(e.target.value)}
          className="px-3 py-2 border rounded-md text-sm focus:outline-none"
        >
          <option value="">All Quality</option>
          <option value="HIGH">High</option>
          <option value="MEDIUM">Medium</option>
          <option value="LOW">Low</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-white shadow rounded-lg overflow-hidden">
        {loading ? (
          <div className="text-center py-16 text-gray-500">Loading leads from database...</div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-gray-500 font-medium">No leads found</p>
            <p className="text-sm text-gray-400 mt-1">Go to <a href="/finder" className="text-blue-600 underline">Finder</a> and click "Process URL" to start extracting leads</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Client</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Project</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Contact</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Quality</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Source</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {filtered.map((lead) => (
                  <tr key={lead.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div className="font-medium text-sm text-gray-900">{lead.full_name || '—'}</div>
                      <div className="text-xs text-gray-500">{lead.company_name || '—'}</div>
                    </td>
                    <td className="px-4 py-3 max-w-xs">
                      <div className="text-sm text-gray-900 truncate">{lead.project_title || '—'}</div>
                      <div className="text-xs text-blue-600 truncate">
                        {Array.isArray(lead.technologies) ? lead.technologies.join(', ') : lead.technologies || '—'}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-sm text-gray-900">{lead.email || <span className="text-gray-400 italic">No email</span>}</div>
                      <div className="text-xs text-gray-500">{lead.phone || '—'}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 text-xs font-semibold rounded-full ${QUALITY_COLORS[lead.lead_quality] || 'bg-gray-100 text-gray-800'}`}>
                        {lead.lead_quality || '—'}
                      </span>
                      {lead.budget && <div className="text-xs text-gray-500 mt-1">{lead.currency} {lead.budget}</div>}
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-xs text-gray-500">{lead.source_platform || '—'}</div>
                      {lead.source_url && (
                        <a href={lead.source_url} target="_blank" rel="noreferrer" className="text-xs text-blue-500 flex items-center gap-1 hover:underline mt-1">
                          <ExternalLink className="h-3 w-3" /> View
                        </a>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 text-xs font-semibold rounded-full ${STATUS_COLORS[lead.lead_status] || 'bg-gray-100 text-gray-700'}`}>
                        {lead.lead_status || 'NEW'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-1 flex-wrap">
                        {lead.lead_status === 'NEW' && (
                          <>
                            <button
                              onClick={() => updateStatus(lead.id, 'APPROVED')}
                              disabled={actionLoading === lead.id + 'APPROVED'}
                              className="flex items-center gap-1 px-2 py-1 text-xs bg-green-50 text-green-700 border border-green-200 rounded hover:bg-green-100"
                            >
                              <CheckCircle className="h-3 w-3" /> Approve
                            </button>
                            <button
                              onClick={() => updateStatus(lead.id, 'REJECTED')}
                              disabled={actionLoading === lead.id + 'REJECTED'}
                              className="flex items-center gap-1 px-2 py-1 text-xs bg-red-50 text-red-700 border border-red-200 rounded hover:bg-red-100"
                            >
                              <XCircle className="h-3 w-3" /> Reject
                            </button>
                          </>
                        )}
                        {lead.lead_status === 'APPROVED' && lead.email && (
                          <button
                            onClick={() => openEmailModal(lead)}
                            className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-50 text-blue-700 border border-blue-200 rounded hover:bg-blue-100"
                          >
                            <Mail className="h-3 w-3" /> Send Email
                          </button>
                        )}
                        {lead.lead_status === 'APPROVED' && !lead.email && (
                          <span className="text-xs text-gray-400 italic">No email available</span>
                        )}
                        {lead.lead_status === 'EMAIL_SENT' && (
                          <span className="text-xs text-purple-600 font-medium">✓ Sent</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Email Modal */}
      {emailModal && (
        <div className="fixed inset-0 z-50 bg-black bg-opacity-40 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg">
            <div className="p-5 border-b flex items-center justify-between">
              <h2 className="font-semibold text-gray-900">Send Proposal Email</h2>
              <button onClick={() => setEmailModal(null)} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">To</label>
                <input
                  type="email"
                  value={emailTo}
                  onChange={(e) => setEmailTo(e.target.value)}
                  className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Subject</label>
                <input
                  type="text"
                  value={emailSubject}
                  onChange={(e) => setEmailSubject(e.target.value)}
                  className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Message (edit before sending)</label>
                <textarea
                  rows={8}
                  value={emailMessage}
                  onChange={(e) => setEmailMessage(e.target.value)}
                  className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
                />
              </div>
            </div>
            <div className="p-5 border-t flex gap-3 justify-end">
              <button
                onClick={() => setEmailModal(null)}
                className="px-4 py-2 text-sm border rounded-md hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={sendEmail}
                disabled={sendingEmail || !emailTo}
                className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
              >
                <Mail className="h-4 w-4" />
                {sendingEmail ? 'Sending...' : 'Send Email'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
