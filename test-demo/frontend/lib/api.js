// Direct API client connecting Next.js to Python Backend Database (/api/...)
// 100% Dynamic - All leads, statuses, scrapers, and emails are processed directly by Python

import { supabase } from './supabase';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

// Attach the signed-in user's Supabase access token so the Python API can verify it.
async function authHeaders() {
  if (typeof window !== 'undefined') {
    const localUser = localStorage.getItem('lead_hub_demo_user');
    if (localUser) {
      return { 'X-Demo-User': 'true' };
    }
  }
  try {
    const { data } = await supabase.auth.getSession();
    const token = data?.session?.access_token;
    if (token) return { Authorization: `Bearer ${token}` };
  } catch (e) {
    // Supabase unreachable
  }
  return {};
}

async function apiFetch(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(await authHeaders()),
      ...(options.headers || {})
    }
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.error || `HTTP ${res.status}: ${res.statusText}`);
  }
  return await res.json();
}

// 1. Fetch Real Live Leads from Python DB (all_leads_master.csv)
export async function fetchLeads() {
  try {
    const data = await apiFetch('/api/leads');
    if (data && data.success) {
      return {
        success: true,
        leads: data.leads || [],
        total: data.total || (data.leads ? data.leads.length : 0),
        backendOnline: true
      };
    }
    return { success: false, leads: [], total: 0, backendOnline: false };
  } catch (err) {
    console.error('[API] Failed to fetch leads from Python backend:', err.message);
    return {
      success: false,
      leads: [],
      total: 0,
      backendOnline: false,
      error: 'Python backend offline. Run python app.py'
    };
  }
}

