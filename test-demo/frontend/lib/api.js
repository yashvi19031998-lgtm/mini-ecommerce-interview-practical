// Direct API client connecting Next.js to Python Backend Database (/api/...)
// 100% Dynamic - All leads, statuses, scrapers, and emails are processed directly by Python

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

async function apiFetch(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
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

// 10. Send Verification SMTP Test Email
export async function testSmtpEmail() {
  return await apiFetch('/api/settings/test-email', { method: 'POST' });
}

// 11. Trigger Supabase Cloud Sync
export async function triggerSupabaseSync() {
  return await apiFetch('/api/sync-supabase', { method: 'POST' });
}

// 12. Live Search Import via Python lead_importer
export async function searchImportLeads({ keyword, location, target_type, max_results }) {
  return await apiFetch('/api/import/search', {
    method: 'POST',
    body: JSON.stringify({ keyword, location, target_type, max_results })
  });
}

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
