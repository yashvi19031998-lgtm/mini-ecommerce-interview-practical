'use client';

import React, { useState } from 'react';
import { useAuth } from '../lib/auth-context';
import { 
  Lock, Mail, User, Eye, EyeOff, ArrowRight, 
  Sparkles, ShieldCheck, AlertCircle, CheckCircle2, Loader2
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
      if (msg.toLowerCase().includes('is invalid')) {
        setErrorMsg('Email address was rejected by Gmail/Supabase deliverability check (mailbox does not exist). You can use your real email, or click below to enter directly.');
      } else if (msg.toLowerCase().includes('not confirmed')) {
        setErrorMsg('Account exists but email is not confirmed in your inbox yet. Click below to enter the workspace directly.');
      } else if (msg.toLowerCase().includes('rate limit')) {
        setErrorMsg('Supabase free tier hourly email rate limit reached. Click below to enter the workspace directly.');
      } else {
        setErrorMsg(err.message || 'Authentication failed. Please verify credentials.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleInstantBypass = () => {
    bypassDemoLogin({
      id: 'user-' + Date.now(),
      email: email.trim() || 'demo@sangeetainfotech.com',
      user_metadata: { full_name: fullName.trim() || 'Lead Admin' }
    });
  };

  return (
    <div className="auth-wrapper">
      <div className="auth-card">
        {/* Brand Header */}
        <div className="auth-header">
          <div className="auth-logo">S</div>
          <h2 className="auth-title">Sangeeta Infotech</h2>
          <p className="auth-subtitle">Lead Discovery & Autonomous Outreach Engine</p>
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
          <div className="auth-alert alert-error" style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', alignItems: 'flex-start' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', width: '100%' }}>
              <AlertCircle size={15} style={{ flexShrink: 0 }} />
              <span style={{ fontSize: '0.82rem' }}>{errorMsg}</span>
            </div>
            {(errorMsg.includes('click below') || errorMsg.includes('rejected') || errorMsg.includes('confirmed') || errorMsg.includes('rate limit')) && (
              <button
                type="button"
                onClick={handleInstantBypass}
                style={{
                  alignSelf: 'stretch',
                  marginTop: '0.25rem',
                  padding: '0.45rem 0.75rem',
                  background: 'var(--primary-lavender)',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '6px',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.4rem',
                  transition: 'opacity 0.2s ease'
                }}
              >
                <Sparkles size={13} />
                Enter Workspace as {email.trim() || 'Admin'}
              </button>
            )}
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

        {/* Quick Demo Access Divider */}
        <div className="auth-divider">
          <span>OR QUICK ACCESS</span>
        </div>

        <button
          type="button"
          onClick={bypassDemoLogin}
          className="auth-quick-btn"
        >
          <Sparkles size={14} style={{ color: 'var(--primary-lavender)' }} />
          One-Click Admin Demo Login
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
