'use client';

import React, { useEffect } from 'react';
import { 
  X, Sparkles, Building2, User, Globe, Mail, Phone, ExternalLink, 
  CheckCircle2, DollarSign, Briefcase, Award, ArrowUpRight, MessageSquare, Copy, Check
} from 'lucide-react';
import { buildWhatsAppLink } from '../lib/api';

export default function AILeadDossierModal({
  lead,
  isOpen,
  onClose,
  onSendEmail,
  onOpenWhatsApp,
  onStatusChange
}) {
  const [copiedField, setCopiedField] = React.useState(null);

  // Close on Escape & prevent background scroll
  useEffect(() => {
    if (!isOpen) return;
    const orig = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const handleKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => {
      document.body.style.overflow = orig;
      window.removeEventListener('keydown', handleKey);
    };
  }, [isOpen, onClose]);

  if (!isOpen || !lead) return null;

  const handleCopy = (text, fieldName) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedField(fieldName);
    setTimeout(() => setCopiedField(null), 1800);
  };

  const compName = lead['Company Name'] || lead.company_name || 'Business Prospect';
  const website = lead['Website URL'] || lead.website || '';
  const email = lead.Email || lead.email || '';
  const phone = lead['Mobile Number'] || lead.mobile_number || '';
  const location = lead.Address || lead.location || 'India';
  const source = lead.Source || lead.source || 'Scraper';
  const sourceUrl = lead.source_url || '';
  
  const score = parseInt(lead.ai_score, 10) || 0;
  const category = lead.ai_category || 'general_prospect';
  const summary = lead.ai_summary || 'No AI summary generated yet.';
  const requirement = lead.ai_requirement || 'General software development & technical solutions.';
  const techStack = lead.ai_tech_stack || '';
  const reason = lead.ai_reason || '';
  const budget = lead.deal_size_estimate || lead.ai_budget || '';
  const seniorityFit = lead.seniority_fit || 'Standard Web';
  const decisionMaker = lead.full_name || 'Hiring Lead / Founder';
  const decisionTitle = lead.decision_maker_title || (lead.lead_type === 'Job Posting' ? 'Technical Hiring Manager' : 'Business Owner');
  const linkedinUrl = lead.linkedin_url || (compName ? `https://www.linkedin.com/search/results/all/?keywords=${encodeURIComponent(compName)}` : '');
  const signals = lead.website_signals || '';
  const pipelineStatus = String(lead.Status || lead.status || 'NEW').toUpperCase();

  const isHot = score >= 7;
  const hasPhone = phone && phone !== 'N/A';
  const hasEmail = email && email.includes('@') && email !== 'N/A';

  // Split tech stack into pills
  const techPills = techStack
    ? techStack.split(/[,;/|]+/).map(t => t.trim()).filter(Boolean)
    : [];

  return (
    <div 
      className="dossier-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="dossier-drawer" role="dialog" aria-modal="true">
        {/* Top Drawer Header */}
        <div className="dossier-header">
          <div className="dossier-brand-row">
            <span className="dossier-ai-badge">
              <Sparkles size={13} className="text-amber-400" />
              <span>LeadsGen AI Intelligence Dossier</span>
            </span>
            <button 
              onClick={onClose} 
              className="dossier-close-btn"
              title="Close Dossier (Esc)"
            >
              <X size={18} />
            </button>
          </div>

          <div className="dossier-hero-row">
            <div className="dossier-avatar">
              {compName[0]?.toUpperCase() || 'C'}
            </div>
            <div className="dossier-hero-info">
              <h2 className="dossier-company-name">{compName}</h2>
              <div className="dossier-sub-info">
                {website ? (
                  <a 
                    href={website.startsWith('http') ? website : `https://${website}`}
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="dossier-link"
                  >
                    <Globe size={12} />
                    <span>{website.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '')}</span>
                    <ExternalLink size={10} />
                  </a>
                ) : (
                  <span className="text-dim">No website URL</span>
                )}
                <span className="dossier-dot-sep">•</span>
                <span className="dossier-loc-pill">{location}</span>
                <span className="dossier-dot-sep">•</span>
                <span className="dossier-source-pill">Via {source}</span>
              </div>
            </div>

            {/* Score Visual Gauge */}
            <div className={`dossier-score-card ${isHot ? 'hot' : 'warm'}`}>
              <div className="dossier-score-num">{score}/10</div>
              <div className="dossier-score-label">{isHot ? '🔥 High Intent Fit' : 'Prospect'}</div>
            </div>
          </div>
        </div>

        {/* Action Bar */}
        <div className="dossier-action-bar">
          <button
            onClick={() => onSendEmail && onSendEmail(lead)}
            className="dossier-action-btn primary"
            disabled={!hasEmail}
            title={hasEmail ? 'Draft AI Email Outreach' : 'No email address on file'}
          >
            <Mail size={14} />
            <span>Draft AI Email</span>
          </button>

          <button
            onClick={() => onOpenWhatsApp && onOpenWhatsApp(lead)}
            className="dossier-action-btn whatsapp"
            disabled={!hasPhone}
            title={hasPhone ? '1-Click WhatsApp Chat' : 'No phone number on file'}
          >
            <MessageSquare size={14} />
            <span>Launch WhatsApp</span>
          </button>

          {linkedinUrl && (
            <a
              href={linkedinUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="dossier-action-btn linkedin"
              title="Open LinkedIn Profile / Search"
            >
              <ArrowUpRight size={14} />
              <span>LinkedIn</span>
            </a>
          )}

          {sourceUrl && (
            <a
              href={sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="dossier-action-btn neutral"
              title="Open Original Source Posting"
            >
              <ExternalLink size={14} />
              <span>Original Post</span>
            </a>
          )}
        </div>

        {/* Scrollable Content Body */}
        <div className="dossier-body">
          {/* Section 1: AI Opportunity Analysis */}
          <div className="dossier-card">
            <div className="dossier-card-title">
              <Sparkles size={15} color="#2563eb" />
              <span>AI Fit & Opportunity Breakdown</span>
            </div>

            <div className="dossier-grid-2">
              <div className="dossier-metric-item">
                <div className="metric-label">Seniority Match</div>
                <div className="metric-val highlight-blue">
                  <Award size={14} />
                  <span>{seniorityFit}</span>
                </div>
              </div>

              <div className="dossier-metric-item">
                <div className="metric-label">Estimated Deal Size</div>
                <div className="metric-val highlight-green">
                  <DollarSign size={14} />
                  <span>{budget || '$2,500 - $6,000'}</span>
                </div>
              </div>
            </div>

            <div className="dossier-field-row">
              <div className="dossier-field-label">AI Category</div>
              <div className="dossier-field-val">
                <span className="dossier-category-pill">{category.replace(/_/g, ' ').toUpperCase()}</span>
              </div>
            </div>

            <div className="dossier-field-row">
              <div className="dossier-field-label">Executive Brief</div>
              <div className="dossier-field-val brief-text">{summary}</div>
            </div>

            {requirement && (
              <div className="dossier-field-row">
                <div className="dossier-field-label">Client Requirement</div>
                <div className="dossier-field-val brief-text">{requirement}</div>
              </div>
            )}

            {reason && (
              <div className="dossier-field-row">
                <div className="dossier-field-label">AI Rationale</div>
                <div className="dossier-field-val text-muted text-sm">{reason}</div>
              </div>
            )}
          </div>

          {/* Section 2: Tech Stack & Digital Health */}
          <div className="dossier-card">
            <div className="dossier-card-title">
              <Briefcase size={15} color="#7c3aed" />
              <span>Tech Stack & Digital Signals</span>
            </div>

            <div className="dossier-tech-container">
              {techPills.length > 0 ? (
                techPills.map((tech, i) => (
                  <span key={i} className="dossier-tech-tag">{tech}</span>
                ))
              ) : (
                <span className="text-dim text-sm">Full-Stack / Modern Web Architecture</span>
              )}
            </div>

            {signals && (
              <div className="dossier-signals-box">
                <span className="signals-title">Website Signals:</span>
                <span className="signals-desc">{signals}</span>
              </div>
            )}
          </div>

          {/* Section 3: Decision Maker & Contact Coordinates */}
          <div className="dossier-card">
            <div className="dossier-card-title">
              <User size={15} color="#059669" />
              <span>Decision Maker & Direct Contacts</span>
            </div>

            <div className="dossier-contact-list">
              {/* Decision Maker */}
              <div className="dossier-contact-row">
                <div className="contact-icon-box">
                  <User size={14} />
                </div>
                <div className="contact-info">
                  <div className="contact-name">{decisionMaker}</div>
                  <div className="contact-title">{decisionTitle}</div>
                </div>
              </div>

              {/* Email */}
              <div className="dossier-contact-row">
                <div className="contact-icon-box">
                  <Mail size={14} />
                </div>
                <div className="contact-info">
                  <div className="contact-label">Verified Email</div>
                  <div className="contact-value-row">
                    <span className="contact-val">{email || 'Not available'}</span>
                    {hasEmail && (
                      <button 
                        onClick={() => handleCopy(email, 'email')} 
                        className="dossier-copy-btn"
                        title="Copy email"
                      >
                        {copiedField === 'email' ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Phone / WhatsApp */}
              <div className="dossier-contact-row">
                <div className="contact-icon-box">
                  <Phone size={14} />
                </div>
                <div className="contact-info">
                  <div className="contact-label">Direct Phone / WhatsApp</div>
                  <div className="contact-value-row">
                    <span className="contact-val">{phone || 'Not available'}</span>
                    {hasPhone && (
                      <button 
                        onClick={() => handleCopy(phone, 'phone')} 
                        className="dossier-copy-btn"
                        title="Copy phone"
                      >
                        {copiedField === 'phone' ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
                      </button>
                    )}
                    {lead.whatsapp_status === 'READY' && (
                      <span className="dossier-wa-ready-tag">WhatsApp Ready</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Section 4: Pipeline Status */}
          <div className="dossier-card">
            <div className="dossier-card-title">
              <CheckCircle2 size={15} color="#ea580c" />
              <span>CRM Pipeline Progression</span>
            </div>
            
            <div className="dossier-pipeline-wrap">
              {['NEW', 'CONTACTED', 'REPLIED', 'MEETING', 'WON', 'DISQUALIFIED'].map(st => (
                <button
                  key={st}
                  onClick={() => onStatusChange && onStatusChange(lead.id, st)}
                  className={`dossier-stage-pill ${pipelineStatus === st ? 'active' : ''}`}
                >
                  {st}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
