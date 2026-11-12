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
export async function sendBulkEmail({ lead_ids, subject, message, delay_ms = 1500 }) {
  return await apiFetch('/api/leads/bulk-email', {
    method: 'POST',
    body: JSON.stringify({ lead_ids, subject, message, delay_ms })
  });
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
