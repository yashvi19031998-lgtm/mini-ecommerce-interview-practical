'use client';

import React, { useState, useEffect } from 'react';
import { X, Mail, CheckCircle2, AlertCircle, Loader2, Sparkles, Building, User } from 'lucide-react';
import { outreachNames } from '../lib/leadNames';

export default function BulkEmailModal({
  selectedLeadIds = [],
  leads = [],
  isOpen,
  onClose,
  onBulkSend,
  signature = ''
}) {
  const [subject, setSubject] = useState('Partnership & Dedicated Tech Team for {company}');
  const [message, setMessage] = useState(
    `Hi {name},\n\n` +
    `I came across {company} and your business presence in {location}.\n\n` +
    `At Sangeeta Infotech, we specialize in high-performance web applications, mobile apps, and custom software systems. ` +
    `We help ambitious companies scale engineering velocity and launch features faster with dependable tech talent.\n\n` +
    `Key expertise we offer:\n` +
    `• Full-Stack Web Development & Modern Portals\n` +
    `• Mobile Apps (iOS & Android)\n` +
    `• AI Integrations & Automation Workflows\n\n` +
    `Would you be open to a brief 10-minute call this week to explore how we can support your tech needs?`
  );
  const [delayMs, setDelayMs] = useState(1500);
  const [useAi, setUseAi] = useState(true);
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
<<<<<<< HEAD
        delay_ms: delayMs
      });
      if (res) {
        const errors = (res.results || []).filter(r => !r.success);
        const dupCount = errors.filter(r => r.already_sent || (r.error && r.error.includes('already received'))).length;
        const otherErr = errors.find(r => !r.already_sent && (!r.error || !r.error.includes('already received')))?.error;
        let summaryMsg = '';
        if (dupCount > 0 && Number(res.sent) === 0 && !otherErr) {
          summaryMsg = `${dupCount} lead(s) skipped: already contacted in a previous campaign (Anti-spam shield protected).`;
        } else if (otherErr) {
          summaryMsg = otherErr;
        } else if (errors.length > 0) {
          summaryMsg = errors[0].error || 'Some leads were skipped.';
        }
        setProgress({
          sent: Number(res.sent) || 0,
          failed: Number(res.failed) || 0,
          total: validEmailLeads.length,
          done: true,
          error: summaryMsg,
          isDuplicateNotice: dupCount > 0 && !otherErr
        });
      }
=======
        delay_ms: delayMs,
        use_ai: useAi
      }, (job) => setProgress(toProgress(job)));
      if (res) setProgress(toProgress({ ...res, done: true }));
