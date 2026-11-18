// One vocabulary for leads across Today, Leads (table + board) and the lead panel.
// The ids match lead_status.py (next_action) and the band rule there (hot 7-10, warm 4-6, cold 0-3).

export const ACTIONS = {
  replied:         { label: 'Reply now',         short: 'Reply',     verb: 'Reply',       tone: 'green', group: 'todo', hint: 'They answered your message' },
  followup_due:    { label: 'Follow-up due',     short: 'Follow-up', verb: 'Follow up',   tone: 'red',   group: 'todo', hint: 'A follow-up you planned is due' },
  call_pending:    { label: 'Call or WhatsApp',  short: 'Call',      verb: 'Call',        tone: 'amber', group: 'todo', hint: 'No e-mail, but a phone number' },
  message_pending: { label: 'Reply on post',     short: 'Message',   verb: 'Reply on post', tone: 'amber', group: 'todo', hint: 'Only reachable on Reddit, Freelancer or HN' },
  no_reply:        { label: 'No reply yet',      short: 'Chase',     verb: 'Follow up',   tone: 'amber', group: 'todo', hint: 'Contacted 4+ days ago, no answer' },
  mail_pending:    { label: 'In mail queue',     short: 'Queued',    verb: 'Send now',    tone: 'blue',  group: 'auto', hint: 'Auto-mail sends it in office hours' },
  waiting:         { label: 'Waiting for reply', short: 'Waiting',   verb: '',            tone: 'gray',  group: 'wait', hint: 'Contacted in the last 4 days' },
  old_post:        { label: 'Post too old',      short: 'Too old',   verb: '',            tone: 'gray',  group: 'done', hint: 'The post is over 14 days old' },
  no_contact:      { label: 'No contact found',  short: 'No contact', verb: '',           tone: 'gray',  group: 'done', hint: 'No e-mail, phone or post' },
  not_fit:         { label: 'Not a fit',         short: 'Not a fit', verb: '',            tone: 'gray',  group: 'done', hint: 'Job seeker, agency or directory' },
  closed:          { label: 'Closed',            short: 'Closed',    verb: '',            tone: 'gray',  group: 'done', hint: 'Won, lost or asked to stop' },
};
export const ACTION_ORDER = Object.keys(ACTIONS);
export const TODO_ACTIONS = ACTION_ORDER.filter(a => ACTIONS[a].group === 'todo');

export const BANDS = {
  hot:      { label: 'Hot',  range: '7-10', tone: 'red' },
  warm:     { label: 'Warm', range: '4-6',  tone: 'amber' },
  cold:     { label: 'Cold', range: '0-3',  tone: 'blue' },
  unscored: { label: 'Not scored', range: '', tone: 'gray' },
};

// Outcome of the conversation (stored in the lead's status column). EMAIL_SENT is written by the mailer.
export const OUTCOMES = ['NEW', 'EMAIL_SENT', 'CONTACTED', 'REPLIED', 'MEETING', 'WON', 'LOST', 'DISQUALIFIED'];
export const OUTCOME_LABEL = {
  NEW: 'New', EMAIL_SENT: 'Mailed', CONTACTED: 'Contacted', REPLIED: 'Replied', MEETING: 'Meeting',
  WON: 'Won', LOST: 'Lost', DISQUALIFIED: 'Disqualified',
};

const clean = (v) => {
  const s = String(v ?? '').trim();
  return ['nan', 'n/a', 'none', 'null'].includes(s.toLowerCase()) ? '' : s;
};

export const leadName = (l) => clean(l.company_name || l['Company Name']) || clean(l.full_name) || '(no name)';
export const leadAbout = (l) => clean(l.ai_requirement) || clean(l.ai_summary) || clean(l.description);
export const leadEmail = (l) => {
  const e = clean(l.email || l.Email).split(',')[0].trim().toLowerCase();
  return e.includes('@') ? e : '';
};
export const leadPhone = (l) => {
  const p = clean(l.mobile_number || l['Mobile Number']).split(/[,;/|]/)[0].trim();
  return p.replace(/\D/g, '').length >= 8 ? p : '';
};
export const whatsappUrl = (phone) => {
  let d = String(phone || '').replace(/\D/g, '');
  if (d.length === 10) d = `91${d}`;
  else if (d.length === 11 && d.startsWith('0')) d = `91${d.slice(1)}`;
  return d.length >= 11 ? `https://wa.me/${d}` : '';
};
export const postUrl = (l) => {
  const u = clean(l.source_url);
  return u.startsWith('http') ? u : '';
};
export const websiteUrl = (l) => {
  const w = clean(l.website || l['Website URL']);
  if (!w) return '';
  return w.startsWith('http') ? w : `https://${w}`;
};
export const leadScore = (l) => {
  for (const k of ['ai_score', 'intent_score']) {
    const n = parseFloat(l[k]);
    if (!Number.isNaN(n)) return Math.max(0, Math.min(10, Math.round(n)));
  }
  return null;
};
export const leadOutcome = (l) => {
  const s = clean(l.status || l.Status).toUpperCase();
  return OUTCOMES.includes(s) ? s : 'NEW';
};
// "query | Search Engine (query)" -> "Search Engine"; "Job Portal (Foundit (Monster))" -> "Job Portal"
export const leadSource = (l) => {
  const s = clean(l.source || l.Source);
  return s.split('|').pop().split('(')[0].replace(/["']/g, '').trim() || 'Unknown';
};
export const foundDate = (l) => clean(l.first_seen_at).slice(0, 10);

export function niceDate(stamp) {
  const s = clean(stamp);
  if (!s) return '';
  const d = new Date(s.replace(' ', 'T'));
  if (Number.isNaN(d.getTime())) return s.slice(0, 10);
  const days = Math.floor((Date.now() - d.getTime()) / 86400000);
  if (days <= 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days} days ago`;
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}
