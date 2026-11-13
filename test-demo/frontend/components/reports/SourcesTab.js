'use client';

import React, { useState, useMemo } from 'react';
import { Download, Globe, ArrowUpDown, AlertCircle } from 'lucide-react';
import { exportToCsv, formatNum, formatPct } from './reportUtils';

export default function SourcesTab({ data }) {
  const [sortKey, setSortKey] = useState('hot');
  const [sortDir, setSortDir] = useState('desc');

  const rows = data?.rows || [];

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const sortedRows = useMemo(() => {
    const list = [...rows];
    list.sort((a, b) => {
      let vA = a[sortKey];
      let vB = b[sortKey];
      if (vA === null || vA === undefined) vA = -999999;
      if (vB === null || vB === undefined) vB = -999999;
      if (typeof vA === 'string') {
        return sortDir === 'asc' ? vA.localeCompare(vB) : vB.localeCompare(vA);
      }
      return sortDir === 'asc' ? vA - vB : vB - vA;
    });
    return list;
  }, [rows, sortKey, sortDir]);

  const handleExport = () => {
    const cols = [
      { key: 'source', label: 'Source Family' },
      { key: 'leads', label: 'Total Leads' },
      { key: 'with_email_pct', label: 'Email %' },
      { key: 'with_phone_pct', label: 'Phone %' },
      { key: 'with_contact_pct', label: 'Any Contact %' },
      { key: 'ai_scored', label: 'AI Scored' },
      { key: 'avg_ai_score', label: 'Avg AI Score' },
      { key: 'hot', label: 'Hot Leads (>=7)' },
      { key: 'hot_pct', label: 'Hot %' },
      { key: 'contacted', label: 'Contacted' },
      { key: 'replied', label: 'Replied' },
      { key: 'reply_rate_pct', label: 'Reply Rate %' },
      { key: 'meetings', label: 'Meetings' },
      { key: 'won', label: 'Deals Won' },
      { key: 'stale', label: 'Stale Leads' },
      { key: 'low_value', label: 'Low Value Flag' },
    ];
    exportToCsv('lead_sources_quality_report', cols, sortedRows);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className="rp-table-card">
        <div className="rp-table-top">
          <div>
            <div className="rp-table-title">
              <Globe size={16} color="var(--primary-blue)" />
              Lead Source Family Quality ({rows.length} sources)
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 2 }}>
              Hot Leads are calculated strictly as AI Score ≥ 7 to mirror the Dashboard. Sources with ≥20 leads and 0 hot leads are flagged as Low Value.
            </div>
          </div>
          <div className="rp-table-actions">
            <button type="button" className="theme-pill-btn neutral" onClick={handleExport} disabled={rows.length === 0}>
              <Download size={13} /> Export Sources CSV
            </button>
          </div>
        </div>

        {rows.length === 0 ? (
          <div className="rp-empty">
            <div className="rp-empty-title">No lead sources found in this range</div>
            <div className="rp-empty-desc">Check date or status filters.</div>
          </div>
        ) : (
          <div className="theme-table-scroll">
            <table className="jp-table">
              <thead>
                <tr>
                  <th onClick={() => handleSort('source')} style={{ cursor: 'pointer' }}>
                    Source Family <ArrowUpDown size={11} />
                  </th>
                  <th onClick={() => handleSort('leads')} style={{ cursor: 'pointer', textAlign: 'right' }}>
                    Leads <ArrowUpDown size={11} />
                  </th>
                  <th onClick={() => handleSort('with_contact_pct')} style={{ cursor: 'pointer', textAlign: 'right' }}>
                    Contact % <ArrowUpDown size={11} />
                  </th>
                  <th onClick={() => handleSort('ai_scored')} style={{ cursor: 'pointer', textAlign: 'right' }}>
                    Scored <ArrowUpDown size={11} />
                  </th>
                  <th onClick={() => handleSort('avg_ai_score')} style={{ cursor: 'pointer', textAlign: 'right' }}>
                    Avg Score <ArrowUpDown size={11} />
                  </th>
                  <th onClick={() => handleSort('hot')} style={{ cursor: 'pointer', textAlign: 'right' }}>
                    Hot (≥7) <ArrowUpDown size={11} />
                  </th>
                  <th onClick={() => handleSort('hot_pct')} style={{ cursor: 'pointer', textAlign: 'right' }}>
                    Hot % <ArrowUpDown size={11} />
                  </th>
                  <th onClick={() => handleSort('contacted')} style={{ cursor: 'pointer', textAlign: 'right' }}>
                    Contacted <ArrowUpDown size={11} />
                  </th>
                  <th onClick={() => handleSort('reply_rate_pct')} style={{ cursor: 'pointer', textAlign: 'right' }}>
                    Reply % <ArrowUpDown size={11} />
                  </th>
                  <th onClick={() => handleSort('won')} style={{ cursor: 'pointer', textAlign: 'right' }}>
                    Won <ArrowUpDown size={11} />
                  </th>
                  <th>Quality Flag</th>
                </tr>
              </thead>
              <tbody>
                {sortedRows.map(r => (
                  <tr key={r.source}>
                    <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{r.source}</td>
                    <td style={{ textAlign: 'right', fontWeight: 600 }}>{formatNum(r.leads)}</td>
                    <td style={{ textAlign: 'right' }}>{formatPct(r.with_contact_pct)}</td>
                    <td style={{ textAlign: 'right' }}>{formatNum(r.ai_scored)}</td>
                    <td style={{ textAlign: 'right', fontWeight: 600 }}>{r.avg_ai_score !== null ? r.avg_ai_score : '—'}</td>
                    <td style={{ textAlign: 'right', fontWeight: 700, color: r.hot > 0 ? 'var(--success-green)' : 'var(--text-muted)' }}>
                      {formatNum(r.hot)}
                    </td>
                    <td style={{ textAlign: 'right' }}>{formatPct(r.hot_pct)}</td>
                    <td style={{ textAlign: 'right' }}>{formatNum(r.contacted)}</td>
                    <td style={{ textAlign: 'right' }}>{formatPct(r.reply_rate_pct)}</td>
                    <td style={{ textAlign: 'right', fontWeight: 700, color: r.won > 0 ? 'var(--success-green)' : 'var(--text-muted)' }}>
                      {formatNum(r.won)}
                    </td>
                    <td>
                      {r.low_value ? (
                        <span className="rp-badge rp-badge-danger" title="High volume with 0 hot buyer signals. Consider pausing.">
                          Low Value
                        </span>
                      ) : (
                        <span className="rp-badge rp-badge-success">
                          Active Source
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

