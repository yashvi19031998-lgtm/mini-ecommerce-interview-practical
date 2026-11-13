'use client';

import React, { useState, useEffect } from 'react';
import { 
  Building, Mail, Key, Globe, Phone, MapPin, 
  Send, Save, CheckCircle2, Loader2, Sparkles, Database, Sliders, Clock, ShieldAlert
} from 'lucide-react';
import { fetchSettings, saveSettings, testSmtpEmail } from '../lib/api';
import ApiKeysPanel from './ApiKeysPanel';

export default function SettingsView({ showToast, onNavigateToLeads = null }) {
  const [settings, setSettings] = useState({
    company_name: '',
    company_description: '',
    tagline: '',
    website: '',
    phone: '',
    address: '',
    email: '',
    default_keywords: 'software company, web development, mobile app, IT services',
    default_city: 'Ahmedabad',
    default_state: 'Gujarat',
    auto_send_email: true,
    max_pending_emails: 5,
    excluded_companies: '8dots',
    smtp_host: 'smtp.gmail.com',
    smtp_port: 587,
    smtp_user: '',
    smtp_pass: '',
    sender_name: '',
    default_subject: '',
    default_template: ''
  });

  const [formattedSignature, setFormattedSignature] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);

  useEffect(() => {
    fetchSettings().then(res => {
      if (res && res.settings) {
        const s = res.settings;
        setSettings(prev => ({
          company_name: s.company_name || s.companyName || prev.company_name || '',
          company_description: s.company_description || s.companyDescription || prev.company_description || '',
          tagline: s.tagline || prev.tagline || '',
          website: s.website || prev.website || '',
          phone: s.phone || prev.phone || '',
          address: s.address || prev.address || '',
          email: s.email || prev.email || '',
          default_keywords: Array.isArray(s.default_keywords || s.defaultKeywords)
            ? (s.default_keywords || s.defaultKeywords).join(', ')
            : (s.default_keywords || s.defaultKeywords || prev.default_keywords),
          default_city: s.default_city || s.defaultCity || prev.default_city || 'Ahmedabad',
          default_state: s.default_state || s.defaultState || prev.default_state || 'Gujarat',
          auto_send_email: s.auto_send_email !== undefined ? s.auto_send_email : (s.autoSendEmail !== undefined ? s.autoSendEmail : true),
          max_pending_emails: s.max_pending_emails ?? s.maxPendingEmailsPerRun ?? prev.max_pending_emails ?? 5,
          excluded_companies: Array.isArray(s.excludedCompanies || s.excluded_companies)
            ? (s.excludedCompanies || s.excluded_companies).join(', ')
            : (s.excludedCompanies || s.excluded_companies || prev.excluded_companies || '8dots'),
          smtp_host: s.smtp_host || s.smtpHost || prev.smtp_host || 'smtp.gmail.com',
          smtp_port: s.smtp_port || s.smtpPort || prev.smtp_port || 587,
          smtp_user: s.smtp_user || s.smtpUser || s.email || prev.smtp_user || '',
          smtp_pass: s.smtp_pass || s.smtpPass || prev.smtp_pass || '',
          sender_name: s.sender_name || s.senderName || prev.sender_name || '',
          default_subject: s.default_subject || s.defaultSubject || prev.default_subject || '',
          default_template: s.default_template || s.defaultMessage || prev.default_template || ''
        }));
        setFormattedSignature(res.formattedSignature || '');
      }
    });
  }, []);

  const handleChange = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      const kwsArray = String(settings.default_keywords || '')
        .split(',')
        .map(k => k.trim())
        .filter(Boolean);

      const excludedArray = String(settings.excluded_companies || '')
        .split(',')
        .map(c => c.trim())
        .filter(Boolean);

      // The mail password is never sent or stored from this screen (the server reads it from .env).
      const { smtp_pass: _smtpPass, ...safeSettings } = settings;
      const payload = {
        ...safeSettings,
        companyName: settings.company_name,
        companyDescription: settings.company_description,
        defaultKeywords: kwsArray,
        defaultCity: settings.default_city,
        defaultState: settings.default_state,
        autoSendEmail: Boolean(settings.auto_send_email),
        // 0 = no per-run limit (every qualified lead found is e-mailed; a daily limit still applies)
        maxPendingEmailsPerRun: Math.max(0, Math.floor(Number(settings.max_pending_emails) || 0)),
        excludedCompanies: excludedArray,
        senderName: settings.sender_name,
        defaultSubject: settings.default_subject,
        defaultMessage: settings.default_template
      };
      await saveSettings(payload);
      showToast('Settings, branding & automation parameters saved successfully!', 'success');
    } catch (err) {
      showToast(err.message || 'Failed saving configuration', 'error');
    } finally {
      setIsSaving(false);
    }
  };

  const handleTestEmail = async () => {
    setIsTesting(true);
    try {
      const res = await testSmtpEmail();
      if (res.success) {
        showToast('Verification email delivered to ' + (settings.email || 'your inbox') + '!', 'success');
      } else {
        showToast(res.error || 'SMTP delivery test failed', 'error');
      }
    } catch (err) {
      showToast(err.message || 'SMTP test failed', 'error');
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <form onSubmit={handleSave}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 400px), 1fr))', gap: '1.5rem', marginBottom: '1.5rem' }}>
          {/* Card 1: Company Profile */}
          <div className="glass-panel">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginBottom: '1.25rem' }}>
              <div style={{ background: 'var(--bg-lavender-light)', color: 'var(--primary-lavender)', padding: '7px', borderRadius: '8px' }}>
                <Building size={18} />
              </div>
              <div>
                <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                  Company Profile & Branding
                </h3>
                <p style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
                  Applied across cold email templates and outgoing signatures.
                </p>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div className="form-group">
                <label className="form-label">Company Name</label>
                <input
                  type="text"
                  className="form-input"
                  value={settings.company_name || ''}
                  onChange={(e) => handleChange('company_name', e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Tagline / Mission Statement</label>
                <input
                  type="text"
                  className="form-input"
                  value={settings.tagline || ''}
                  onChange={(e) => handleChange('tagline', e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Company Description & Core Services (Used by AI & Cold Emails)</label>
                <textarea
                  className="form-input"
                  rows={3}
                  placeholder="Describe your company services, core tech stack, and offerings. Used in cold emails and AI qualification..."
                  value={settings.company_description || ''}
                  onChange={(e) => handleChange('company_description', e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Official Website URL</label>
                <input
                  type="text"
                  className="form-input"
                  value={settings.website || ''}
                  onChange={(e) => handleChange('website', e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Contact Mobile / WhatsApp</label>
                <input
                  type="text"
                  className="form-input"
                  value={settings.phone || ''}
                  onChange={(e) => handleChange('phone', e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Business Office Location</label>
                <input
                  type="text"
                  className="form-input"
                  value={settings.address || ''}
                  onChange={(e) => handleChange('address', e.target.value)}
                />
              </div>
            </div>
          </div>

          {/* Card 2: SMTP & Delivery Server */}
          <div className="glass-panel">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginBottom: '1.25rem' }}>
              <div style={{ background: 'var(--bg-pink-soft)', color: 'var(--accent-pink)', padding: '7px', borderRadius: '8px' }}>
                <Key size={18} />
              </div>
              <div>
                <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                  SMTP Outreach Credentials
                </h3>
                <p style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
                  Delivers automated outreach directly through your verified mail server.
                </p>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '0.75rem' }}>
                <div className="form-group">
                  <label className="form-label">SMTP Server Host</label>
                  <input
                    type="text"
                    className="form-input"
                    value={settings.smtp_host || ''}
                    readOnly
                    disabled
                    title="Set in the server's .env file (SMTP_HOST)"
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Port</label>
                  <input
                    type="number"
                    className="form-input"
                    value={settings.smtp_port ?? 587}
                    readOnly
                    disabled
                    title="Set in the server's .env file (SMTP_PORT)"
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Sender Display Name</label>
                <input
                  type="text"
                  className="form-input"
                  value={settings.sender_name || ''}
                  onChange={(e) => handleChange('sender_name', e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Sender Email Address (Username)</label>
                <input
                  type="email"
                  className="form-input"
                  value={settings.email || settings.smtp_user || ''}
                  onChange={(e) => {
                    handleChange('email', e.target.value);
                    handleChange('smtp_user', e.target.value);
                  }}
                />
              </div>

              <div className="form-group">
                <label className="form-label">SMTP Password / Google App Password</label>
                <div className="settings-note" role="note">
                  <Key size={14} style={{ flexShrink: 0, marginTop: 2 }} />
                  <span>
                    The mail server, port and password are read from the server&apos;s <code>.env</code> file, so they
                    are not edited here. For safety the mail password is not entered or saved here. Put it in the server&apos;s <code>.env</code> file
                    as <code>SMTP_USER</code> and <code>SMTP_PASS</code> (for Gmail, a 16-character App Password from
                    myaccount.google.com/apppasswords), then restart the backend. &ldquo;Send Test Verification Email&rdquo; below
                    confirms it works, and the API Keys list at the bottom of this page shows whether it is set.
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Card 3: Default Scraper Targeting & 1-Hour Automation */}
          <div className="glass-panel" style={{ gridColumn: '1 / -1' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginBottom: '1.25rem' }}>
              <div style={{ background: 'var(--bg-lavender-light)', color: 'var(--primary-lavender)', padding: '7px', borderRadius: '8px' }}>
                <Sliders size={18} />
              </div>
              <div>
                <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                  Default Scraper Targeting & 1-Hour Automation
                </h3>
                <p style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
                  Pre-fills all scraping forms and powers the hourly automated lead harvesting and outreach engine.
                </p>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.25rem' }}>
              <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                <label className="form-label">Default Search Keywords (Comma-separated)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. software company, web development, mobile app, IT services"
                  value={settings.default_keywords || ''}
                  onChange={(e) => handleChange('default_keywords', e.target.value)}
                />
                <span style={{ fontSize: '0.71rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                  Auto-populated across Google Maps, Search Engines, Ecommerce, and Job Portals.
                </span>
              </div>

              <div className="form-group">
                <label className="form-label">Default City</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Ahmedabad"
                  value={settings.default_city || ''}
                  onChange={(e) => handleChange('default_city', e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Default State</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Gujarat"
                  value={settings.default_state || ''}
                  onChange={(e) => handleChange('default_state', e.target.value)}
                />
              </div>

              <div className="form-group" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem' }}>
                  <input
                    type="checkbox"
                    checked={Boolean(settings.auto_send_email)}
                    onChange={(e) => handleChange('auto_send_email', e.target.checked)}
                    style={{ width: 16, height: 16, accentColor: 'var(--primary-lavender)' }}
                  />
                  <span>1-Hour Auto Scraper: Send Intro Emails to Qualified Leads</span>
                </label>
                <span style={{ fontSize: '0.71rem', color: 'var(--text-muted)', marginTop: '4px', paddingLeft: 24 }}>
                  Automatically dispatches verified intro emails to newly qualified leads during hourly runs.
                </span>
              </div>

              <div className="form-group">
                <label className="form-label">Max Automated Emails Per 1-Hour Run (0 = no limit)</label>
                <input
                  type="number"
                  min={0}
                  className="form-input"
                  value={settings.max_pending_emails ?? 5}
                  onChange={(e) => handleChange('max_pending_emails', Math.max(0, Math.floor(Number(e.target.value) || 0)))}
                />
                <span style={{ fontSize: '0.71rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                  0 = every qualified lead found is e-mailed in the same run. To protect the Gmail account the app
                  never sends more than 300 e-mails in one day (Gmail blocks sending above about 500); the rest go the next day.
                </span>
              </div>

              <div className="form-group" style={{ gridColumn: '1 / -1', marginTop: '0.5rem', background: 'rgba(244, 63, 94, 0.05)', padding: '14px', borderRadius: '10px', border: '1px solid rgba(244, 63, 94, 0.2)' }}>
                <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#f43f5e', fontWeight: 700 }}>
                  <ShieldAlert size={15} />
                  Excluded Companies / Do-Not-Contact List (બ્લેકલિસ્ટેડ કંપનીઓ)
                </label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. 8dots, CompetitorLtd, PartnerCompany"
                  value={settings.excluded_companies || ''}
                  onChange={(e) => handleChange('excluded_companies', e.target.value)}
                  style={{ borderColor: 'rgba(244, 63, 94, 0.4)', background: 'var(--bg-glass)' }}
                />
                <span style={{ fontSize: '0.73rem', color: '#f43f5e', marginTop: '4px', display: 'block', fontWeight: 500 }}>
                  🛡️ Strict Safety Shield: Emails will NEVER be sent to leads from these companies (matches company name, website domain, or email address). Multiple companies can be separated by commas (e.g. 8dots, ABC Corp).
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Live Signature Preview & Actions */}
        <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--primary-lavender)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Sparkles size={16} />
            Live Outgoing Email Signature Preview
          </h3>
          <div className="signature-preview-box">
            <div>--</div>
            <div style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{settings.sender_name || 'Your Name'}</div>
            <div style={{ color: 'var(--primary-lavender)' }}>{settings.company_name || 'Sangeeta Infotech'} — {settings.tagline || 'Dedicated Tech Teams'}</div>
            <div>🌐 <a href={settings.website} target="_blank" rel="noreferrer" style={{ color: 'var(--primary-lavender)' }}>{settings.website}</a></div>
            <div>📱 {settings.phone} | ✉️ {settings.email}</div>
            <div style={{ color: 'var(--text-secondary)' }}>📍 {settings.address}</div>
          </div>
        </div>

        {/* Save Bar */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', flexWrap: 'wrap' }}>
          {onNavigateToLeads && (
            <button
              type="button"
              onClick={onNavigateToLeads}
              className="btn btn-secondary btn-sm"
              style={{ marginRight: 'auto' }}
              title="Return to qualified leads CRM"
            >
              <Database size={14} />
              Return to Leads Database
            </button>
          )}

          <button
            type="button"
            onClick={handleTestEmail}
            disabled={isTesting}
            className="btn btn-secondary btn-sm"
          >
            {isTesting ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                Testing SMTP Server...
              </>
            ) : (
              <>
                <Send size={14} />
                Send Test Verification Email
              </>
            )}
          </button>

          <button
            type="submit"
            disabled={isSaving}
            className="btn btn-primary btn-sm"
          >
            {isSaving ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save size={14} />
                Save Settings
              </>
            )}
          </button>
        </div>
      </form>
      <ApiKeysPanel />
    </div>
  );
}
