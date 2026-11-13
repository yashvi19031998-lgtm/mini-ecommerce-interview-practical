# Reports & Analytics Module Documentation / રિપોર્ટ્સ અને એનાલિટિક્સ મોડ્યુલ દસ્તાવેજીકરણ

*Bilingual Documentation: English and Gujarati (દ્વિભાષી દસ્તાવેજીકરણ: અંગ્રેજી અને ગુજરાતી)*

---

## 1. Overview / સંક્ષિપ્ત પરિચય

### English
The **Reports & Analytics** module is an executive intelligence suite designed for LeadsGen AI. It delivers real-time visibility into lead acquisition, data health, scraper infrastructure performance, pipeline progression, and follow-up activities without modifying underlying datasets.

The system adheres to the core principle: **"Not a single lead's follow-up may be missed."**

Key capabilities include:
- **R1: Executive Summary** — High-level KPI cards with automatic comparison to the previous period of identical length, zero-filled daily discovery/email trends, and instant attention alerts.
- **R2: Scrapers Infrastructure Report** — Granular metrics per scraper script, total execution logs, yield efficiency, duplicate ratios, and operational health flags (`failed_last_run`, `not_producing`, `stale_scrapers`).
- **R3: Source Quality Analysis** — Quality metrics by source family, hot lead yield (AI Score ≥ 7), contact and reply rates, and automatic flags for low-value sources.
- **R4: Follow-up Watchlist ("No Lead Missed")** — Prioritized queue across 8 critical follow-up categories, full Do-Not-Contact (DNC) list exclusion, and direct action triggers.
- **R5: Pipeline & Conversion Funnel** — Complete stage progression across all 8 pipeline states with zero-safety, conversion rates, and stagnant lead tracking (>14 days).
- **R6: Multi-Channel Outreach Analytics** — Cold outreach attribution across channels (`auto`, `manual`, `bulk`, `sequence`, `other`, `before_tracking`) and top subject line rankings.
- **R7: CRM Data Health & Hygiene** — Audit across 9 data completeness rules (missing email, phone, website, unqualified leads, duplicate entries) with sample lead IDs.
- **R8: Daily Activity Audit Log** — Chronological day-by-day stream of scraper executions, lead additions, sent emails, and touchpoints.

### ગુજરાતી (Gujarati)
**રિપોર્ટ્સ અને એનાલિટિક્સ** મોડ્યુલ એ LeadsGen AI માટેનું એક વ્યાપક અને પાવરફુલ એક્ઝિક્યુટિવ મોડ્યુલ છે. આ મોડ્યુલ લીડ પ્રાપ્તિ, ડેટાની ગુણવત્તા, સ્ક્રેપર સિસ્ટમની વિશ્વસનીયતા, સેલ્સ પાઇપલાઇન અને ફોલો-અપ પ્રવૃત્તિઓની રીઅલ-ટાઇમ માહિતી પૂરી પાડે છે.

મુખ્ય સિદ્ધાંત: **"એક પણ લીડનો ફોલો-અપ છૂટવો ન જોઈએ."**

