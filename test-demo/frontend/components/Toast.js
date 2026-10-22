'use client';

import React from 'react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';

export default function Toast({ toasts = [], onDismiss }) {
  if (!toasts.length) return null;

  return (
    <div className="toast-shelf">
      {toasts.map((t) => {
        let Icon = Info;
        let iconColor = 'var(--primary-lavender)';
        if (t.type === 'success') {
          Icon = CheckCircle2;
          iconColor = 'var(--success)';
        }
        if (t.type === 'error') {
          Icon = AlertCircle;
          iconColor = 'var(--error)';
        }

        return (
          <div key={t.id} className={`toast-item ${t.type || 'info'}`}>
            <Icon size={18} style={{ flexShrink: 0, color: iconColor }} />
            <div style={{ flex: 1, fontSize: '0.82rem', lineHeight: '1.4', color: 'var(--text-primary)' }}>
              {t.message}
            </div>
            <button
              onClick={() => onDismiss(t.id)}
              className="toast-dismiss-btn"
            >
              <X size={14} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
