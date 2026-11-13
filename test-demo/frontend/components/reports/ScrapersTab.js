'use client';

import React, { useState, useMemo } from 'react';
import { 
  Download, AlertTriangle, CheckCircle2, Terminal, 
  ArrowUpDown, ChevronLeft, ChevronRight, Clock, Zap
} from 'lucide-react';
import { exportToCsv, formatNum, formatPct, formatDateStr } from './reportUtils';

export default function ScrapersTab({ data }) {
  const [sortKey, setSortKey] = useState('new_leads_added');
  const [sortDir, setSortDir] = useState('desc');
  const [runPage, setRunPage] = useState(1);
  const [runPageSize] = useState(50);

  const scrapers = data?.scrapers || [];
  const totals = data?.totals || {};
  const runs = data?.runs || [];
  const flags = data?.flags || {};

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const sortedScrapers = useMemo(() => {
    const list = [...scrapers];
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
  }, [scrapers, sortKey, sortDir]);

  const paginatedRuns = useMemo(() => {
    const start = (runPage - 1) * runPageSize;
    return runs.slice(start, start + runPageSize);
  }, [runs, runPage, runPageSize]);

  const totalRunPages = Math.ceil(runs.length / runPageSize) || 1;

  const exportScrapersCsv = () => {
    const cols = [
      { key: 'script_name', label: 'Script Name' },
      { key: 'full_name', label: 'Full Description' },
      { key: 'times_run', label: 'Runs' },
      { key: 'successful', label: 'Successful' },
      { key: 'failed', label: 'Failed' },
      { key: 'records_collected', label: 'Records Collected' },
      { key: 'new_leads_added', label: 'New Leads Added' },
      { key: 'existing_leads_updated', label: 'Existing Updated' },
      { key: 'duplicates_detected', label: 'Duplicates Detected' },
      { key: 'duplicate_pct', label: 'Duplicate %' },
      { key: 'yield_pct', label: 'New Lead Yield %' },
      { key: 'last_run_time', label: 'Last Run' },
      { key: 'last_status', label: 'Last Status' },
      { key: 'days_since_new_lead', label: 'Days Since New Lead' },
    ];
    exportToCsv('scraper_performance_report', cols, sortedScrapers);
  };

  const exportRunsCsv = () => {
    const cols = [
      { key: 'run_id', label: 'Run ID' },
      { key: 'start_time', label: 'Start Time' },
      { key: 'end_time', label: 'End Time' },
      { key: 'duration_minutes', label: 'Duration (min)' },
      { key: 'scrapers_count', label: 'Scrapers Count' },
      { key: 'failed_scrapers_count', label: 'Failed Scrapers' },
      { key: 'total_records', label: 'Total Records' },
      { key: 'total_new_leads', label: 'New Leads' },
    ];
    exportToCsv('scraper_execution_cycles', cols, runs);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Flag List Alert */}
      {flags.total_flags > 0 && (
        <div className="jp-alert jp-alert-error" style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', alignItems: 'stretch' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 700, fontSize: '0.85rem' }}>
            <AlertTriangle size={16} />
            Scraper Engine Attention Flags ({flags.total_flags})
          </div>

          <div style={{ fontSize: '0.78rem', display: 'flex', flexDirection: 'column', gap: 4 }}>
            {(flags.failed_last_run || []).map(f => (
              <div key={f.script}>
                • <strong>{f.script}</strong> failed in its last run ({f.time}): <em>{f.error || 'Failed'}</em>
              </div>
            ))}
            {(flags.not_producing || []).map(f => (
              <div key={f.script}>
                • <strong>{f.script}</strong> has added <strong>0 new leads</strong> across its last {f.runs_checked} executions (low yield / stale source).
              </div>
            ))}
            {(flags.stale_scrapers || []).map(f => (
              <div key={f.script}>
                • <strong>{f.script}</strong> has not executed for {f.hours_ago} hours (hourly schedule expected).
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Scrapers Aggregated Table */}
      <div className="rp-table-card">
        <div className="rp-table-top">
          <div className="rp-table-title">
            <Terminal size={16} color="var(--primary-blue)" />
            Scraper Engine Performance ({scrapers.length} engines)
          </div>
          <div className="rp-table-actions">
            <button type="button" className="theme-pill-btn neutral" onClick={exportScrapersCsv}>
              <Download size={13} /> Export Scrapers CSV
            </button>
          </div>
        </div>

        <div className="theme-table-scroll">
          <table className="jp-table">
            <thead>
              <tr>
                <th onClick={() => handleSort('script_name')} style={{ cursor: 'pointer' }}>
                  Scraper Script <ArrowUpDown size={11} />
                </th>
                <th onClick={() => handleSort('times_run')} style={{ cursor: 'pointer', textAlign: 'right' }}>
                  Runs <ArrowUpDown size={11} />
                </th>
                <th onClick={() => handleSort('successful')} style={{ cursor: 'pointer', textAlign: 'right' }}>
                  Success / Fail <ArrowUpDown size={11} />
                </th>
                <th onClick={() => handleSort('records_collected')} style={{ cursor: 'pointer', textAlign: 'right' }}>
                  Records <ArrowUpDown size={11} />
                </th>
                <th onClick={() => handleSort('new_leads_added')} style={{ cursor: 'pointer', textAlign: 'right' }}>
                  New Leads <ArrowUpDown size={11} />
                </th>
                <th onClick={() => handleSort('duplicates_detected')} style={{ cursor: 'pointer', textAlign: 'right' }}>
                  Dupes <ArrowUpDown size={11} />
                </th>
                <th onClick={() => handleSort('duplicate_pct')} style={{ cursor: 'pointer', textAlign: 'right' }}>
                  Dupe % <ArrowUpDown size={11} />
                </th>
                <th onClick={() => handleSort('yield_pct')} style={{ cursor: 'pointer', textAlign: 'right' }}>
                  Yield % <ArrowUpDown size={11} />
                </th>
                <th onClick={() => handleSort('days_since_new_lead')} style={{ cursor: 'pointer', textAlign: 'right' }}>
                  Last Added <ArrowUpDown size={11} />
                </th>
                <th>Last Status</th>
              </tr>
            </thead>
            <tbody>
              {/* Totals Row */}
              {totals.times_run > 0 && (
                <tr style={{ background: 'var(--bg-subtle-2)', fontWeight: 700 }}>
                  <td>{totals.script_name}</td>
                  <td style={{ textAlign: 'right' }}>{formatNum(totals.times_run)}</td>
                  <td style={{ textAlign: 'right' }}>{formatNum(totals.successful)} / {formatNum(totals.failed)}</td>
                  <td style={{ textAlign: 'right' }}>{formatNum(totals.records_collected)}</td>
                  <td style={{ textAlign: 'right', color: 'var(--success-green)' }}>+{formatNum(totals.new_leads_added)}</td>
                  <td style={{ textAlign: 'right' }}>{formatNum(totals.duplicates_detected)}</td>
                  <td style={{ textAlign: 'right' }}>{formatPct(totals.duplicate_pct)}</td>
                  <td style={{ textAlign: 'right' }}>{formatPct(totals.yield_pct)}</td>
                  <td style={{ textAlign: 'right' }}>—</td>
                  <td>
                    <span className={`rp-badge ${totals.failed > 0 ? 'rp-badge-warning' : 'rp-badge-success'}`}>
                      {totals.last_status}
                    </span>
                  </td>
                </tr>
              )}

              {sortedScrapers.map(s => {
                const isFail = s.failed > 0 || s.last_status.toLowerCase() === 'failed';
                return (
                  <tr key={s.script_name}>
                    <td>
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{s.script_name}</div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{s.full_name}</div>
                    </td>
                    <td style={{ textAlign: 'right' }}>{formatNum(s.times_run)}</td>
                    <td style={{ textAlign: 'right', fontSize: '0.74rem' }}>
                      <span style={{ color: 'var(--success-green)' }}>{s.successful}</span> / <span style={{ color: s.failed ? 'var(--danger-red)' : 'var(--text-muted)' }}>{s.failed}</span>
                    </td>
                    <td style={{ textAlign: 'right' }}>{formatNum(s.records_collected)}</td>
                    <td style={{ textAlign: 'right', fontWeight: 700, color: s.new_leads_added > 0 ? 'var(--success-green)' : 'var(--text-muted)' }}>
                      {s.new_leads_added > 0 ? `+${formatNum(s.new_leads_added)}` : '0'}
                    </td>
                    <td style={{ textAlign: 'right', color: 'var(--text-muted)' }}>{formatNum(s.duplicates_detected)}</td>
                    <td style={{ textAlign: 'right' }}>{formatPct(s.duplicate_pct)}</td>
                    <td style={{ textAlign: 'right', fontWeight: 600 }}>{formatPct(s.yield_pct)}</td>
                    <td style={{ textAlign: 'right', fontSize: '0.74rem' }}>
                      {s.days_since_new_lead !== null ? (
                        <span style={{ color: s.days_since_new_lead > 7 ? 'var(--warning-amber)' : 'var(--text-primary)' }}>
                          {s.days_since_new_lead === 0 ? 'Today' : `${s.days_since_new_lead}d ago`}
                        </span>
                      ) : 'Never'}
                    </td>
                    <td>
                      <span className={`rp-badge ${isFail ? 'rp-badge-danger' : 'rp-badge-success'}`}>
                        {s.last_status}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Historical Cycles (Per Run Table) */}
      <div className="rp-table-card">
        <div className="rp-table-top">
          <div className="rp-table-title">
            <Clock size={16} color="var(--primary-blue)" />
            Hourly Execution Cycles ({runs.length} runs in period)
          </div>
          <div className="rp-table-actions">
            <button type="button" className="theme-pill-btn neutral" onClick={exportRunsCsv}>
              <Download size={13} /> Export Cycles CSV
            </button>
          </div>
        </div>

        {runs.length === 0 ? (
          <div className="rp-empty">
            <div className="rp-empty-title">No scraper runs in this period</div>
            <div className="rp-empty-desc">Adjust your date range filter to view older execution logs.</div>
          </div>
        ) : (
          <>
            <div className="theme-table-scroll">
              <table className="jp-table">
                <thead>
                  <tr>
                    <th>Run ID</th>
                    <th>Start Time</th>
                    <th>End Time</th>
                    <th style={{ textAlign: 'right' }}>Duration</th>
                    <th style={{ textAlign: 'right' }}>Scrapers Executed</th>
                    <th style={{ textAlign: 'right' }}>Failures</th>
                    <th style={{ textAlign: 'right' }}>Records Collected</th>
                    <th style={{ textAlign: 'right' }}>New Leads Added</th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedRuns.map(r => (
                    <tr key={r.run_id}>
                      <td style={{ fontFamily: 'monospace', fontSize: '0.74rem', fontWeight: 600 }}>{r.run_id}</td>
                      <td style={{ fontSize: '0.74rem' }}>{formatDateStr(r.start_time)}</td>
                      <td style={{ fontSize: '0.74rem' }}>{formatDateStr(r.end_time)}</td>
                      <td style={{ textAlign: 'right' }}>{r.duration_minutes} min</td>
                      <td style={{ textAlign: 'right' }}>{r.scrapers_count}</td>
                      <td style={{ textAlign: 'right' }}>
                        <span className={`rp-badge ${r.failed_scrapers_count > 0 ? 'rp-badge-danger' : 'rp-badge-success'}`}>
                          {r.failed_scrapers_count}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>{formatNum(r.total_records)}</td>
                      <td style={{ textAlign: 'right', fontWeight: 700, color: r.total_new_leads > 0 ? 'var(--success-green)' : 'var(--text-muted)' }}>
                        {r.total_new_leads > 0 ? `+${r.total_new_leads}` : '0'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {runs.length > runPageSize && (
              <div className="rp-pagination">
                <span>
                  Showing {((runPage - 1) * runPageSize) + 1}–{Math.min(runPage * runPageSize, runs.length)} of {runs.length} runs
                </span>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button 
                    type="button" 
                    className="theme-pill-btn neutral" 
                    style={{ padding: '3px 8px' }} 
                    disabled={runPage <= 1} 
                    onClick={() => setRunPage(p => p - 1)}
                  >
                    <ChevronLeft size={13} /> Prev
                  </button>
                  <button 
                    type="button" 
                    className="theme-pill-btn neutral" 
                    style={{ padding: '3px 8px' }} 
                    disabled={runPage >= totalRunPages} 
                    onClick={() => setRunPage(p => p + 1)}
                  >
                    Next <ChevronRight size={13} />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