મુખ્ય સુવિધાઓ:
- **R1: એક્ઝિક્યુટિવ સમરી** — અગાઉના સમયગાળા સાથે સરખામણી ધરાવતા ૧૨ મુખ્ય KPI કાર્ડ્સ, દૈનિક ગ્રાફ અને તાત્કાલિક ધ્યાનની જરૂર હોય તેવી બાબતો.
- **R2: સ્ક્રેપર રિપોર્ટ** — દરેક સ્ક્રેપર સ્ક્રિપ્ટ દીઠ સંગ્રહિત રેકોર્ડ્સ, નવી લીડ્સ, ડુપ્લિકેટ દર, અને ઓપરેશનલ ફ્લેગ્સ (`failed_last_run`, `not_producing`, `stale_scrapers`).
- **R3: સોર્સ ગુણવત્તા વિશ્લેષણ** — સોર્સ ફેમિલી મુજબ વર્ગીકરણ, હોટ લીડ્સ (AI સ્કોર ≥ ૭), સંપર્ક અને પ્રત્યુત્તર દર, અને ઓછા મૂલ્યવાળા સોર્સની ઓળખ.
- **R4: ફોલો-અપ વોચલિસ્ટ ("કોઈ લીડ ન ચૂકો")** — ૮ પ્રાથમિકતા સ્તરો આધારિત ફોલો-અપ લિસ્ટ, DNC (Do-Not-Contact) કંપની ફિલ્ટરિંગ અને ડાયરેક્ટ ફોલો-અપ શેડ્યૂલિંગ.
- **R5: પાઇપલાઇન અને ફનલ** — તમામ ૮ સ્ટેજનું ટ્રેકિંગ (શૂન્ય લીડ હોય તો પણ ચોક્કસ ડિસ્પ્લે), કન્વર્ઝન દર અને ૧૪ દિવસથી વધુ અટવાયેલી લીડ્સ.
- **R6: આઉટરીચ પર્ફોર્મન્સ** — ચેનલ મુજબ ઈમેલ ટ્રેકિંગ (`auto`, `manual`, `bulk`, `sequence`, `other`, `before_tracking`) અને સફળ સબ્જેક્ટ લાઇનનું રેન્કિંગ.
- **R7: ડેટા હેલ્થ ઓડિટ** — ૯ ડેટા ગુણવત્તા નિયમોની તપાસ (ઈમેલ, ફોન, વેબસાઈટ વગરની લીડ્સ, ડુપ્લિકેટ એન્ટ્રીઓ) અને સેમ્પલ લીડ ID.
- **R8: દૈનિક ઓડિટ લોગ** — ચોક્કસ તારીખે થયેલી સ્ક્રેપર રન, નવી લીડ્સ અને ઈમેલ ગતિવિધિઓનો ક્રમબદ્ધ ટાઈમલાઈન લોગ.

---

## 2. Architecture & File Structure / આર્કિટેક્ચર અને ફાઇલ માળખું

```
test-demo/
├── reports_engine.py                    # Pure computational analytics engine (no Flask dependency)
├── test_reports_engine.py               # Unit & integration test suite (22 tests, < 4s execution)
├── app.py                               # Section: # REPORTS (reports_engine.py) - 9 REST endpoints
├── docs/
│   └── reports.md                       # This bilingual technical documentation
├── reports/
│   └── qa/
│       ├── 2026-11-13-reports.md        # QA signoff and validation report
│       └── 2026-11-13-reports-screens/  # Desktop and mobile browser screenshots
└── frontend/
    ├── app/
    │   ├── page.js                      # Active tab routing for 'reports'
    │   └── globals.css                  # Prefixed styling rules (/* ---- Reports ---- */, rp-*)
    ├── lib/
    │   └── api.js                       # Section 16: fetchReport* API client methods
    └── components/
        ├── Header.js                    # Tab title resolution ('Reports')
        ├── Sidebar.js                   # Nav item: { id: 'reports', label: 'Reports', icon: BarChart3 }
        ├── Reports.js                   # Top-level shell with filter bar, tablist, and persistence
        └── reports/
            ├── reportUtils.js           # CSV export with formula neutralization, formatting utilities
            ├── OverviewTab.js           # R1 view
            ├── FollowupsTab.js          # R4 view with schedule action modal
            ├── ScrapersTab.js           # R2 view
            ├── SourcesTab.js            # R3 view
            ├── PipelineTab.js           # R5 view
            ├── OutreachTab.js           # R6 view
            ├── DataHealthTab.js         # R7 view
            └── DailyLogTab.js           # R8 view
```

---

## 3. Data Safety & Read-Only Invariant / ડેટા સુરક્ષા અને રીડ-ઓન્લી નિયમ

### English
All analytical computations in `reports_engine.py` are strictly read-only.
- **Zero Disk Mutation:** The engine never writes to `all_leads_master.csv`, `logs/scraper_runs.csv`, `logs/sent_emails.csv`, or configuration files.
- **Cryptographic Verification:** SHA-256 integrity checks confirm `all_leads_master.csv` byte equality before and after API sweeps.
- **Formula Injection Defense:** All CSV exports sanitize text cells starting with `=`, `+`, `-`, or `@` by prepending a single quote `'` and prepend a UTF-8 BOM (`\uFEFF`) for seamless Microsoft Excel compatibility.
- **Do-Not-Contact (DNC) Shield:** Excluded companies (`excludedCompanies` in settings) are strictly excluded from proactive follow-up recommendations to avoid unauthorized contact.

