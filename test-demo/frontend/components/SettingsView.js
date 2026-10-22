'use client';

import React, { useState, useEffect } from 'react';
import { 
  Building, Mail, Key, Globe, Phone, MapPin, 
  Send, Save, Eye, EyeOff, CheckCircle2, Loader2, Sparkles, Database
} from 'lucide-react';
import { fetchSettings, saveSettings, testSmtpEmail } from '../lib/api';

export default function SettingsView({ showToast, onNavigateToLeads = null }) {
  const [settings, setSettings] = useState({
    company_name: '',
    tagline: '',
    website: '',
    phone: '',
    address: '',
    email: '',
    smtp_host: 'smtp.gmail.com',
    smtp_port: 587,
    smtp_user: '',
    smtp_pass: '',
    sender_name: '',
    default_subject: '',
    default_template: ''
  });

  const [formattedSignature, setFormattedSignature] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);

  useEffect(() => {
    fetchSettings().then(res => {
      if (res.settings) {
        setSettings(res.settings);
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
      await saveSettings(settings);
      showToast('Settings & signature saved successfully!', 'success');
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
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '1.5rem', marginBottom: '1.5rem' }}>
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
                  value={settings.company_name}
                  onChange={(e) => handleChange('company_name', e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Tagline / Mission Statement</label>
                <input
                  type="text"
                  className="form-input"
                  value={settings.tagline}
                  onChange={(e) => handleChange('tagline', e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Official Website URL</label>
                <input
                  type="text"
                  className="form-input"
                  value={settings.website}
                  onChange={(e) => handleChange('website', e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Contact Mobile / WhatsApp</label>
                <input
                  type="text"
                  className="form-input"
                  value={settings.phone}
                  onChange={(e) => handleChange('phone', e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Business Office Location</label>
                <input
                  type="text"
                  className="form-input"
                  value={settings.address}
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
                    value={settings.smtp_host}
                    onChange={(e) => handleChange('smtp_host', e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Port</label>
                  <input
                    type="number"
                    className="form-input"
                    value={settings.smtp_port}
                    onChange={(e) => handleChange('smtp_port', Number(e.target.value))}
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Sender Display Name</label>
                <input
                  type="text"
                  className="form-input"
                  value={settings.sender_name}
                  onChange={(e) => handleChange('sender_name', e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Sender Email Address (Username)</label>
                <input
                  type="email"
                  className="form-input"
                  value={settings.email || settings.smtp_user}
                  onChange={(e) => {
                    handleChange('email', e.target.value);
                    handleChange('smtp_user', e.target.value);
                  }}
                />
              </div>

              <div className="form-group">
                <label className="form-label">SMTP Password / Google App Password</label>
                <div style={{ position: 'relative' }}>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    className="form-input"
                    style={{ paddingRight: '2.5rem' }}
                    value={settings.smtp_pass}
                    onChange={(e) => handleChange('smtp_pass', e.target.value)}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(p => !p)}
                    className="auth-toggle-pwd"
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                <span style={{ fontSize: '0.71rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                  For Gmail, generate a 16-character App Password at myaccount.google.com/apppasswords
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
    </div>
  );
}