>>>>>>> 85e03f3f39bf42e108e96409ebe3691f593663c6
    } catch (err) {
      setProgress(p => ({ ...(p || {}), done: true, stopped: err.message || 'Failed to dispatch emails' }));
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

  const firstError = (progress?.results || []).find(r => !r.success && r.error)?.error || '';

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
<<<<<<< HEAD
                <span style={{ fontWeight: 600, color: progress.error && progress.sent === 0 && !progress.isDuplicateNotice ? 'var(--danger-red, #dc2626)' : (progress.isDuplicateNotice ? '#b45309' : 'var(--primary-lavender)') }}>
                  {progress.done ? (progress.sent > 0 ? 'Campaign Finished!' : (progress.isDuplicateNotice ? 'Already Contacted' : 'Outreach Not Dispatched')) : 'Dispatching Campaign...'}
                </span>
                <span style={{ color: 'var(--text-secondary)' }}>
                  {progress.sent} Sent | {progress.failed} Skipped of {progress.total}
=======
                <span style={{ fontWeight: 600, color: progress.done && progress.sent === 0 ? 'var(--danger-red, #dc2626)' : 'var(--primary-lavender)' }}>
                  {progress.done
                    ? (progress.sent > 0 ? 'Finished' : 'Finished - nothing was sent')
                    : `Checking mailboxes and sending… ${progress.processed} of ${progress.total}`}
                </span>
                <span style={{ color: 'var(--text-secondary)' }}>
                  {progress.sent} sent · {progress.notSent} not sent
>>>>>>> 85e03f3f39bf42e108e96409ebe3691f593663c6
                </span>
              </div>
              <div className="progress-bar-track">
                <div
                  className="progress-bar-fill"
                  style={{ width: `${pct}%`, background: progress.sent === 0 && progress.done ? (progress.isDuplicateNotice ? '#f59e0b' : '#dc2626') : undefined }}
                />
              </div>
<<<<<<< HEAD
              {progress.error && (
                <div style={{
                  marginTop: '8px',
                  fontSize: '0.78rem',
                  color: progress.isDuplicateNotice ? '#92400e' : '#dc2626',
                  background: progress.isDuplicateNotice ? '#fef3c7' : '#fef2f2',
                  padding: '6px 10px',
                  borderRadius: '6px',
                  border: `1px solid ${progress.isDuplicateNotice ? '#fde68a' : '#fee2e2'}`
                }}>
                  <strong>Status:</strong> {progress.error}
=======
              {!progress.done && (
                <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                  Each address is checked with its mail server first, so this takes a few seconds per lead.
                  You can close this window; sending continues on the server.
>>>>>>> 85e03f3f39bf42e108e96409ebe3691f593663c6
                </div>
              )}
              {(progress.stopped || (progress.done && progress.sent === 0 && firstError)) && (
                <div role="alert" style={{ marginTop: '8px', fontSize: '0.78rem', color: '#dc2626', background: '#fef2f2', padding: '6px 10px', borderRadius: '6px', border: '1px solid #fee2e2' }}>
                  <strong>Reason:</strong> {progress.stopped || firstError}
                </div>
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

          {/* AI Requirement Personalization Toggle */}
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: '10px',
              padding: '10px 12px',
              background: useAi ? 'rgba(99, 102, 241, 0.06)' : 'var(--bg-subtle, #f7f7f8)',
              border: useAi ? '1px solid var(--primary-lavender, #6366f1)' : '1px solid var(--border-light, #e5e7eb)',
              borderRadius: '8px',
              marginBottom: '1rem',
              cursor: isSending ? 'default' : 'pointer'
            }}
            onClick={(e) => {
              if (e.target.tagName !== 'INPUT' && !isSending) {
                setUseAi(!useAi);
              }
            }}
          >
            <input
              type="checkbox"
              id="bulk-use-ai-check"
              checked={useAi}
              onChange={(e) => setUseAi(e.target.checked)}
              disabled={isSending}
              style={{ marginTop: '2px', cursor: 'pointer', accentColor: 'var(--primary-lavender)' }}
            />
            <label htmlFor="bulk-use-ai-check" style={{ cursor: isSending ? 'default' : 'pointer', fontSize: '0.8rem', margin: 0 }}>
              <div style={{ fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Sparkles size={14} style={{ color: 'var(--primary-lavender)' }} />
                <span>AI Requirement Personalization (Recommended)</span>
              </div>
              <div style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                Auto-tailor each email copy to the target company's exact tech stack (React, Node, Python, Mobile, Ecommerce) and hiring need. Sangeeta Infotech signature is 100% guaranteed.
              </div>
            </label>
          </div>

          {/* Message Template */}
          <div className="form-group">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
              <label className="form-label" style={{ margin: 0 }}>Email Message Template</label>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                Smart Placeholders: <code>{'{name}'}</code>, <code>{'{company}'}</code>, <code>{'{location}'}</code>
              </span>
            </div>
            <textarea
              className="form-input"
              rows={7}
              value={message || ''}
              onChange={(e) => setMessage(e.target.value)}
              disabled={isSending}
            />
          </div>

          {/* Dynamic Personalized Preview for First Lead */}
          {validEmailLeads.length > 0 && (() => {
            const sampleLead = validEmailLeads[0];
            const names = outreachNames(sampleLead['Company Name'] || sampleLead.company_name);
            const sampleLoc = String(sampleLead.Address || sampleLead.location || 'your region').trim();
            const previewSub = subject
              .replace(/{company}/g, names.company)
              .replace(/{name}/g, names.greeting)
              .replace(/{location}/g, sampleLoc);
            const previewBody = message
              .replace(/{company}/g, names.company)
              .replace(/{name}/g, names.greeting)
              .replace(/{location}/g, sampleLoc);

            return (
              <div style={{ marginTop: '0.85rem', padding: '0.75rem', background: 'var(--bg-subtle, #f7f7f8)', borderRadius: '8px', border: '1px solid var(--border-light, #ececee)' }}>
                <div style={{ fontSize: '0.74rem', fontWeight: 700, color: 'var(--primary-blue, #1a6dff)', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <Sparkles size={13} />
                  Live Personalized Preview for: {names.company} ({sampleLead.Email})
                </div>
                <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
                  Subject: {previewSub}
                </div>
                <div style={{ fontSize: '0.73rem', color: 'var(--text-secondary)', whiteSpace: 'pre-line', lineHeight: '1.4' }}>
                  {previewBody}
                  {signature && (
                    <>
                      <br /><br />
                      ---<br />
                      {signature.trim()}
                    </>
                  )}
                </div>
              </div>
            );
          })()}
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