### ગુજરાતી (Gujarati)
`reports_engine.py` માં તમામ એનાલિટિક્સ ગણતરીઓ સંપૂર્ણપણે રીડ-ઓન્લી (Read-Only) છે.
- **ડેટા ફાઇલોમાં ફેરફાર નહીં:** આ મોડ્યુલ `all_leads_master.csv`, `logs/scraper_runs.csv`, `logs/sent_emails.csv` અથવા સેટિંગ્સ ફાઈલોમાં ક્યારેય કોઈ ફેરફાર કરતું નથી.
- **SHA-256 વેરિફિકેશન:** API કોલ પહેલાં અને પછી `all_leads_master.csv` નો ક્રિપ્ટોગ્રાફિક હેશ ચેક કરવામાં આવે છે જે ખાતરી કરે છે કે ફાઇલ સંપૂર્ણ સુરક્ષિત છે.
- **CSV ફોર્મ્યુલા ઇન્જેક્શન સુરક્ષા:** CSV એક્સપોર્ટ વખતે `=`, `+`, `-`, અથવા `@` થી શરૂ થતી કિંમતોને સેનિટાઈઝ કરવામાં આવે છે અને Excel સુસંગતતા માટે UTF-8 BOM ઉમેરવામાં આવે છે.
- **DNC (Do-Not-Contact) સુરક્ષા:** સેટિંગ્સમાં બ્લોક કરેલી કંપનીઓને ફોલો-અપ ભલામણોમાંથી બાકાત રાખવામાં આવે છે.

---

## 4. REST API Reference / REST API સંદર્ભ

All endpoints require authentication (session or `X-Demo-User: true`).

| Endpoint | Method | Query Parameters | Description |
|---|---|---|---|
| `/api/reports/options` | `GET` | — | Available presets, source families, and stage options. |
| `/api/reports/summary` | `GET` | `preset`, `date_from`, `date_to`, `source`, `status` | R1 Executive summary, 12 cards with deltas, 30-day series. |
| `/api/reports/scrapers` | `GET` | `preset`, `date_from`, `date_to` | R2 Scraper efficiency table, flags, per-run executions. |
| `/api/reports/sources` | `GET` | `preset`, `date_from`, `date_to`, `status` | R3 Lead yield by source family, hot lead counts, reply rates. |
| `/api/reports/followups` | `GET` | `preset`, `source`, `status`, `quiet_days` | R4 Watchlist categorized by 8 reasons, sorted by priority. |
| `/api/reports/pipeline` | `GET` | `preset`, `date_from`, `date_to`, `source` | R5 Pipeline counts across 8 stages, conversion rates, stuck leads. |
| `/api/reports/outreach` | `GET` | `preset`, `date_from`, `date_to`, `source` | R6 Volume by channel, reply rates, top 10 email subjects. |
| `/api/reports/data-health` | `GET` | — | R7 Completeness audit across 9 hygiene dimensions. |
| `/api/reports/activity` | `GET` | `day` (`YYYY-MM-DD`) | R8 Chronological event timeline for a specified day. |

---

## 5. Test Suite & Verification / ટેસ્ટ પરિણામો અને ચકાસણી

- **Unit & Integration Suite:** `test_reports_engine.py` (22 automated tests) — **PASS** (100%).
- **Full Application Suite:** `python -m unittest discover -p "test_*.py"` (551 tests) — **PASS** (100%).
- **Frontend Production Build:** `NEXT_DIST_DIR=.next-qa npm run build` — **Compiled Successfully (0 errors)**.
- **Performance Benchmark:** 50,000 synthetic leads + 100,000 scraper runs evaluated in **3.89 seconds** (< 4.0s requirement).
- **Browser Visual Verification:** Verified via Playwright automation across desktop (1440x900) and mobile (390x844) viewports. Screenshots saved in `reports/qa/2026-11-13-reports-screens/`.

