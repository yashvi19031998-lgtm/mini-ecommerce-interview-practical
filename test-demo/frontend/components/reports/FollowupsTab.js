'use client';

import React, { useState, useMemo } from 'react';
import { 
  Download, ExternalLink, CalendarPlus, ShieldAlert, CheckCircle2, 
  AlertTriangle, Clock, ArrowUpDown, ChevronLeft, ChevronRight, X
} from 'lucide-react';
import { exportToCsv, formatNum, formatDateStr } from './reportUtils';
import { scheduleFollowup } from '../../lib/api';

export default function FollowupsTab({ data, onOpenLeads, onRefresh, showToast }) {
  const [activeReason, setActiveReason] = useState('all');
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [modalLead, setModalLead] = useState(null);
  const [modalDueAt, setModalDueAt] = useState('');
  const [modalNote, setModalNote] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [actionAlert, setActionAlert] = useState(null);

  const items = data?.items || [];
  const countsByReason = data?.counts_by_reason || {};
  const dncBlocked = data?.blocked_by_dnc_count || 0;

  // Filter items by selected reason chip
  const filtered = useMemo(() => {
    if (activeReason === 'all') return items;
    return items.filter(i => i.reason === activeReason);
  }, [items, activeReason]);

  // Paginated slice
  const paginated = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filtered.slice(start, start + pageSize);
  }, [filtered, page, pageSize]);

  const totalPages = Math.ceil(filtered.length / pageSize) || 1;

  const handleExport = () => {
    const cols = [
      { key: 'lead_id', label: 'Lead ID' },
      { key: 'company', label: 'Company' },
      { key: 'reason_label', label: 'Watchlist Reason' },
      { key: 'days_waiting', label: 'Days Waiting' },
      { key: 'email', label: 'Email' },
      { key: 'phone', label: 'Phone' },
      { key: 'source', label: 'Source' },
      { key: 'ai_score', label: 'AI Score' },
      { key: 'status', label: 'Status' },
      { key: 'last_contact_type', label: 'Last Contact Type' },
      { key: 'last_contact_date', label: 'Last Contact Date' },
      { key: 'next_due_date', label: 'Next Due Date' },
      { key: 'note', label: 'Scheduled Note' },
    ];
    exportToCsv(`followup_watchlist_${activeReason}`, cols, filtered);
  };

  const handleOpenScheduleModal = (item) => {
    setModalLead(item);
    // Default tomorrow at 10:00
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const yyyy = tomorrow.getFullYear();
    const mm = String(tomorrow.getMonth() + 1).padStart(2, '0');
    const dd = String(tomorrow.getDate()).padStart(2, '0');
    setModalDueAt(`${yyyy}-${mm}-${dd} 10:00`);
    setModalNote('Follow up on outreach');
  };

  const handleSubmitSchedule = async (e) => {
    e.preventDefault();
    if (!modalLead || !modalDueAt) return;
    setIsSubmitting(true);
    try {
      const res = await scheduleFollowup({
        lead_id: modalLead.lead_id,
        due_at: modalDueAt,
        note: modalNote
      });
      if (res && res.success !== false) {
        setActionAlert({ type: 'success', text: `Follow-up scheduled for ${modalLead.company} on ${modalDueAt}!` });
        if (showToast) showToast('Follow-up scheduled successfully', 'success');
        setModalLead(null);
        if (onRefresh) onRefresh();
      } else {
        setActionAlert({ type: 'error', text: res.error || 'Failed scheduling follow-up' });
      }
    } catch (err) {
      setActionAlert({ type: 'error', text: err.message || 'Error scheduling follow-up' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const REASON_LABELS = {
    all: `All Attention (${items.length})`,
    overdue_followup: `Overdue (${countsByReason.overdue_followup || 0})`,
    replied_no_answer: `Replied - Needs Answer (${countsByReason.replied_no_answer || 0})`,
    due_today: `Due Today (${countsByReason.due_today || 0})`,
    sequence_due: `Sequence Due (${countsByReason.sequence_due || 0})`,
    meeting_no_next_step: `Meeting No Next Step (${countsByReason.meeting_no_next_step || 0})`,
    contacted_gone_quiet: `Contacted Gone Quiet (${countsByReason.contacted_gone_quiet || 0})`,
    hot_never_contacted: `Hot Never Contacted (${countsByReason.hot_never_contacted || 0})`,
    stale_open: `Stale Open (${countsByReason.stale_open || 0})`,
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {actionAlert && (
        <div role="status" className={`jp-alert ${actionAlert.type === 'error' ? 'jp-alert-error' : 'jp-alert-success'}`}>
          {actionAlert.type === 'error' ? <AlertTriangle size={15} /> : <CheckCircle2 size={15} />}
          <span style={{ flex: 1 }}>{actionAlert.text}</span>
          <button type="button" className="jp-alert-close" onClick={() => setActionAlert(null)}>×</button>
        </div>
      )}

      {dncBlocked > 0 && (
        <div className="jp-alert" style={{ background: 'var(--bg-subtle-2)', borderColor: 'var(--border-med)', color: 'var(--text-secondary)' }}>
          <ShieldAlert size={15} color="var(--danger-red)" />
          <span>
            <strong>{dncBlocked} leads</strong> are shielded on your Do-Not-Contact list (e.g. 8dots) and excluded from automated follow-up triggers.
          </span>
        </div>
      )}

      <div className="rp-table-card">
        {/* Top Header & Export */}
        <div className="rp-table-top">
          <div className="rp-table-title">
            <Clock size={16} color="var(--primary-blue)" />
            Follow-up Watchlist ({formatNum(filtered.length)})
            <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)', fontWeight: 500 }}>
              Zero Missed Follow-ups Engine
            </span>
          </div>

          <div className="rp-table-actions">
            <button type="button" className="theme-pill-btn neutral" onClick={handleExport} disabled={filtered.length === 0}>
              <Download size={13} /> Export CSV
            </button>
          </div>
        </div>

        {/* Reason Filter Chips */}
        <div className="rp-chip-group">
          {Object.entries(REASON_LABELS).map(([rKey, rLabel]) => (
            <button
              key={rKey}
              type="button"
              className={`rp-chip ${activeReason === rKey ? 'active' : ''}`}
              onClick={() => { setActiveReason(rKey); setPage(1); }}
            >
              {rLabel}
            </button>
          ))}
        </div>

        {/* Watchlist Table */}
        {filtered.length === 0 ? (
          <div className="rp-empty">
            <CheckCircle2 size={36} color="var(--success-green)" />
            <div className="rp-empty-title">No leads need attention under this filter</div>
            <div className="rp-empty-desc">
              All scheduled follow-ups are on track and no uncontacted hot leads are waiting.
            </div>
          </div>
        ) : (
          <div className="theme-table-scroll">
            <table className="jp-table">
              <thead>
                <tr>
                  <th>Reason</th>
                  <th>Days Waiting</th>
                  <th>Company / Contact</th>
                  <th>Source</th>
                  <th>Score</th>
                  <th>Status</th>
                  <th>Last Contact</th>
                  <th>Next Due</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {paginated.map(item => {
                  const isUrgent = ['overdue_followup', 'replied_no_answer'].includes(item.reason);
                  const isWarning = ['due_today', 'sequence_due', 'hot_never_contacted'].includes(item.reason);

                  return (
                    <tr key={item.lead_id}>
                      <td>
                        <span className={`rp-badge ${isUrgent ? 'rp-badge-danger' : (isWarning ? 'rp-badge-warning' : 'rp-badge-neutral')}`}>
                          {item.reason_label}
                        </span>
                      </td>
                      <td style={{ fontWeight: 700, color: item.days_waiting > 3 ? 'var(--danger-red)' : 'var(--text-primary)' }}>
                        {item.days_waiting > 0 ? `${item.days_waiting}d` : 'Today'}
                      </td>
                      <td>
                        <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{item.company}</div>
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                          {item.email || item.phone || 'No direct contact'}
                        </div>
                      </td>
                      <td>
                        <span className="rp-badge rp-badge-neutral">{item.source || 'Unknown'}</span>
                      </td>
                      <td>
                        <span style={{ fontWeight: 700, color: item.ai_score >= 7 ? 'var(--success-green)' : 'var(--text-secondary)' }}>
                          {item.ai_score ? `${item.ai_score}/10` : '—'}
                        </span>
                      </td>
                      <td>
                        <span className="rp-badge rp-badge-neutral">{item.status}</span>
                      </td>
                      <td style={{ fontSize: '0.74rem' }}>
                        {item.last_contact_date ? (
                          <>
                            <div style={{ fontWeight: 500 }}>{formatDateStr(item.last_contact_date)}</div>
                            <div style={{ color: 'var(--text-muted)' }}>{item.last_contact_type}</div>
                          </>
                        ) : 'Never'}
                      </td>
                      <td style={{ fontSize: '0.74rem', color: item.next_due_date ? 'var(--primary-blue)' : 'var(--text-muted)' }}>
                        {item.next_due_date ? formatDateStr(item.next_due_date) : 'None set'}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', gap: 6 }}>
                          <button
                            type="button"
                            className="theme-pill-btn neutral"
                            style={{ padding: '3px 8px', fontSize: '0.72rem' }}
                            title="Open lead in Leads Database"
                            onClick={() => onOpenLeads && onOpenLeads(item.company)}
                          >
                            <ExternalLink size={12} /> Open
                          </button>
                          <button
                            type="button"
                            className="theme-pill-btn primary"
                            style={{ padding: '3px 8px', fontSize: '0.72rem' }}
                            title="Schedule Next Follow-up"
                            onClick={() => handleOpenScheduleModal(item)}
                          >
                            <CalendarPlus size={12} /> Schedule
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Footer */}
        {filtered.length > pageSize && (
          <div className="rp-pagination">
            <span>
              Showing {((page - 1) * pageSize) + 1}–{Math.min(page * pageSize, filtered.length)} of {filtered.length} leads
            </span>
            <div style={{ display: 'flex', gap: 6 }}>
              <button 
                type="button" 
                className="theme-pill-btn neutral" 
                style={{ padding: '3px 8px' }} 
                disabled={page <= 1} 
                onClick={() => setPage(p => p - 1)}
              >
                <ChevronLeft size={13} /> Prev
              </button>
              <button 
                type="button" 
                className="theme-pill-btn neutral" 
                style={{ padding: '3px 8px' }} 
                disabled={page >= totalPages} 
                onClick={() => setPage(p => p + 1)}
              >
                Next <ChevronRight size={13} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Schedule Follow-up Modal */}
      {modalLead && (
        <div className="rp-modal-backdrop" onClick={() => !isSubmitting && setModalLead(null)}>
          <div className="rp-modal" onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <h4 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                Schedule Follow-up
              </h4>
              <button 
                type="button" 
                onClick={() => setModalLead(null)} 
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                <X size={18} />
              </button>
            </div>

            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              For <strong>{modalLead.company}</strong> ({modalLead.email || modalLead.phone || 'No email'})
            </div>

            <form onSubmit={handleSubmitSchedule} style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
              <div className="form-group">
                <label className="form-label" style={{ fontSize: '0.75rem' }}>Due Date & Time (YYYY-MM-DD HH:MM)</label>
                <input
                  type="text"
                  className="theme-form-input"
                  value={modalDueAt}
                  onChange={e => setModalDueAt(e.target.value)}
                  placeholder="e.g. 2026-11-14 10:00"
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label" style={{ fontSize: '0.75rem' }}>Follow-up Note / Objective</label>
                <input
                  type="text"
                  className="theme-form-input"
                  value={modalNote}
                  onChange={e => setModalNote(e.target.value)}
                  placeholder="e.g. Send portfolio examples or call regarding React app"
                  required
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: '0.5rem' }}>
                <button 
                  type="button" 
                  className="theme-pill-btn neutral" 
                  onClick={() => setModalLead(null)} 
                  disabled={isSubmitting}
                >
                  Cancel
                </button>
                <button 
                  type="submit" 
                  className="theme-pill-btn primary" 
                  disabled={isSubmitting}
                >
                  {isSubmitting ? 'Saving…' : 'Save Follow-up'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

