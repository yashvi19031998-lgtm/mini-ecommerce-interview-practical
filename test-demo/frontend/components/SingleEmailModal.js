'use client';

import React, { useState, useEffect } from 'react';
import { outreachNames } from '../lib/leadNames';
import { fetchAiEmailDraft } from '../lib/api';
import { X, Send, Mail, Building, MapPin, Sparkles, RefreshCw } from 'lucide-react';

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
  const [isAiLoading, setIsAiLoading] = useState(false);

  // Load tailored draft on open
  useEffect(() => {
    if (!lead || !isOpen) return;

    let isCancelled = false;

    // 1. Initial immediate fallback draft
    const names = outreachNames(lead['Company Name']);
    const loc = String(lead.Address || '').trim();
    const where = names.isCompany ? `${names.company}${loc ? ` (${loc})` : ''}` : 'your team';
    setSubject(`Software & Technical Engineering Partnership for ${where}`);
    setMessage(
      `Hi ${names.greeting},\n\n` +
      `I noticed ${where}'s growing engineering presence. Scaling development bandwidth and finding pre-vetted senior engineers often creates friction in sprint cycles.\n\n` +
      `At Sangeeta Infotech, our senior engineers specialize in high-impact full-stack web development, modern mobile apps, and custom software systems. We partner with tech teams to provide dedicated developers who integrate seamlessly into your roadmap without hiring lag.\n\n` +
      `Would you have 10 minutes for a brief discovery chat this week to explore how we could support your technical roadmaps?`
    );

    // 2. Fetch specific requirement-aware AI draft from backend
    if (lead.id) {
      setIsAiLoading(true);
      fetchAiEmailDraft(lead.id)
        .then((draft) => {
          if (!isCancelled && draft && draft.subject && draft.body) {
            setSubject(draft.subject);
            // If draft body already has signature, strip it for the editable textarea since the box below previews it
            let bodyText = draft.body;
            if (bodyText.includes('\n\n---\n')) {
              bodyText = bodyText.split('\n\n---\n')[0].trim();
            }
            setMessage(bodyText);
          }
        })
        .catch(() => {
          // Keep the initial clean fallback on error
        })
        .finally(() => {
          if (!isCancelled) setIsAiLoading(false);
        });
    }

    return () => {
      isCancelled = true;
    };
  }, [lead, isOpen]);

  const handleAiRegenerate = async () => {
    if (!lead?.id || isAiLoading) return;
    setIsAiLoading(true);
    try {
      const draft = await fetchAiEmailDraft(lead.id);
      if (draft && draft.subject && draft.body) {
        setSubject(draft.subject);
        let bodyText = draft.body;
        if (bodyText.includes('\n\n---\n')) {
          bodyText = bodyText.split('\n\n---\n')[0].trim();
        }
        setMessage(bodyText);
      }
    } catch (e) {
      console.warn('AI draft regeneration failed:', e);
    } finally {
      setIsAiLoading(false);
    }
  };

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
    } catch {
      // The page already showed why the send failed (bad login, do-not-contact rule...).
      // Keep the pop-up open so the text is not lost; without this catch the error was left unhandled.
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
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
              <label className="form-label" style={{ margin: 0 }}>Email Pitch & Message Body</label>
              <button
                type="button"
                onClick={handleAiRegenerate}
                disabled={isAiLoading || isSending}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  background: 'rgba(99, 102, 241, 0.08)',
                  border: '1px solid var(--primary-lavender, #6366f1)',
                  color: 'var(--primary-lavender, #6366f1)',
                  borderRadius: '6px',
                  padding: '3px 8px',
                  fontSize: '0.72rem',
                  fontWeight: 600,
                  cursor: isAiLoading ? 'wait' : 'pointer',
                  transition: 'all 0.15s ease'
                }}
                title="Regenerate company and requirement-tailored draft using AI"
              >
                {isAiLoading ? (
                  <>
                    <RefreshCw size={11} className="animate-spin" />
                    <span>Synthesizing...</span>
                  </>
                ) : (
                  <>
                    <Sparkles size={11} />
                    <span>Regenerate with AI</span>
                  </>
                )}
              </button>
            </div>
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
