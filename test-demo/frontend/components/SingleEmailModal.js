'use client';

import React, { useState, useEffect } from 'react';
import { X, Send, Mail, Building, MapPin, Sparkles } from 'lucide-react';

export default function SingleEmailModal({
  lead,
  isOpen,
  onClose,
  onSend,
  signature = ''
}) {
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [isSending, setIsSending] = useState(false);

  useEffect(() => {
    if (lead) {
      const comp = lead['Company Name'] || 'your team';
      const loc = lead.Address || 'your area';
      setSubject(`Partnership & Dedicated Tech Team for ${comp}`);
      setMessage(
        `Hi ${comp} Team,\n\n` +
        `I noticed your impressive work at ${comp} in ${loc}. At Sangeeta Infotech, we specialize in high-impact software development, scalable web architectures, and full-stack engineering.\n\n` +
        `We would love to discuss whether our developers can help streamline your upcoming technical roadmaps on a flexible model.\n\n` +
        `Would you have 10 minutes for a brief discovery call this week?`
      );
    }
  }, [lead]);

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

  if (!isOpen || !lead) return null;

  const handleSendClick = async () => {
    setIsSending(true);
    try {
      await onSend({
        id: lead.id,
        to: lead.Email,
        subject,
        message: signature ? `${message}\n\n---\n${signature.trim()}` : message
      });
      onClose();
    } finally {
      setIsSending(false);
    }
  };

  const insertVariable = (placeholder) => {
    setMessage(prev => `${prev} ${placeholder}`);
  };

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
        {/* Header */}
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <div style={{ background: 'var(--bg-lavender-light)', color: 'var(--primary-lavender)', padding: '7px', borderRadius: '8px' }}>
              <Mail size={18} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                Cold Outreach Composer
              </h3>
              <p style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
                Target: <strong>{lead['Company Name']}</strong> ({lead.Email})
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="modal-close-btn"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="modal-body">
          {/* Lead Meta Strip */}
          <div className="modal-meta-strip">
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Building size={14} style={{ color: 'var(--primary-lavender)' }} />
              <strong>{lead['Company Name']}</strong>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <MapPin size={14} style={{ color: 'var(--warning)' }} />
              <span>{lead.Address || 'Remote'}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Sparkles size={14} style={{ color: 'var(--success)' }} />
              <span>Intent: {lead.Intent || 'High'}</span>
            </div>
          </div>

          {/* Subject Field */}
          <div className="form-group">
            <label className="form-label">Email Subject Line</label>
            <input
              type="text"
              className="form-input"
              value={subject || ''}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Enter compelling subject line..."
            />
          </div>

          {/* Variables helper */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>Insert chips:</span>
            <button
              type="button"
              onClick={() => insertVariable('{company}')}
              className="btn-chip"
            >
              + {'{company}'}
            </button>
            <button
              type="button"
              onClick={() => insertVariable('{name}')}
              className="btn-chip"
            >
              + {'{name}'}
            </button>
            <button
              type="button"
              onClick={() => insertVariable('{location}')}
              className="btn-chip"
            >
              + {'{location}'}
            </button>
          </div>

          {/* Message Body */}
          <div className="form-group">
            <label className="form-label">Email Pitch & Message Body</label>
            <textarea
              className="form-input"
              rows={8}
              value={message || ''}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Write personalized outreach message..."
            />
          </div>

          {/* Signature Preview */}
          {signature && (
            <div className="signature-preview-box">
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '4px', textTransform: 'uppercase', fontWeight: 600 }}>
                Included Sangeeta Infotech Signature:
              </div>
              <div style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', whiteSpace: 'pre-wrap', fontFamily: 'var(--font-code)' }}>
                {signature}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="modal-footer">
          <button
            onClick={onClose}
            disabled={isSending}
            className="btn btn-secondary btn-sm"
          >
            Cancel
          </button>
          <button
            onClick={handleSendClick}
            disabled={isSending || !subject.trim() || !message.trim()}
            className="btn btn-primary btn-sm"
          >
            <Send size={14} />
            {isSending ? 'Sending via Gmail SMTP...' : 'Dispatch Email Now'}
          </button>
        </div>
      </div>
    </div>
  );
}
