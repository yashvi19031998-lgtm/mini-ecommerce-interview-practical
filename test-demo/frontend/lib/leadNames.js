// Names to use inside outreach text. Mirrors followup_sequence.py (company_for_email / outreach_names).
//
// Many saved leads are job posts, so their "company name" is really a post title
// ("[Hiring] Senior React dev - Remote (USA only)"). That must never be written into a message:
// "Hi [Hiring] Senior React dev - Remote (USA only) Team" is what the recipient would read first.

const POST_TITLE_MARKERS = [':', '|', '[', '(', ' - ', 'hiring', 'looking for', 'show hn', 'ask hn', 'needed', 'wanted'];

export function looksLikeCompanyName(name) {
  const n = String(name || '').trim();
  if (!n || n === 'N/A' || n.length > 40) return false;
  const lower = n.toLowerCase();
  return !POST_TITLE_MARKERS.some(m => lower.includes(m));
}

// { isCompany, greeting, company, subjectFor }
//   real company : greeting "Acme Foods Team", company "Acme Foods"
//   post title   : greeting "there",           company "your team"
export function outreachNames(name) {
  const n = String(name || '').trim();
  if (looksLikeCompanyName(n)) return { isCompany: true, greeting: `${n} Team`, company: n, subjectFor: n };
  return { isCompany: false, greeting: 'there', company: 'your team', subjectFor: 'your team' };
}
