'use client';

import React, { useState, useEffect } from 'react';
import { 
  Building2, 
  Mail, 
  Phone, 
  Globe, 
  MapPin, 
  User, 
  Briefcase, 
  Save, 
  RotateCcw, 
  Send, 
  CheckCircle2, 
  Sparkles,
  ShieldCheck,
  FileText,
  Clock,
  Layers
} from 'lucide-react';
import { 
  CompanySettings, 
  DEFAULT_COMPANY_SETTINGS, 
  getStoredSettings, 
  saveStoredSettings, 
  formatSignature 
} from '@/lib/settings';

export default function SettingsPage() {
  const [settings, setSettings] = useState<CompanySettings>(DEFAULT_COMPANY_SETTINGS);
  const [newService, setNewService] = useState('');
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [testEmailLoading, setTestEmailLoading] = useState(false);
  const [testEmailStatus, setTestEmailStatus] = useState<string | null>(null);

  useEffect(() => {
    setSettings(getStoredSettings());
  }, []);

  const handleChange = (field: keyof CompanySettings, value: any) => {
    setSettings(prev => ({ ...prev, [field]: value }));
  };

  const handleSave = () => {
    saveStoredSettings(settings);
    setSavedSuccess(true);
    setTimeout(() => setSavedSuccess(false), 3000);
  };

  const handleReset = () => {
    if (confirm('Are you sure you want to reset all company settings to defaults?')) {
      setSettings(DEFAULT_COMPANY_SETTINGS);
      saveStoredSettings(DEFAULT_COMPANY_SETTINGS);
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    }
  };

  const addService = () => {
    if (!newService.trim()) return;
    setSettings(prev => ({
      ...prev,
      services: [...prev.services, newService.trim()]
    }));
    setNewService('');
  };

  const removeService = (index: number) => {
    setSettings(prev => ({
      ...prev,
      services: prev.services.filter((_, i) => i !== index)
    }));
  };

  const sendTestEmail = async () => {
    setTestEmailLoading(true);
    setTestEmailStatus(null);
    try {
      const fullSignature = formatSignature(settings);
      const testBody = `Hello,\n\nThis is a test outreach email confirming that your Sangeeta Infotech signature and SMTP settings are operational!\n\n---\n${fullSignature}`;
      
      const res = await fetch('/api/leads/bulk-email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          leads: [
            {
              id: 'test-ping',
              email: settings.email,
              full_name: settings.senderName,
              company_name: settings.companyName,
              project_title: 'SMTP & Signature Verification Test'
            }
          ],
          subject: `[Test] Sangeeta Infotech Outreach Signature Preview`,
          message: testBody,
          isDirectTest: true
        })
      });

      const data = await res.json();
      if (data.success && data.sent > 0) {
        setTestEmailStatus(`Test email successfully delivered to ${settings.email}!`);
      } else {
        setTestEmailStatus(`Failed to send: ${data.results?.[0]?.error || data.error || 'Check SMTP configuration'}`);
      }
    } catch (err: any) {
      setTestEmailStatus(`Error: ${err.message}`);
    } finally {
      setTestEmailLoading(false);
    }
  };

  const liveSignature = formatSignature(settings);

  return (
    <div className="max-w-5xl mx-auto space-y-8 pb-16">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-gray-200 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-blue-600 text-white rounded-lg shadow-sm">
              <Building2 className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Company & Signature Settings</h1>
              <p className="text-sm text-gray-500">
                Manage Sangeeta Infotech profile, contact details, and automated cold outreach email signature.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleReset}
            className="flex items-center gap-1.5 px-3.5 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors shadow-sm"
          >
            <RotateCcw className="h-4 w-4 text-gray-500" />
            Reset Defaults
          </button>
          <button
            onClick={handleSave}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors shadow-sm"
          >
            <Save className="h-4 w-4" />
            Save Changes
          </button>
        </div>
      </div>

      {savedSuccess && (
        <div className="p-4 rounded-lg bg-green-50 border border-green-200 text-green-800 flex items-center gap-3 animate-fade-in">
          <CheckCircle2 className="h-5 w-5 text-green-600 flex-shrink-0" />
          <div>
            <p className="font-medium text-sm">Settings saved successfully!</p>
            <p className="text-xs text-green-700">Your Sangeeta Infotech details and signature will be automatically used in all bulk and single emails.</p>
          </div>
        </div>
      )}

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Form Fields (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          {/* Card 1: Company Profile */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 space-y-5">
            <div className="flex items-center gap-2 pb-3 border-b border-gray-100">
              <Building2 className="h-5 w-5 text-blue-600" />
              <h2 className="font-semibold text-gray-900">Company Profile</h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1.5">Company Name</label>
                <div className="relative">
                  <Building2 className="h-4 w-4 absolute left-3 top-2.5 text-gray-400" />
                  <input
                    type="text"
                    value={settings.companyName}
                    onChange={(e) => handleChange('companyName', e.target.value)}
                    className="w-full pl-9 pr-3 py-2 text-sm border rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1.5">Tagline / Slogan</label>
                <div className="relative">
                  <Sparkles className="h-4 w-4 absolute left-3 top-2.5 text-gray-400" />
                  <input
                    type="text"
                    value={settings.tagline}
                    onChange={(e) => handleChange('tagline', e.target.value)}
                    className="w-full pl-9 pr-3 py-2 text-sm border rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1.5">Sender / Representative Name</label>
                <div className="relative">
                  <User className="h-4 w-4 absolute left-3 top-2.5 text-gray-400" />
                  <input
                    type="text"
                    value={settings.senderName}
                    onChange={(e) => handleChange('senderName', e.target.value)}
                    className="w-full pl-9 pr-3 py-2 text-sm border rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1.5">Sender Role / Title</label>
                <div className="relative">
                  <Briefcase className="h-4 w-4 absolute left-3 top-2.5 text-gray-400" />
                  <input
                    type="text"
                    value={settings.senderRole}
                    onChange={(e) => handleChange('senderRole', e.target.value)}
                    className="w-full pl-9 pr-3 py-2 text-sm border rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Card 2: Contact Information */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 space-y-5">
            <div className="flex items-center gap-2 pb-3 border-b border-gray-100">
              <Mail className="h-5 w-5 text-blue-600" />
              <h2 className="font-semibold text-gray-900">Contact & Web Details</h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1.5">Sender Email Address</label>
                <div className="relative">
                  <Mail className="h-4 w-4 absolute left-3 top-2.5 text-gray-400" />
                  <input
                    type="email"
                    value={settings.email}
                    onChange={(e) => handleChange('email', e.target.value)}
                    className="w-full pl-9 pr-3 py-2 text-sm border rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1.5">Phone / WhatsApp</label>
                <div className="relative">
                  <Phone className="h-4 w-4 absolute left-3 top-2.5 text-gray-400" />
                  <input
                    type="text"
                    value={settings.phone}
                    onChange={(e) => handleChange('phone', e.target.value)}
                    className="w-full pl-9 pr-3 py-2 text-sm border rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1.5">Company Website</label>
                <div className="relative">
                  <Globe className="h-4 w-4 absolute left-3 top-2.5 text-gray-400" />
                  <input
                    type="url"
                    value={settings.website}
                    onChange={(e) => handleChange('website', e.target.value)}
                    className="w-full pl-9 pr-3 py-2 text-sm border rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1.5">Location / City</label>
                <div className="relative">
                  <MapPin className="h-4 w-4 absolute left-3 top-2.5 text-gray-400" />
                  <input
                    type="text"
                    value={settings.address}
                    onChange={(e) => handleChange('address', e.target.value)}
                    className="w-full pl-9 pr-3 py-2 text-sm border rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Card 3: Core Services */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 space-y-4">
            <div className="flex items-center gap-2 pb-3 border-b border-gray-100">
              <Layers className="h-5 w-5 text-blue-600" />
              <h2 className="font-semibold text-gray-900">Key Services Offered</h2>
            </div>
            <p className="text-xs text-gray-500">
              These highlights demonstrate Sangeeta Infotech capabilities in outreach emails.
            </p>

            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Add service (e.g. AI Automation, Mobile App)..."
                value={newService}
                onChange={(e) => setNewService(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addService()}
                className="flex-1 px-3 py-2 text-sm border rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
              <button
                type="button"
                onClick={addService}
                className="px-4 py-2 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800 transition-colors"
              >
                Add
              </button>
            </div>

            <div className="flex flex-wrap gap-2 pt-2">
              {settings.services.map((service, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200"
                >
                  {service}
                  <button
                    type="button"
                    onClick={() => removeService(idx)}
                    className="text-blue-400 hover:text-blue-700 font-bold ml-1"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          </div>

          {/* Card 4: Signature Template Editor */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <div className="flex items-center gap-2">
                <FileText className="h-5 w-5 text-blue-600" />
                <h2 className="font-semibold text-gray-900">Signature Template Pattern</h2>
              </div>
              <span className="text-xs text-gray-400 font-mono">Tags: &#123;companyName&#125;, &#123;email&#125;, etc.</span>
            </div>

            <textarea
              rows={7}
              value={settings.signatureTemplate}
              onChange={(e) => handleChange('signatureTemplate', e.target.value)}
              className="w-full p-3 text-xs font-mono border rounded-lg bg-gray-50 focus:bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
            />

            <div className="flex items-center gap-2 text-xs text-gray-500">
              <Clock className="h-4 w-4 text-gray-400" />
              <span>Delay between bulk emails:</span>
              <select
                value={settings.delayBetweenEmailsMs}
                onChange={(e) => handleChange('delayBetweenEmailsMs', Number(e.target.value))}
                className="border rounded px-2 py-1 text-xs bg-white"
              >
                <option value={1000}>1.0 second</option>
                <option value={1500}>1.5 seconds (Recommended)</option>
                <option value={2000}>2.0 seconds</option>
                <option value={3000}>3.0 seconds (Safest)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Right Column: Live Signature Preview & Test Sender (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* Card: Live Signature Card */}
          <div className="bg-gradient-to-br from-gray-900 to-gray-800 rounded-xl shadow-lg p-6 text-white space-y-4 sticky top-6">
            <div className="flex items-center justify-between border-b border-gray-700/60 pb-3">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-emerald-400" />
                <h3 className="font-semibold text-sm text-gray-100">Live Signature Preview</h3>
              </div>
              <span className="text-xs text-emerald-400 bg-emerald-950/80 px-2.5 py-0.5 rounded-full border border-emerald-800">
                Active
              </span>
            </div>

            <p className="text-xs text-gray-300">
              This official signature will be dynamically appended at the bottom of every proposal & outreach email:
            </p>

            {/* Email Preview Box */}
            <div className="bg-white rounded-lg p-5 text-gray-800 shadow-sm border border-gray-200 text-xs space-y-4">
              <div className="text-gray-400 italic text-[11px] pb-2 border-b border-dashed border-gray-200">
                ... [Proposal message text will appear here] ...
              </div>

              {/* Formatted Signature */}
              <div className="space-y-2 pt-1 font-sans">
                <div className="font-bold text-gray-900 text-sm">
                  {settings.senderName}
                </div>
                <div className="text-blue-700 font-medium text-xs">
                  {settings.senderRole} — {settings.companyName}
                </div>
                <div className="text-gray-500 text-[11px]">
                  {settings.tagline}
                </div>

                <div className="pt-2 border-t border-gray-100 space-y-1 text-gray-600">
                  <div className="flex items-center gap-2">
                    <span className="text-gray-400">📧</span>
                    <span className="font-mono text-gray-800">{settings.email}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-gray-400">📞</span>
                    <span>{settings.phone}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-gray-400">🌐</span>
                    <a href={settings.website} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">
                      {settings.website}
                    </a>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-gray-400">📍</span>
                    <span>{settings.address}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Test Email Verification */}
            <div className="pt-3 border-t border-gray-700/60 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-gray-300">Verify SMTP & Signature</span>
                <button
                  type="button"
                  onClick={sendTestEmail}
                  disabled={testEmailLoading}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors shadow disabled:opacity-50"
                >
                  <Send className="h-3.5 w-3.5" />
                  {testEmailLoading ? 'Sending...' : 'Send Test Mail'}
                </button>
              </div>

              {testEmailStatus && (
                <div className={`p-3 rounded-lg text-xs ${testEmailStatus.startsWith('Test email') ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-700' : 'bg-red-950/80 text-red-300 border border-red-700'}`}>
                  {testEmailStatus}
                </div>
              )}

              <p className="text-[11px] text-gray-400 leading-relaxed">
                💡 Test email sends a sample message to <strong className="text-gray-200">{settings.email}</strong> via Gmail SMTP to verify everything looks perfect.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
