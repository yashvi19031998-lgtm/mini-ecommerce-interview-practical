# QA Report — Lead Care → Lead Enrichment

**Date:** 2026-11-12 · **Build:** uncommitted working tree on `master` · **Result:** PASSED.

## English

### 1. Automated tests (Python, no network)
| Suite | Result |
|---|---|
| `test_lead_enrichment.py` (new) | 5/5 |
| Full regression (33 suites) | **496/496** |

**What the new tests cover:**
- **Candidates:** the filters (missing fields, a portal link not counted as a website, source, limits).
- **Enrich:**
  - proposals only for empty fields
  - the website check on a newly found website
  - a portal link never sent as the website
  - **enrich writes nothing**; bad input is rejected
- **Save:**
  - a valid e-mail, website and website check are filled, and the e-mail is normalised
  - skipped: already-filled fields, a non-fillable field (company_name), an invalid e-mail or phone, an unknown lead
  - **no old value changed**, no row removed
  - undo brings every old value back and empties the filled fields
  - a private-IP website is refused
- **API:** 401, candidates, run, save.

### 2. Browser QA (Playwright, real backend, **real 929 leads**) — 6/6 pass
| ID | Test | Result |
|---|---|---|
| LE01 | Find leads with a website missing e-mail / phone → "73 leads match — showing 10" | PASS |
| LE02 | Enrich 10 (2 batches) → 10 proposals; **file unchanged** | PASS |
| LE03 | Save 10 → 10 empty fields filled; 929 rows; **0 old values changed**; backup named | PASS |
| LE04 | Undo from Data Cleanup → history → **file identical** (md5 31caab71 = 31caab71) | PASS |
| LE05 | Mobile at 390 px | PASS |
| LE06 | No console errors | PASS |

**Live result:**
- The 10 leads gave website checks only, e.g. "old jQuery 1.11; copyright year 2019 (site not updated recently)" and "not mobile-friendly".
- There were no new e-mails or phones, because these sites had already been read when the leads were saved.

### 3. Bugs found and fixed
1. **An empty "missing" list** silently used the default instead of asking. It now returns a clear error.
2. **Website validation on save** did a DNS lookup through the URL guard, which refused real but unresolvable-at-that-moment domains. It now refuses localhost and private / loopback IP literals without any network call; the value is only stored, never fetched there.

### 4. Earlier in this session (related, already committed)
- The hourly auto-update had run with the old normaliser and blanked LEAD-00047's website and reformatted LEAD-00122's phone. Both were restored exactly (commit d9b7239).
- The owner's `next dev` broke after QA builds wrote into the shared `.next` folder. QA builds now use `NEXT_DIST_DIR=.next-qa`. The owner's dev server was restarted with a clean cache and serves HTTP 200.

### 5. Data safety
- The leads file is unchanged after QA (md5 `31caab71…`). The QA backup and log were removed.
- SMTP, IMAP and Supabase were off during QA. The owner's dev server on port 3000 was not stopped.

## ગુજરાતી
- **Tests:** browser QA 6/6 pass અને unit tests 496/496 pass.
- **સાચા 929 leads પર QA:**
  - Enrich થી file માં કંઈ ન બદલાયું.
  - Save થી 10 ખાલી fields ભરાયાં, અને જૂની કોઈ value ન બદલાઈ.
  - Undo પછી file બરાબર પહેલાં જેવી જ થઈ ગઈ.
- **પરિણામ:** આ 10 leads માં નવા email કે phone ન મળ્યા, ફક્ત website check મળ્યો.
- **તમારો નિર્ણય બાકી:** સાચા data પર હજી કંઈ save નથી કર્યું.
