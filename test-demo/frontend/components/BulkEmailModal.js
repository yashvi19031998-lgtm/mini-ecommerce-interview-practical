'use client';

import React, { useState, useEffect } from 'react';
import { X, Mail, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';

export default function BulkEmailModal({
  selectedLeadIds = [],
  leads = [],
  isOpen,
  onClose,
  onBulkSend
}) {
  const [subject, setSubject] = useState('Partnership & Dedicated Tech Team for {company}');
  const [message, setMessage] = useState(
    `Hi {name} Team,\n\n` +
    `I came across your business {company} in {location}. Sangeeta Infotech specializes in dedicated full-stack development, modern web applications, and backend scaling.\n\n` +
    `We would love to know if your team needs extra engineering hands or specialized talent on a monthly or project engagement.\n\n` +
    `Would you be open to a 10-minute discovery call this week?`
  );
  const [delayMs, setDelayMs] = useState(1500);
  const [isSending, setIsSending] = useState(false);
  const [progress, setProgress] = useState(null);

  // Body scroll lock and Escape key listener
  useEffect(() => {
    if (!isOpen) return;

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && !isSending) {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      document.body.style.overflow = originalOverflow;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, isSending, onClose]);

  if (!isOpen) return null;

  const selectedLeads = leads.filter(l => selectedLeadIds.includes(l.id));
  const validEmailLeads = selectedLeads.filter(l => l.Email && l.Email.includes('@') && l.Email !== 'N/A');

  const handleStartCampaign = async () => {
    setIsSending(true);
    setProgress({ sent: 0, failed: 0, total: validEmailLeads.length });

    try {
      const res = await onBulkSend({
        lead_ids: validEmailLeads.map(l => l.id),
        subject,
        message,
        delay_ms: delayMs
      });
      if (res) {
        setProgress({ sent: res.sent || validEmailLeads.length, failed: res.failed || 0, total: validEmailLeads.length, done: true });
      }
    } catch {
      setProgress(p => ({ ...p, done: true }));
    } finally {
      setIsSending(false);
    }
  };

  const pct = progress && progress.total > 0 ? Math.round(((progress.sent + progress.failed) / progress.total) * 100) : 0;

  return (
    <div
      className="modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSending) {
          onClose();
        }
      }}
    >
      <div className="modal-content" role="dialog" aria-modal="true">
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <div style={{ background: 'var(--bg-lavender-light)', color: 'var(--primary-lavender)', padding: '7px', borderRadius: '8px' }}>
              <Mail size={18} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                Bulk Outreach Campaign
              </h3>
              <p style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
                Dispatching to <strong>{validEmailLeads.length}</strong> recipients with valid emails ({selectedLeadIds.length - validEmailLeads.length} skipped without email)
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isSending}
            className="modal-close-btn"
          >
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          {/* Progress Banner */}
          {progress && (
            <div className="campaign-progress-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', marginBottom: '8px' }}>
                <span style={{ fontWeight: 600, color: 'var(--primary-lavender)' }}>
                  {progress.done ? 'Campaign Finished!' : 'Dispatching Campaign...'}
                </span>
                <span style={{ color: 'var(--text-secondary)' }}>
                  {progress.sent} Sent | {progress.failed} Failed of {progress.total}
                </span>
              </div>
              <div className="progress-bar-track">
                <div
                  className="progress-bar-fill"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          )}

          {/* Subject Field */}
          <div className="form-group">
            <label className="form-label">Campaign Subject Template</label>
            <input
              type="text"
              className="form-input"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              disabled={isSending}
            />
          </div>

          {/* Delay Throttle */}
          <div className="form-group">
            <label className="form-label">
              SMTP Throttle Delay: <strong>{delayMs} ms</strong> between emails (Recommended: 1500ms to safeguard sender reputation)
            </label>
            <input
              type="range"
              min={500}
              max={5000}
              step={250}
              value={delayMs}
              onChange={(e) => setDelayMs(Number(e.target.value))}
              disabled={isSending}
              style={{ accentColor: 'var(--primary-lavender)' }}
            />
          </div>

          {/* Message Template */}
          <div className="form-group">
            <label className="form-label">Email Message Template</label>
            <textarea
              className="form-input"
              rows={7}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              disabled={isSending}
            />
          </div>
        </div>

        <div className="modal-footer">
          <button
            onClick={onClose}
            disabled={isSending}
            className="btn btn-secondary btn-sm"
          >
            {progress?.done ? 'Close' : 'Cancel'}
          </button>

          {!progress?.done && (
            <button
              onClick={handleStartCampaign}
              disabled={isSending || validEmailLeads.length === 0}
              className="btn btn-primary btn-sm"
            >
              {isSending ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  Sending Batch...
                </>
              ) : (
                <>
                  <CheckCircle2 size={14} />
                  Launch Outreach ({validEmailLeads.length} leads)
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
