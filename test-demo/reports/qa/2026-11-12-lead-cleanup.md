# QA Report — Lead Care → Data Cleanup

**Date:** 2026-11-12 · **Build:** uncommitted working tree on `master` · **Result:** PASSED.

## English

### 1. Owner's rule
"Do not delete anything old." The module therefore only fills empty fields, backs up first, logs every change and can undo. QA proved this on the real 921 leads: apply, then undo, and the file matches byte for byte.

### 2. Found before building: silent changes to old data (fixed)
A read-only check showed that `MasterLeadRegistry` load + save, with no edits at all, changed **2 cells** of the real leads file:
- the `.gov.in` website of LEAD-00047 was **blanked**;
- the phone list of LEAD-00122 was reformatted.

This happened on every save by any module and by the hourly scraper, whenever a normalising rule had changed. The fix keeps the stored values exactly and uses the normalised copy only for duplicate matching. Load + save now changes **0 cells**. A regression test covers it.

### 3. Automated tests (Python, no network)
| Suite | Result |
|---|---|
| `test_lead_cleanup.py` (new) | 8/8 |
| Full regression (32 suites) | **491/491** |

**What the new tests cover:**
- **Lossless file:** the load + save round trip; duplicate matching still normalised.
- **Dry run:**
  - the 3 fixes, with all their safety rules (domain must match the lead, free mail, shared / platform domains)
  - `.co.in` kept
  - the shared-contacts and format reports
  - **the scan writes nothing**
- **Apply:**
  - only blanks filled, **no row removed, no filled cell changed**
  - full backup; change log
  - a chained fill on the next run; then nothing left
- **Undo:**
  - values and dates restored
  - **a value edited later is kept**
  - double undo, bad or path-like log ids rejected
- **Backups:** pruned to the limit.
- **API:** 401 / 400 / apply / undo.

### 4. Browser QA (Playwright, real backend, **real leads file**) — 5/5 pass
| ID | Test | Result |
|---|---|---|
| LC01 | Dry run: 921 leads; 716 no e-mail / 709 no phone / 714 no website; "Fill 42 empty fields"; change list shown; **file unchanged** | PASS |
| LC02 | Apply → 42 cells filled; 921 = 921 rows; **0 filled cells changed**; backup named | PASS |
| LC03 | Undo → 42 fields emptied again; **every cell equals the original** (md5 963d94bc = 963d94bc) | PASS |
| LC04 | Mobile at 390 px, no sideways scroll | PASS |
| LC05 | No console errors | PASS |

The QA-made backup and log were removed afterwards, so the history is empty for the owner. The data was **not** left cleaned: the owner decides when to apply.

### 5. Other findings
- **Website-from-e-mail false match:** a first draft would have given "ZoomInfo Technologies LLC" the website pagerduty.com, an e-mail of another company in its job post. Now the domain's name must appear in the lead itself, which brought the count from 50 down to 40.
- **Free-mail domains** (gmail.com) were listed as "shared contacts"; they are excluded now.
- **QA harness:** two Flask processes were listening on port 5000. A stale one answered 404. The stop script now stops every listener; the app code was not at fault.

### 6. Data safety
- The leads file is unchanged after QA (md5 `963d94bc…`).
- `backups/` contains only the owner's tracked `pre_migration/` folder. Cleanup backups and logs are git-ignored (`backups/all_leads_master_*.csv`, `backups/cleanup_*.json`).

## ગુજરાતી
- **Tests:** browser QA 5/5 pass અને unit tests 491/491 pass.
- **સાચા 921 leads પર QA:**
  - Apply થી 42 ખાલી fields ભરાયાં, એક પણ row કે ભરેલું field બદલાયું નહીં.
  - Undo પછી file બરાબર પહેલાં જેવી જ થઈ ગઈ.
- **મહત્ત્વનો સુધારો:** leads file save થતી વખતે જૂની values ચૂપચાપ બદલાતી કે ખાલી થતી હતી (જેમ કે `.gov.in` website). હવે એ નથી થતું.
- **તમારો નિર્ણય બાકી:** સાચા data પર cleanup હજી apply નથી કર્યો. Page પર "Fill 42 empty fields" દબાવો ત્યારે થશે.