// 2. Patch Lead Workflow Status in Python DB
export async function patchLeadStatus(leadId, status) {
  return await apiFetch(`/api/leads/${leadId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status })
  });
}

// 3. Dispatch Single Cold Outreach Email via Python Gmail SMTP
export async function sendSingleEmail({ id, to, subject, message }) {
  return await apiFetch('/api/leads/send-email', {
    method: 'POST',
    body: JSON.stringify({ id, to, subject, message })
  });
}

// 4. Dispatch Bulk Cold Outreach Email via Python Gmail SMTP
// Bulk e-mail runs as a background job on the server (every mailbox is checked first, so it takes minutes).
// Starts the job, then polls it; onProgress(job) gets every update. Resolves with the finished job.
export async function sendBulkEmail({ lead_ids, subject, message, delay_ms = 1500 }, onProgress = null) {
  const start = await apiFetch('/api/leads/bulk-email', {
    method: 'POST',
    body: JSON.stringify({ lead_ids, subject, message, delay_ms })
  });
  let job = { ...start, processed: 0, sent: 0, failed: 0, not_verified: 0, skipped: 0, done: false, results: [] };
  if (onProgress) onProgress(job);
  let misses = 0;
  while (!job.done) {
    await new Promise(r => setTimeout(r, 1500));
    try {
      job = await apiFetch(`/api/leads/bulk-email/${encodeURIComponent(start.job_id)}`);
      misses = 0;
    } catch (err) {
      if (++misses >= 5) throw new Error(`Lost contact with the server while sending (${err.message}). Mails already sent stay sent.`);
      continue;
    }
    if (onProgress) onProgress(job);
  }
  return job;
}

// 5. Query Real-Time Scraper Engine Status & Live Logs
export async function fetchScraperStatus() {
  try {
    const res = await apiFetch('/api/scraper/status');
    return {
      running: !!res.running,
      logs: res.logs || []
    };
  } catch {
    return { running: false, logs: [] };
  }
}

// 6. Launch Background Scraper via Python Subprocess
export async function startScraper(mode = 'quick') {
  return await apiFetch('/api/scraper/start', {
    method: 'POST',
    body: JSON.stringify({ mode })
  });
}

// 6b. Freelance Scraper page: full run status (running, mode of the run the logs belong to, logs)
export async function fetchScraperRun() {
  return await apiFetch('/api/scraper/status');
}

// 7. Terminate Background Scraper
export async function stopScraper() {
  return await apiFetch('/api/scraper/stop', {
    method: 'POST'
  });
}

// 8. Fetch Company & SMTP Settings from Python (company_settings.json)
export async function fetchSettings() {
  try {
    return await apiFetch('/api/settings');
  } catch {
    return {
      success: false,
      settings: {},
      formattedSignature: ''
    };
  }
}

// 9. Save Company & SMTP Settings to Python
export async function saveSettings(settings) {
  return await apiFetch('/api/settings', {
    method: 'POST',
    body: JSON.stringify(settings)
  });
}

// 9b. Which API keys are set in .env (status only, never the values)
export async function fetchApiKeysStatus() {
  return await apiFetch('/api/settings/api-keys');
}

// 10. Send Verification SMTP Test Email
export async function testSmtpEmail() {
  return await apiFetch('/api/settings/test-email', { method: 'POST' });
}

// 11. Trigger Supabase Cloud Sync
export async function triggerSupabaseSync() {
  return await apiFetch('/api/sync-supabase', { method: 'POST' });
}

// 12. (Live Search moved to Scraping / Mining -> Search Engines, see 36-39 below)

// 13. Commit Extracted Leads to Master CSV & Supabase
export async function commitImportedLeads(leads, sendOutreachEmail = false) {
  return await apiFetch('/api/import/commit', {
    method: 'POST',
    body: JSON.stringify({ leads, send_outreach_email: sendOutreachEmail })
  });
}

// 14. Raw Text & Website Contact Scraping via Python lead_importer
export async function importRawTextData(text, crawl_urls = true) {
  return await apiFetch('/api/import/raw-text', {
    method: 'POST',
    body: JSON.stringify({ text, crawl_urls })
  });
}

// 16. Job Portal Scraper: portal catalog + Indian states for the form
export async function fetchJobPortals() {
  return await apiFetch('/api/job-portals');
}

// 17. Job Portal Scraper: search the selected portals (can take 10-60 seconds)
export async function searchJobPortals({ titles, state, portals, refresh = false }) {
  return await apiFetch('/api/job-portals/search', {
    method: 'POST',
    body: JSON.stringify({ titles, state, portals, refresh })
  });
}

// 18. Job Portal Scraper: save selected job postings as leads (hiring company = lead)
export async function saveJobsToLeads(jobs) {
  return await apiFetch('/api/job-portals/save', {
    method: 'POST',
    body: JSON.stringify({ jobs })
  });
}

// 19. FollowUp History: counts for overdue / today / upcoming follow-ups
export async function fetchFollowupSummary() {
  return await apiFetch('/api/followups/summary');
}

// 20. FollowUp History: pending follow-ups ('all' | 'overdue' | 'today' | 'upcoming' | 'later')
export async function fetchFollowupQueue(bucket = 'all') {
  return await apiFetch(`/api/followups/queue?bucket=${encodeURIComponent(bucket)}`);
}

// New leads nobody has contacted yet, highest score first. band = all|high|medium|low
export async function fetchUntouchedLeads({ band = 'all', hasEmail = false } = {}) {
  return await apiFetch(`/api/followups/untouched?band=${encodeURIComponent(band)}&has_email=${hasEmail ? 1 : 0}`);
}

// 20b. Reply Today: fresh buyer posts with no e-mail (answer them on Reddit / Freelancer / HN by hand)
export async function fetchReplyToday({ days = 3 } = {}) {
  return await apiFetch(`/api/followups/reply-today?days=${encodeURIComponent(days)}`);
}

export async function fetchReplyDraft(leadId) {
  return await apiFetch('/api/followups/reply-draft', { method: 'POST', body: JSON.stringify({ lead_id: leadId }) });
}

export async function markReplyDone(leadId, text = '') {
  return await apiFetch('/api/followups/reply-done', { method: 'POST', body: JSON.stringify({ lead_id: leadId, text }) });
}

// 21. FollowUp History: activity feed (newest first)
export async function fetchFollowupHistory({ leadId = '', types = [], q = '', limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({ lead_id: leadId, types: types.join(','), q, limit, offset });
  return await apiFetch(`/api/followups/history?${params.toString()}`);
}

// 22. FollowUp History: one lead's timeline + its pending follow-up
export async function fetchLeadTimeline(leadId) {
  return await apiFetch(`/api/leads/${encodeURIComponent(leadId)}/timeline`);
}

// 23. FollowUp History: log a call / meeting / note / WhatsApp / email (+ optional next follow-up)
export async function logFollowupActivity(payload) {
  return await apiFetch('/api/followups/activities', { method: 'POST', body: JSON.stringify(payload) });
}

// 24. FollowUp History: plan the next follow-up for a lead
export async function scheduleFollowup({ lead_id, due_at, note }) {
  return await apiFetch('/api/followups/schedule', { method: 'POST', body: JSON.stringify({ lead_id, due_at, note }) });
}

// 25. FollowUp History: mark done / cancel / reschedule a follow-up
export async function updateFollowup(activityId, action, dueAt = '') {
  return await apiFetch(`/api/followups/${encodeURIComponent(activityId)}`, {
    method: 'PATCH',
    body: JSON.stringify({ action, due_at: dueAt })
  });
}

// 26. FollowUp History: import emails sent before this feature existed (safe to repeat)
export async function importSentEmailsHistory() {
  return await apiFetch('/api/followups/import-sent-emails', { method: 'POST' });
}

// 27. FollowUp Phase 2: sequence settings + follow-ups that are due (with email preview)
export async function fetchFollowupSequence() {
  return await apiFetch('/api/followups/sequence');
}

// 28. FollowUp Phase 2: send selected due follow-ups now
export async function sendSequenceFollowups(leadIds) {
  return await apiFetch('/api/followups/sequence/send', { method: 'POST', body: JSON.stringify({ lead_ids: leadIds }) });
}

// 29. FollowUp Phase 2: stop the sequence for one lead
export async function stopSequence(leadId, reason = '') {
  return await apiFetch('/api/followups/sequence/stop', { method: 'POST', body: JSON.stringify({ lead_id: leadId, reason }) });
}

// 30. FollowUp Phase 2: read Gmail for replies / bounces / opt-outs now
export async function checkGmailReplies() {
  return await apiFetch('/api/followups/check-replies', { method: 'POST' });
}

// 31. FollowUp Phase 2: reply-rate report
export async function fetchFollowupReport() {
  return await apiFetch('/api/followups/report');
}

// 32. FollowUp Phase 2: follow-up email templates (get / save / reset to default)
export async function fetchFollowupTemplates() {
  return await apiFetch('/api/followups/templates');
}
export async function saveFollowupTemplates(templates) {
  return await apiFetch('/api/followups/templates', { method: 'PUT', body: JSON.stringify({ templates }) });
}
export async function resetFollowupTemplates() {
  return await apiFetch('/api/followups/templates', { method: 'DELETE' });
}

// 33. CRM Sources: source catalog (directories + contact databases) and states
export async function fetchCrmSources() {
  return await apiFetch('/api/crm-sources');
}

// 34. CRM Sources: search selected sources (can take up to a minute)
export async function searchCrmSources({ keywords, titles, state, city, sources, refresh = false }) {
  return await apiFetch('/api/crm-sources/search', {
    method: 'POST', body: JSON.stringify({ keywords, titles, state, city, sources, refresh })
  });
}

// 35. CRM Sources: save selected businesses/contacts as leads
export async function saveCrmResultsToLeads(results) {
  return await apiFetch('/api/crm-sources/save', { method: 'POST', body: JSON.stringify({ results }) });
}

// 36. Scraping / Mining -> Search Engines: engines, search types, states
export async function fetchSearchEngineOptions() {
  return await apiFetch('/api/search-engine');
}

// 37. Search Engines: run the search (queries run one by one; can take up to a minute)
export async function runSearchEngine(params) {
  return await apiFetch('/api/search-engine/search', { method: 'POST', body: JSON.stringify(params) });
}

// 38. Deep Search: open result websites for email / phone / socials (max 10 per call)
export async function runDeepSearch({ items, engine = 'auto', use_hunter = false, place = '' }) {
  return await apiFetch('/api/search-engine/deep', { method: 'POST', body: JSON.stringify({ items, engine, use_hunter, place }) });
}

// 39. Search Engines: save selected results as leads (optional intro email)
export async function saveSearchEngineResults({ results, send_outreach_email = false }) {
  return await apiFetch('/api/search-engine/save', { method: 'POST', body: JSON.stringify({ results, send_outreach_email }) });
}

// 40. Scraping / Mining -> Global Directories: source catalog + countries
export async function fetchGlobalDirectories() {
  return await apiFetch('/api/global-directories');
}

// 41. Global Directories: search ({ keywords, audience, country, region, city, sources, refresh })
export async function searchGlobalDirectories(params) {
  return await apiFetch('/api/global-directories/search', { method: 'POST', body: JSON.stringify(params) });
}

// 42. Global Directories: save selected results as leads
export async function saveGlobalDirectoryResults(results) {
  return await apiFetch('/api/global-directories/save', { method: 'POST', body: JSON.stringify({ results }) });
}

// 43. Scraping / Mining -> Google Maps: sources + states
export async function fetchMapsSources() {
  return await apiFetch('/api/maps');
}

// 44. Google Maps: search ({ keywords, audience, state, city, sources, min_rating, website, refresh })
export async function searchMaps(params) {
  return await apiFetch('/api/maps/search', { method: 'POST', body: JSON.stringify(params) });
}

// 45. Google Maps: save selected businesses as leads
export async function saveMapsResults(results) {
  return await apiFetch('/api/maps/save', { method: 'POST', body: JSON.stringify({ results }) });
}

// 46. Scraping / Mining -> Ecommerce Platforms: sources, engines, states
export async function fetchEcommerceSources() {
  return await apiFetch('/api/ecommerce');
}

// 47. Ecommerce: search ({ keywords, audience, state, city, sources, engine, refresh })
export async function searchEcommerce(params) {
  return await apiFetch('/api/ecommerce/search', { method: 'POST', body: JSON.stringify(params) });
}

// 48. Ecommerce: save selected stores / sellers as leads
export async function saveEcommerceResults(results) {
  return await apiFetch('/api/ecommerce/save', { method: 'POST', body: JSON.stringify({ results }) });
}

// 49. Scraping / Mining -> Real Estate: sources, engines, states
export async function fetchRealEstateSources() {
  return await apiFetch('/api/realestate');
}

// 50. Real Estate: search ({ keywords, audience, state, city, sources, looking_for, engine, refresh })
export async function searchRealEstate(params) {
  return await apiFetch('/api/realestate/search', { method: 'POST', body: JSON.stringify(params) });
}

// 51. Real Estate: save selected builders / agents as leads
export async function saveRealEstateResults(results) {
  return await apiFetch('/api/realestate/save', { method: 'POST', body: JSON.stringify({ results }) });
}

// Scraping / Mining -> SocialMedia: catalog
export async function fetchSocialSources() {
  return await apiFetch('/api/social');
}

// SocialMedia: search
export async function searchSocial(params) {
  return await apiFetch('/api/social/search', { method: 'POST', body: JSON.stringify(params) });
}

// SocialMedia: save selected results as leads
export async function saveSocialResults(results) {
  return await apiFetch('/api/social/save', { method: 'POST', body: JSON.stringify({ results }) });
}

// Scraping / Mining -> AdLibrary: catalog
export async function fetchAdLibrarySources() {
  return await apiFetch('/api/adlibrary');
}

// AdLibrary: search
export async function searchAdLibrary(params) {
  return await apiFetch('/api/adlibrary/search', { method: 'POST', body: JSON.stringify(params) });
}

// AdLibrary: save selected results as leads
export async function saveAdLibraryResults(results) {
  return await apiFetch('/api/adlibrary/save', { method: 'POST', body: JSON.stringify({ results }) });
}

// Scraping / Mining -> WhatsAppGroups: catalog
export async function fetchWhatsAppSources() {
  return await apiFetch('/api/whatsapp');
}

// WhatsAppGroups: search
export async function searchWhatsApp(params) {
  return await apiFetch('/api/whatsapp/search', { method: 'POST', body: JSON.stringify(params) });
}

// WhatsAppGroups: save selected results as leads
export async function saveWhatsAppResults(results) {
  return await apiFetch('/api/whatsapp/save', { method: 'POST', body: JSON.stringify({ results }) });
}

// Data Extraction -> Indian Directories: catalog
export async function fetchIndianDirectorySources() {
  return await apiFetch('/api/indian-directories');
}

// IndianDirectory: search
export async function searchIndianDirectories(params) {
  return await apiFetch('/api/indian-directories/search', { method: 'POST', body: JSON.stringify(params) });
}

// IndianDirectory: save selected results as leads
export async function saveIndianDirectoryResults(results) {
  return await apiFetch('/api/indian-directories/save', { method: 'POST', body: JSON.stringify({ results }) });
}

// Data Extraction -> Corporate Registries: catalog (company types, statuses, ages, industries)
export async function fetchCorporateRegistryOptions() {
  return await apiFetch('/api/corporate-registries');
}

// Corporate Registries: search (mode: company | pvtltd | gst_find | gst_check)
export async function searchCorporateRegistries(params) {
  return await apiFetch('/api/corporate-registries/search', { method: 'POST', body: JSON.stringify(params) });
}

// Corporate Registries: company page details for up to 10 companies
export async function fetchCompanyDetails(items) {
  return await apiFetch('/api/corporate-registries/details', { method: 'POST', body: JSON.stringify({ items }) });
}

// Corporate Registries: save selected results as leads
export async function saveCorporateRegistryResults(results) {
  return await apiFetch('/api/corporate-registries/save', { method: 'POST', body: JSON.stringify({ results }) });
}

// Bulk Contacts: limits
export async function fetchBulkContactsOptions() {
  return await apiFetch('/api/bulk-contacts');
}

// Bulk Contacts: contacts from up to 10 websites per call
export async function bulkWebsiteContacts(urls) {
  return await apiFetch('/api/bulk-contacts/websites', { method: 'POST', body: JSON.stringify({ urls }) });
}

// Bulk Contacts: verify e-mail addresses (syntax, typos, disposable, role, MX)
export async function bulkVerifyEmails(emails) {
  return await apiFetch('/api/bulk-contacts/emails', { method: 'POST', body: JSON.stringify({ emails }) });
}

// Bulk Contacts: clean / classify phone numbers
export async function bulkCleanPhones(text) {
  return await apiFetch('/api/bulk-contacts/phones', { method: 'POST', body: JSON.stringify({ text }) });
}

// Bulk Contacts: CSV import - preview (headers + guessed mapping), check (normalise + duplicates)
export async function bulkImportPreview(text) {
  return await apiFetch('/api/bulk-contacts/import/preview', { method: 'POST', body: JSON.stringify({ text }) });
}

export async function bulkImportCheck(text, mapping, source) {
  return await apiFetch('/api/bulk-contacts/import/check', { method: 'POST', body: JSON.stringify({ text, mapping, source }) });
}

// Bulk Contacts: save rows as leads (kind: 'import' | 'websites')
export async function bulkSaveContacts(kind, rows) {
  return await apiFetch('/api/bulk-contacts/save', { method: 'POST', body: JSON.stringify({ kind, rows }) });
}

// Web Crawler: limits
export async function fetchWebCrawlerOptions() {
  return await apiFetch('/api/web-crawler');
}

// Web Crawler: run a tool ('site' | 'links' | 'keywords' | 'sitemap')
export async function runWebCrawler(tool, params) {
  return await apiFetch(`/api/web-crawler/${tool}`, { method: 'POST', body: JSON.stringify(params) });
}

// File Uploads: supported types + OCR status
export async function fetchFileUploadOptions() {
  return await apiFetch('/api/file-uploads');
}

// File Uploads: send one file (base64) -> contacts (checked) or Excel sheets as CSV
export async function parseUploadedFile(name, data) {
  return await apiFetch('/api/file-uploads/parse', { method: 'POST', body: JSON.stringify({ name, data }) });
}

// Utilities: Website Analyzer (up to 5 sites per request)
export async function analyzeWebsites(urls) {
  return await apiFetch('/api/utilities/website-analyzer', { method: 'POST', body: JSON.stringify({ urls }) });
}

// Domain Tools: limits and domain endings
export async function fetchDomainToolOptions() {
  return await apiFetch('/api/domain-tools');
}

// Domain Tools: run a tool ('age' | 'dns' | 'new' | 'available')
export async function runDomainTool(tool, params) {
  return await apiFetch(`/api/domain-tools/${tool}`, { method: 'POST', body: JSON.stringify(params) });
}

// Lead Care: Data Cleanup (scan = dry run, apply = fill empty fields with backup + log, undo)
export async function scanLeadCleanup() {
  return await apiFetch('/api/lead-care/cleanup');
}

export async function applyLeadCleanup(fixes) {
  return await apiFetch('/api/lead-care/cleanup/apply', { method: 'POST', body: JSON.stringify({ fixes }) });
}

export async function undoLeadCleanup(logId) {
  return await apiFetch('/api/lead-care/cleanup/undo', { method: 'POST', body: JSON.stringify({ log_id: logId }) });
}

// Lead Care: Lead Enrichment (candidates -> run Deep Search on up to 5 -> save chosen proposals, fill-only)
export async function findEnrichmentCandidates(params) {
  return await apiFetch('/api/lead-care/enrichment/candidates', { method: 'POST', body: JSON.stringify(params) });
}

export async function runLeadEnrichment(leadIds, steps) {
  return await apiFetch('/api/lead-care/enrichment/run', { method: 'POST', body: JSON.stringify({ lead_ids: leadIds, steps }) });
}

export async function saveLeadEnrichment(changes) {
  return await apiFetch('/api/lead-care/enrichment/save', { method: 'POST', body: JSON.stringify({ changes }) });
}

// 49. 1-Hour Auto Scraper & Scheduler API
export async function fetchSchedulerStatus() {
  return await apiFetch('/api/scheduler/status');
}

export async function triggerSchedulerJob() {
  return await apiFetch('/api/scheduler/trigger', { method: 'POST' });
}

// 15. Download master CSV (authenticated fetch, then save as a file)
export async function downloadLeadsCsv() {
  const res = await fetch(`${BASE_URL}/api/export-csv`, { headers: await authHeaders() });
  if (!res.ok) throw new Error(`Export failed: HTTP ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'sangeeta_infotech_leads.csv';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// Helper: Build WhatsApp click-to-chat URL
export function buildWhatsAppLink(phone, companyName, template) {
  if (!phone) return null;
  const cleanPhone = phone.replace(/[^\d+]/g, '');
  const finalPhone = cleanPhone.startsWith('+')
    ? cleanPhone.slice(1)
    : (cleanPhone.length === 10 ? `91${cleanPhone}` : cleanPhone);

  const msg = (template || `Hi ${companyName || 'there'}, I came across your business and wanted to connect regarding dedicated software development support from Sangeeta Infotech. Let me know if you are open to a quick chat!`)
    .replace('{company}', companyName || 'your company')
    .replace('{name}', companyName || 'Team');

  return `https://wa.me/${finalPhone}?text=${encodeURIComponent(msg)}`;
}

// ---------------------------------------------------------------------------
// 16. Reports Engine API (reports_engine.py)
// ---------------------------------------------------------------------------

function toReportQueryString(filters = {}) {
  const params = new URLSearchParams();
  if (filters.preset) params.set('preset', filters.preset);
  if (filters.date_from) params.set('date_from', filters.date_from);
  if (filters.date_to) params.set('date_to', filters.date_to);
  if (filters.source && filters.source !== 'all') params.set('source', filters.source);
  if (filters.status && filters.status.toUpperCase() !== 'ALL') params.set('status', filters.status);
  const q = params.toString();
  return q ? `?${q}` : '';
}

export async function fetchReportOptions() {
  return await apiFetch('/api/reports/options');
}

export async function fetchReportSummary(filters = {}) {
  return await apiFetch(`/api/reports/summary${toReportQueryString(filters)}`);
}

export async function fetchReportScrapers(filters = {}) {
  return await apiFetch(`/api/reports/scrapers${toReportQueryString(filters)}`);
}

export async function fetchReportSources(filters = {}) {
  return await apiFetch(`/api/reports/sources${toReportQueryString(filters)}`);
}

export async function fetchReportFollowups(filters = {}, quietDays = 5) {
  const baseQ = toReportQueryString(filters);
  const sep = baseQ ? '&' : '?';
  const q = `${baseQ}${sep}quiet_days=${encodeURIComponent(quietDays)}`;
  return await apiFetch(`/api/reports/followups${q}`);
}

export async function fetchReportPipeline(filters = {}) {
  return await apiFetch(`/api/reports/pipeline${toReportQueryString(filters)}`);
}

export async function fetchReportOutreach(filters = {}) {
  return await apiFetch(`/api/reports/outreach${toReportQueryString(filters)}`);
}

export async function fetchReportDataHealth() {
  return await apiFetch('/api/reports/data-health');
}

export async function fetchReportActivity(day) {
  const q = day ? `?day=${encodeURIComponent(day)}` : '';
  return await apiFetch(`/api/reports/activity${q}`);
}


// In-app chat assistant (chat_assistant.py): read-only answers about leads, e-mails, scrapers
export async function askAssistant(message) {
  return await apiFetch('/api/chat', { method: 'POST', body: JSON.stringify({ message }) });
}
