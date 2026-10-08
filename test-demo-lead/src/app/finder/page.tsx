"use client";

import { useState, useEffect } from 'react';
import { supabase } from '@/lib/supabase';
import { ExternalLink, Loader2, CheckCircle, XCircle, AlertCircle } from 'lucide-react';

type ProcessStatus = 'idle' | 'processing' | 'saved' | 'duplicate' | 'failed';

interface ResultItem {
  title: string;
  link: string;
  status: ProcessStatus;
  leadId?: string;
  error?: string;
}

export default function LeadFinder() {
  const [query, setQuery] = useState('');
  const [url, setUrl] = useState('');
  const [processingUrl, setProcessingUrl] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<ResultItem[]>([]);
  const [savedQueries, setSavedQueries] = useState<any[]>([]);
  const [lastSavedLead, setLastSavedLead] = useState<any>(null);

  useEffect(() => {
    async function fetchQueries() {
      const { data } = await supabase.from('search_queries').select('*').eq('active', true);
      if (data) setSavedQueries(data);
    }
    fetchQueries();
  }, []);

  const addLog = (msg: string) => setLogs(l => [...l, msg]);

  const handleSearch = async () => {
    if (!query) return;
    setIsSearching(true);
    setLogs(['🔍 Searching Google via Serper...']);
    setSearchResults([]);
    try {
      const res = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });
      const data = await res.json();
      if (res.ok) {
        addLog(`✅ Found ${data.results.length} results.`);
        setSearchResults(data.results.map((r: any) => ({ ...r, status: 'idle' })));
      } else {
        addLog(`❌ Search Error: ${data.error}`);
      }
    } catch (error: any) {
      addLog(`❌ Error: ${error.message}`);
    } finally {
      setIsSearching(false);
    }
  };

  // Real process-url: calls API, shows status per result
  const processLink = async (link: string, platform: string = 'unknown', isManual = false) => {
    if (!isManual) {
      setSearchResults(prev =>
        prev.map(r => r.link === link ? { ...r, status: 'processing' } : r)
      );
    } else {
      setProcessingUrl(true);
      setLastSavedLead(null);
    }
    setLogs([]);
    addLog(`[PROCESS_URL] Starting: ${link}`);
    addLog(`[SCRAPER] Fetching page content...`);

    try {
      const res = await fetch('/api/process-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: link, source_platform: platform })
      });
      const data = await res.json();

      if (res.status === 409) {
        // Duplicate
        addLog(`⚠️ DUPLICATE: This URL is already in your leads database.`);
        if (!isManual) {
          setSearchResults(prev =>
            prev.map(r => r.link === link ? { ...r, status: 'duplicate' } : r)
          );
        }
        return;
      }

      if (!res.ok || !data.success) {
        const errMsg = data.error?.message || 'Unknown error';
        addLog(`❌ FAILED: ${errMsg}`);
        if (!isManual) {
          setSearchResults(prev =>
            prev.map(r => r.link === link ? { ...r, status: 'failed', error: errMsg } : r)
          );
        }
        return;
      }

      // Success
      addLog(`[SCRAPER] Content extracted via: ${data.scraping_method}`);
      addLog(`[GEMINI] Lead extracted successfully`);
      addLog(`[LEAD] Saved to database ✅`);
      addLog(`📋 Project: ${data.lead?.project_title || 'N/A'}`);
      addLog(`👤 Client: ${data.lead?.full_name || 'N/A'}`);
      addLog(`📧 Email: ${data.lead?.email || 'Not found on page'}`);
      addLog(`🎯 Quality: ${data.lead?.lead_quality || 'N/A'}`);

      if (!isManual) {
        setSearchResults(prev =>
          prev.map(r => r.link === link ? { ...r, status: 'saved', leadId: data.lead?.id } : r)
        );
      } else {
        setLastSavedLead(data.lead);
      }
    } catch (error: any) {
      addLog(`❌ Error: ${error.message}`);
      if (!isManual) {
        setSearchResults(prev =>
          prev.map(r => r.link === link ? { ...r, status: 'failed', error: error.message } : r)
        );
      }
    } finally {
      if (isManual) setProcessingUrl(false);
    }
  };

  const statusIcon = (status: ProcessStatus) => {
    if (status === 'processing') return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
    if (status === 'saved') return <CheckCircle className="h-4 w-4 text-green-500" />;
    if (status === 'duplicate') return <AlertCircle className="h-4 w-4 text-yellow-500" />;
    if (status === 'failed') return <XCircle className="h-4 w-4 text-red-500" />;
    return null;
  };

  const statusLabel = (item: ResultItem) => {
    if (item.status === 'processing') return <span className="text-xs text-blue-600">Processing...</span>;
    if (item.status === 'saved') return <span className="text-xs text-green-600 font-medium">✓ Saved to Leads</span>;
    if (item.status === 'duplicate') return <span className="text-xs text-yellow-600">Already in DB</span>;
    if (item.status === 'failed') return <span className="text-xs text-red-500">Failed</span>;
    return null;
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-8">Lead Finder</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Left: Search */}
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium mb-4">Search Queries</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Select or Enter Query</label>
              {savedQueries.length > 0 && (
                <div className="mt-2 mb-2">
                  <select
                    className="block w-full rounded-md border-gray-300 shadow-sm sm:text-sm p-2 border"
                    onChange={(e) => setQuery(e.target.value)}
                    value={savedQueries.find(q => q.query === query) ? query : ""}
                  >
                    <option value="">-- Select a saved query --</option>
                    {savedQueries.map(sq => (
                      <option key={sq.id} value={sq.query}>{sq.name} ({sq.platform})</option>
                    ))}
                  </select>
                </div>
              )}
              <div className="mt-1 flex rounded-md shadow-sm">
                <input
                  type="text"
                  className="block w-full rounded-none rounded-l-md border-gray-300 sm:text-sm p-2 border"
                  placeholder='site:freelancer.com "laravel developer"'
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                />
                <button
                  onClick={handleSearch}
                  disabled={isSearching || !query}
                  className="relative -ml-px inline-flex items-center rounded-r-md border border-gray-300 bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:bg-blue-400"
                >
                  {isSearching ? 'Searching...' : 'Run Search'}
                </button>
              </div>
            </div>

            {searchResults.length > 0 && (
              <div className="mt-4 border rounded-md divide-y max-h-96 overflow-y-auto">
                <div className="px-3 py-2 bg-gray-50 flex items-center justify-between">
                  <span className="text-xs font-bold text-gray-500">{searchResults.length} RESULTS</span>
                  <button
                    onClick={() => {
                      searchResults.forEach(r => {
                        if (r.status === 'idle') processLink(r.link, 'serper');
                      });
                    }}
                    className="text-xs bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700"
                  >
                    Process All
                  </button>
                </div>
                {searchResults.map((result, idx) => (
                  <div key={idx} className="p-3">
                    <div className="flex items-start gap-2">
                      <div className="flex-1 min-w-0">
                        <a
                          href={result.link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 text-sm font-medium hover:underline flex items-center gap-1"
                        >
                          <span className="truncate">{result.title}</span>
                          <ExternalLink className="h-3 w-3 flex-none" />
                        </a>
                        <span className="text-gray-400 text-xs block truncate">{result.link}</span>
                        {statusLabel(result)}
                      </div>
                      <div className="flex items-center gap-2 flex-none">
                        {statusIcon(result.status)}
                        {result.status === 'idle' && (
                          <button
                            onClick={() => {
                              setUrl(result.link);
                              processLink(result.link, 'serper');
                            }}
                            className="text-xs bg-gray-100 border px-2 py-1 rounded hover:bg-gray-200 text-gray-700 whitespace-nowrap"
                          >
                            Process
                          </button>
                        )}
                        {result.status === 'saved' && result.leadId && (
                          <a href="/leads" className="text-xs text-green-600 hover:underline">View Lead →</a>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right: Manual URL + Logs */}
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium mb-4">Manual URL Processing</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Target URL</label>
              <div className="mt-1 flex rounded-md shadow-sm">
                <input
                  type="text"
                  className="block w-full rounded-none rounded-l-md border-gray-300 sm:text-sm p-2 border"
                  placeholder="https://freelancer.com/projects/123"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && url && processLink(url, 'manual', true)}
                />
                <button
                  onClick={() => processLink(url, 'manual', true)}
                  disabled={processingUrl || !url}
                  className="relative -ml-px inline-flex items-center rounded-r-md border border-gray-300 bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:bg-blue-400"
                >
                  {processingUrl ? (
                    <><Loader2 className="h-4 w-4 animate-spin mr-1" />Processing...</>
                  ) : 'Process URL'}
                </button>
              </div>
            </div>

            {logs.length > 0 && (
              <div className="mt-4 bg-gray-900 rounded-md p-4 h-48 overflow-y-auto">
                {logs.map((log, i) => (
                  <div key={i} className="text-green-400 font-mono text-xs mb-1">&gt; {log}</div>
                ))}
              </div>
            )}

            {lastSavedLead && (
              <div className="mt-4 bg-green-50 border border-green-200 rounded-md p-4">
                <div className="font-medium text-green-800 text-sm mb-2">✅ Lead saved to database!</div>
                <div className="text-xs text-gray-600 space-y-1">
                  <div><span className="font-medium">Project:</span> {lastSavedLead.project_title || '—'}</div>
                  <div><span className="font-medium">Client:</span> {lastSavedLead.full_name || '—'}</div>
                  <div><span className="font-medium">Email:</span> {lastSavedLead.email || 'Not found on page'}</div>
                  <div><span className="font-medium">Quality:</span> {lastSavedLead.lead_quality || '—'}</div>
                </div>
                <a href="/leads" className="inline-block mt-3 text-xs text-blue-600 hover:underline font-medium">
                  → Go to Leads page to Approve &amp; Send Email
                </a>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
