'use client';

import React, { useState } from 'react';
import { exportToCsv, formatNum, formatPct } from './reportUtils';
import { ShieldAlert, Download, Copy, Check, Info } from 'lucide-react';

export default function DataHealthTab({ data, loading, onOpenLeads }) {
  const [copiedId, setCopiedId] = useState(null);

  if (loading) {
    return (
      <div className="rp-loading-state" role="status" aria-live="polite">
        <div className="rp-spinner" />
        <p>Analyzing CRM data hygiene and field completeness...</p>
      </div>
    );
  }

  if (!data || !data.metrics) {
    return (
      <div className="rp-empty-state">
        <ShieldAlert size={36} color="var(--text-tertiary)" />
        <p>No data health metrics available.</p>
      </div>
    );
  }

  const { total_leads, metrics } = data;

  const handleCopy = (id) => {
    if (!id) return;
    navigator.clipboard?.writeText(id).catch(() => {});
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleExport = () => {
    const headers = ['Metric', 'Severity', 'Issue Count', 'Percentage of Database (%)', 'Description', 'Sample IDs'];
    const rows = metrics.map((m) => [
      m.label,
      m.severity.toUpperCase(),
      m.count,
      m.percentage,
      m.description,
      (m.sample_lead_ids || []).join('; ')
    ]);
    exportToCsv(`crm_data_health_${new Date().toISOString().slice(0, 10)}.csv`, headers, rows);
  };

  const getSeverityBadgeClass = (sev) => {
    switch (sev?.toLowerCase()) {
      case 'high':
        return 'rp-severity-badge rp-severity-high';
      case 'medium':
        return 'rp-severity-badge rp-severity-medium';
      case 'low':
      default:
        return 'rp-severity-badge rp-severity-low';
    }
  };

  return (
    <div className="rp-tab-pane">
      {/* Header bar */}
      <div className="rp-header-row">
        <div>
          <h2 className="rp-section-title">CRM Data Hygiene & Completeness</h2>
          <p className="rp-section-sub">
            Auditing <strong>{formatNum(total_leads)}</strong> total leads across core contactability and enrichment dimensions.
          </p>
        </div>
        <div className="rp-header-actions">
          <button
            type="button"
            className="rp-btn rp-btn-secondary"
            onClick={handleExport}
            title="Export health audit report to CSV"
          >
            <Download size={14} />
            <span>Export CSV</span>
          </button>
        </div>
      </div>

      {/* Grid of health check cards */}
      <div className="rp-health-grid">
        {metrics.map((m) => {
          const isHighAlert = m.severity === 'high' && m.count > 0;
          return (
            <div
              key={m.metric}
              className={`rp-health-card ${isHighAlert ? 'rp-health-card-alert' : ''}`}
            >
              <div className="rp-health-card-header">
                <div className="rp-health-title-group">
                  <span className={getSeverityBadgeClass(m.severity)}>
                    {m.severity.toUpperCase()}
                  </span>
                  <h3 className="rp-health-label">{m.label}</h3>
                </div>
                <div className="rp-health-stat">
                  <span className="rp-health-count">{formatNum(m.count)}</span>
                  <span className="rp-health-pct">({formatPct(m.percentage)})</span>
                </div>
              </div>

              <p className="rp-health-desc">{m.description}</p>

              {/* Progress Bar of Defect Rate */}
              <div className="rp-health-progress-bar-bg" title={`${m.percentage}% of leads affected`}>
                <div
                  className={`rp-health-progress-bar-fill ${m.severity}`}
                  style={{ width: `${Math.min(100, Math.max(0, m.percentage))}%` }}
                />
              </div>

              {/* Sample IDs */}
              <div className="rp-health-samples-container">
                <div className="rp-health-samples-label">
                  <Info size={12} />
                  <span>Sample Affected Leads (up to 20):</span>
                </div>
                {m.sample_lead_ids && m.sample_lead_ids.length > 0 ? (
                  <div className="rp-health-chips">
                    {m.sample_lead_ids.map((lid) => (
                      <button
                        key={lid}
                        type="button"
                        className="rp-health-chip"
                        onClick={() => handleCopy(lid)}
                        title="Click to copy Lead ID"
                      >
                        <span>{lid}</span>
                        {copiedId === lid ? <Check size={10} color="var(--success-text, #10b981)" /> : <Copy size={10} />}
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="rp-health-clean-note">
                    ✓ Clean: No defect instances detected.
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

