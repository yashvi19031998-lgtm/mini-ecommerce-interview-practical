'use client';

import React, { useState, useEffect } from 'react';
import { X, MessageSquare, ExternalLink } from 'lucide-react';
import { buildWhatsAppLink } from '../lib/api';

export default function WhatsAppModal({
  lead,
  isOpen,
  onClose
}) {
  const [template, setTemplate] = useState(
    `Hi {company} Team, I noticed your business in {location}. Sangeeta Infotech provides dedicated software developers and full-stack web solutions. Would you be open to a quick 5-min chat regarding tech requirements?`
  );

  // Body scroll lock and Escape key listener
  React.useEffect(() => {
    if (!isOpen) return;

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      document.body.style.overflow = originalOverflow;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen || !lead) return null;

  const phone = lead['Mobile Number'] || '';
  const comp = lead['Company Name'] || 'there';
  const loc = lead.Address || 'India';
  const filledMsg = template.replace('{company}', comp).replace('{name}', comp).replace('{location}', loc);
  const waUrl = buildWhatsAppLink(phone, comp, filledMsg);

  const handleOpenWhatsApp = () => {
    if (waUrl) {
      window.open(waUrl, '_blank', 'noopener,noreferrer');
      onClose();
    }
  };

  return (
    <div
      className="modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <div className="modal-content" role="dialog" aria-modal="true">
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <div style={{ background: 'var(--bg-pink-soft)', color: 'var(--accent-pink)', padding: '7px', borderRadius: '8px' }}>
              <MessageSquare size={18} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                WhatsApp Direct Outreach
              </h3>
              <p style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
                Target: <strong>{comp}</strong> ({phone || 'No phone'})
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

        <div className="modal-body">
          <div className="form-group">
            <label className="form-label">Recipient Phone Number</label>
            <input
              type="text"
              className="form-input"
              value={phone || ''}
              readOnly
              style={{ background: 'var(--bg-lavender-subtle)', color: 'var(--text-primary)' }}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Message Template</label>
            <textarea
              className="form-input"
              rows={5}
              value={template || ''}
              onChange={(e) => setTemplate(e.target.value)}
            />
          </div>

          {/* Preview Box */}
          <div className="wa-preview-box">
            <div style={{ fontSize: '0.7rem', color: 'var(--success)', fontWeight: 700, marginBottom: '6px', textTransform: 'uppercase' }}>
              Live WhatsApp Message Preview:
            </div>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-primary)', whiteSpace: 'pre-wrap' }}>
              {filledMsg}
            </p>
          </div>
        </div>

        <div className="modal-footer">
          <button onClick={onClose} className="btn btn-secondary btn-sm">
            Cancel
          </button>
          <button
            onClick={handleOpenWhatsApp}
            disabled={!waUrl}
            className="btn btn-whatsapp btn-sm"
          >
            <ExternalLink size={14} />
            Open in WhatsApp Web / App
          </button>
        </div>
      </div>
    </div>
  );
}
