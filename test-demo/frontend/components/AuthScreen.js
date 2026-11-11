'use client';

import React, { useState } from 'react';
import { useAuth } from '../lib/auth-context';
import { 
  Lock, Mail, User, Eye, EyeOff, ArrowRight, 
  ShieldCheck, AlertCircle, CheckCircle2, Loader2, Sparkles
} from 'lucide-react';

export default function AuthScreen() {
  const { signIn, signUp, bypassDemoLogin } = useAuth();
  const [isRegisterMode, setIsRegisterMode] = useState(false);
  
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setSuccessMsg('');

    if (!email || !password) {
      setErrorMsg('Please enter both email and password.');
      return;
    }

    if (password.length < 6) {
      setErrorMsg('Password must be at least 6 characters.');
      return;
    }

    const cleanEmail = email.trim();
    setIsLoading(true);
    try {
      if (isRegisterMode) {
        await signUp(cleanEmail, password, fullName);
        setSuccessMsg('Account registered successfully! If Supabase email confirmation is enabled, check your inbox or sign in.');
        setIsRegisterMode(false);
      } else {
        await signIn(cleanEmail, password);
      }
    } catch (err) {
      console.error('[AUTH ERROR]', err);
      const msg = err.message || '';
      if (msg.toLowerCase().includes('failed to fetch') || msg.toLowerCase().includes('network') || msg.toLowerCase().includes('fetch')) {
        setErrorMsg('Supabase project is paused or offline on supabase.com. You can unpause it or click below to enter directly.');
      } else if (msg.toLowerCase().includes('is invalid')) {
        setErrorMsg('This email address was rejected (mailbox does not exist). Please use your real email address.');
      } else if (msg.toLowerCase().includes('not confirmed')) {
        setErrorMsg('Your email is not confirmed yet. Open the confirmation link in your inbox, or ask the admin to confirm your account in the Supabase dashboard.');
      } else if (msg.toLowerCase().includes('rate limit')) {
        setErrorMsg('Too many sign-up emails were sent this hour. Please try again later, or ask the admin to create your account in the Supabase dashboard.');
      } else {
        setErrorMsg(err.message || 'Authentication failed. Please verify credentials.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-wrapper">
      <div className="auth-card">
        {/* Brand Header */}
        <div className="auth-header">
          <div className="auth-logo">⚡</div>
          <h2 className="auth-title">LeadsGen AI</h2>
          <p className="auth-subtitle">Autonomous B2B Prospecting & Intelligence Engine</p>
        </div>

        {/* Tab Switcher */}
        <div className="auth-tab-bar">
          <button
            type="button"
            onClick={() => { setIsRegisterMode(false); setErrorMsg(''); setSuccessMsg(''); }}
            className={`auth-tab-btn ${!isRegisterMode ? 'active' : ''}`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => { setIsRegisterMode(true); setErrorMsg(''); setSuccessMsg(''); }}
            className={`auth-tab-btn ${isRegisterMode ? 'active' : ''}`}
          >
            Create Account
          </button>
        </div>

        {/* Alerts */}
        {errorMsg && (
          <div className="auth-alert alert-error">
            <AlertCircle size={15} style={{ flexShrink: 0 }} />
            <span style={{ fontSize: '0.82rem' }}>{errorMsg}</span>
          </div>
        )}

        {successMsg && (
          <div className="auth-alert alert-success">
            <CheckCircle2 size={15} style={{ flexShrink: 0 }} />
            <span>{successMsg}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="auth-form">
          {isRegisterMode && (
            <div className="form-group">
              <label className="form-label">Full Name</label>
              <div className="auth-input-wrapper">
                <User size={15} className="auth-input-icon" />
                <input
                  type="text"
                  className="auth-input"
                  placeholder="Enter your name"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                />
              </div>
            </div>
          )}

          <div className="form-group">
            <label className="form-label">Work Email Address</label>
            <div className="auth-input-wrapper">
              <Mail size={15} className="auth-input-icon" />
              <input
                type="email"
                className="auth-input"
                placeholder="name@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Password</label>
            <div className="auth-input-wrapper">
              <Lock size={15} className="auth-input-icon" />
              <input
                type={showPassword ? 'text' : 'password'}
                className="auth-input"
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="auth-toggle-pwd"
              >
                {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="auth-submit-btn"
          >
            {isLoading ? (
              <>
                <Loader2 size={15} className="animate-spin" />
                {isRegisterMode ? 'Creating Account...' : 'Signing In...'}
              </>
            ) : (
              <>
                <span>{isRegisterMode ? 'Register New Account' : 'Sign In to Workspace'}</span>
                <ArrowRight size={15} />
              </>
            )}
          </button>
        </form>

        {/* Quick Local Access */}
        <div style={{ margin: '1.25rem 0 0.5rem', textAlign: 'center', position: 'relative' }}>
          <span style={{ fontSize: '0.72rem', color: '#64748b', letterSpacing: '0.05em', background: '#0f172a', padding: '0 8px' }}>
            OR LOCAL WORKSPACE ACCESS
          </span>
        </div>

        <button
          type="button"
          onClick={() => bypassDemoLogin({
            id: 'admin-' + Date.now(),
            email: email.trim() || 'admin@sangeetainfotech.com',
            user_metadata: { full_name: fullName.trim() || 'Lead Admin' }
          })}
          style={{
            width: '100%',
            padding: '0.65rem',
            background: 'rgba(56, 189, 248, 0.1)',
            border: '1px solid rgba(56, 189, 248, 0.3)',
            borderRadius: '8px',
            color: '#38bdf8',
            fontSize: '0.82rem',
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.5rem',
            marginBottom: '1rem',
            transition: 'background 0.2s'
          }}
        >
          <Sparkles size={14} />
          One-Click Admin Login (Offline / Local Dev)
        </button>

        {/* Security Footer */}
        <div className="auth-footer-note">
          <ShieldCheck size={13} />
          <span>Secured via Supabase Authentication & JWT Encryption</span>
        </div>
      </div>
    </div>
  );
}
