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

  const toProgress = (job) => ({
    sent: Number(job.sent) || 0,
    notSent: (Number(job.failed) || 0) + (Number(job.not_verified) || 0) + (Number(job.skipped) || 0),
    processed: Number(job.processed) || 0,
    total: Number(job.total) || validEmailLeads.length,
    done: !!job.done,
    stopped: job.stopped_reason || '',
    results: job.results || []
  });

  const handleStartCampaign = async () => {
    setIsSending(true);
    setProgress({ sent: 0, notSent: 0, processed: 0, total: validEmailLeads.length, results: [] });

    try {
      // Runs on the server in the background: every mailbox is checked before sending, so it takes minutes.
      const res = await onBulkSend({
        lead_ids: validEmailLeads.map(l => l.id),
        subject,
        message,
        delay_ms: delayMs
      }, (job) => setProgress(toProgress(job)));
      if (res) setProgress(toProgress({ ...res, done: true }));
    } catch (err) {
      setProgress(p => ({ ...(p || {}), done: true, stopped: err.message }));
    } finally {
      setIsSending(false);
    }
  };

  const REASONS = {
    not_verified: 'Address not confirmed by its mail server',
    already_sent: 'Already e-mailed before',
    no_email: 'No e-mail address',
    excluded: 'On the do-not-contact list',
    daily_limit: 'Daily limit reached',
    stopped: 'Stopped',
    error: 'Send failed'
  };
  const reasonCounts = {};
  (progress?.results || []).filter(r => !r.success).forEach(r => {
    const label = REASONS[r.reason] || r.reason || 'Not sent';
    reasonCounts[label] = (reasonCounts[label] || 0) + 1;
  });

  const pct = progress && progress.total > 0 ? Math.round((progress.processed / progress.total) * 100) : 0;

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
            aria-label="Close (sending continues on the server)"
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
                  {progress.done ? 'Finished' : `Checking mailboxes and sending… ${progress.processed} of ${progress.total}`}
                </span>
                <span style={{ color: 'var(--text-secondary)' }}>
                  {progress.sent} sent · {progress.notSent} not sent
                </span>
              </div>
              <div className="progress-bar-track">
                <div
                  className="progress-bar-fill"
                  style={{ width: `${pct}%` }}
                />
              </div>
              {!progress.done && (
                <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                  Each address is checked with its mail server first, so this takes a few seconds per lead.
                  You can close this window; sending continues on the server.
                </div>
              )}
              {progress.stopped && (
                <div role="alert" style={{ fontSize: '0.78rem', color: 'var(--danger-red)' }}>{progress.stopped}</div>
              )}
              {Object.keys(reasonCounts).length > 0 && (
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                  {Object.entries(reasonCounts).map(([label, n]) => <li key={label}>{label}: {n}</li>)}
                </ul>
              )}
            </div>
          )}

          {/* Subject Field */}
          <div className="form-group">
            <label className="form-label">Campaign Subject Template</label>
            <input
              type="text"
              className="form-input"
              value={subject || ''}
              onChange={(e) => setSubject(e.target.value)}
              disabled={isSending}
            />
          </div>

          {/* Delay Throttle */}
          <div className="form-group">
            <label className="form-label">
              SMTP Throttle Delay: <strong>{delayMs ?? 1500} ms</strong> between emails (Recommended: 1500ms to safeguard sender reputation)
            </label>
            <input
              type="range"
              min={500}
              max={5000}
              step={250}
              value={delayMs ?? 1500}
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
              value={message || ''}
              onChange={(e) => setMessage(e.target.value)}
              disabled={isSending}
            />
          </div>
        </div>

        <div className="modal-footer">
          <button
            onClick={onClose}
            className="btn btn-secondary btn-sm"
          >
            {progress?.done || isSending ? 'Close' : 'Cancel'}
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
