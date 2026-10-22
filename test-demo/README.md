# Public IT & Software Hiring Lead Scraper (High-Accuracy Edition)

A Python demonstration tool for identifying and collecting publicly available IT/software business leads. The scraper filters out irrelevant pages (such as dictionaries, educational articles, streaming media, and generic directories), detects buying/hiring intent versus service providers, and scores leads accurately.

---

## 📁 Project Structure

```text
lead-scraper/
│
├── run_all_scrapers.py      # Unified Master Entry Point coordinating all 10 scrapers
├── all_leads_master.csv     # Authoritative Master Database of all unique leads
├── lead_normalizer.py       # Normalization, prioritized deduplication & atomic storage
├── scraper_adapters.py      # Reusable in-memory adapters for all 10 scrapers
├── migrate_historical_leads.py # Reconciles historical CSV leads into the master file
├── test_lead_system.py      # Unit test suite verifying deduplication & safe preservation
├── logs/scraper_runs.csv    # Append-only run telemetry and scraper audit log
├── backups/pre_migration/   # Automatic backups of all original CSV files
├── scraper.py               # Main web search & deep crawl pipeline
├── lead_generation_master.py # RSS & Playwright Justdial multi-source engine
├── leads.csv                # High-quality leads meeting MIN_LEAD_SCORE threshold
├── rejected_leads.csv       # Disqualified candidates with explicit rejection reasons
├── requirements.txt         # Python package dependencies
└── README.md                # Documentation and usage guide
```

---

## 🚀 Unified Master Lead Generation System (`run_all_scrapers.py`)

Run the single unified command to execute all scrapers and incrementally update the master database:

```powershell
python run_all_scrapers.py
```

### Key Guarantees:
1. **Never Loses Old Leads:** Automatically loads [`all_leads_master.csv`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/all_leads_master.csv), preserves all existing records, and safely merges new attributes.
2. **Prioritized Deduplication:** Matches incoming leads against existing records using:
   - Normalized email address
   - Normalized Indian/international phone number
   - Canonical company website domain
   - Exact source/post URL
   - Normalized company name + location
3. **Safe Atomic Writes:** Writes updates to a temporary `.tmp` file and replaces the master file atomically only upon success.
4. **Execution Telemetry:** Records detailed run history (runtime, raw records, new leads, enriched records, duplicates, errors) into [`logs/scraper_runs.csv`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/logs/scraper_runs.csv).
5. **Run Lock Protection:** Uses `.scraper_runner.lock` to prevent two simultaneous processes from conflicting.

---

## 🛠️ Windows Installation & Setup

1. **Open PowerShell / Command Prompt** in the project directory:
   ```powershell
   cd c:\xampp\htdocs\Yashvi-Practical\test-demo
   ```

2. **Create and activate a virtual environment**:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
   *(If PowerShell shows an execution policy error, run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate again).*

3. **Install required packages**:
   ```powershell
   pip install -r requirements.txt
   ```

4. **Run the scraper**:
   ```powershell
   python scraper.py
   ```

---

## ⚙️ Configuration

Configure the parameters near the top of [`scraper.py`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/scraper.py):

```python
# 1. Targeted search queries focused on hiring/need intent
SEARCH_QUERIES = [
    '"looking for software development company"',
    '"need software development company"',
    '"looking for web development company"',
    '"need web development company"',
    '"hire software development company"',
    '"looking for IT company"',
    '"need IT company"',
    '"hire software developer"',
    '"looking for software developer"',
    '"need mobile app development company"',
]

# 2. Configurable location (e.g., "Ahmedabad", "Mumbai", or "" for global)
SEARCH_LOCATION = "Ahmedabad"

# 3. Execution thresholds
MAX_RESULTS_PER_QUERY = 10     # Max search results per query
REQUEST_TIMEOUT = 10           # HTTP request timeout (seconds)
REQUEST_DELAY = 1.5            # Courteous delay between requests
MIN_LEAD_SCORE = 4             # Minimum score required to enter leads.csv
```

---

## 🔍 How Filtering & Classification Work

### 1. Strong Domain & Content Filtering
Before crawling any link, the script filters out:
- **Social Networks**: Facebook, LinkedIn, Instagram, YouTube, X/Twitter, Reddit, TikTok.
- **Search Engines**: Google, Bing, Yahoo, DuckDuckGo.
- **Dictionaries & Educational Sites**: Cambridge Dictionary, Thesaurus, Merriam-Webster, Collins, Britannica, GeeksforGeeks, W3Schools, etc.
- **Streaming & Entertainment**: Netflix, Hotstar, JustWatch, IMDb.
- **Aggregators & Job Portals**: Justdial, Indiamart, Indian Yellow Pages, Upwork, Fiverr, Clutch, GoodFirms, TechBehemoths, DesignRush, SelectedFirms.

### 2. Identifying Service Providers vs. Potential Buyers
- **IT Service Provider**: A company that sells software development services (e.g., *"We provide web development services"*, *"Our IT solutions"*). They are service sellers, not buyers.
- **Potential Buyer**: A company expressing intent to purchase or hire services (e.g., *"Looking for software development company"*, *"RFP for mobile app"*, *"Need IT company"*).

### 3. Intent Detection
- **High Intent (7+)**: Strong explicit buying signals, RFPs, tenders, or direct hiring statements.
- **Medium Intent (4–6)**: Project requirement mentions, hiring notices, or request-a-quote signals.
- **Low Intent (0–3)**: General business presentation without active purchase signals.

### 4. Lead Scoring System
The scoring logic in `calculate_lead_score()` evaluates:
- `+3`: Strong buying-intent phrase found
- `+2`: Hiring phrase found
- `+2`: Software/web/mobile requirement identified
- `+1`: Business website structure confirmed
- `+1`: Verified public business email found
- `+1`: Valid phone number found
- `-5`: IT Service Provider (sellers penalized so only buyers qualify)
- `-5`: Directory, job board, or blog/article

---

## 📊 CSV Output Structure

### `leads.csv`
Contains qualified leads meeting `Lead Score >= MIN_LEAD_SCORE`:
| Column | Description |
|---|---|
| `No` | Record index |
| `Company Name` | Cleaned company brand name (not full search title) |
| `Website URL` | Canonical website link |
| `Email` | Public verified emails (prioritizing `info@`, `contact@`, `sales@`) |
| `Mobile Number` | Validated and normalized Indian phone number (`+91 XXXXX XXXXX` or `079-XXXXXXX`) |
| `Search Query` | The search queries that surfaced this lead (deduplicated with `\|`) |
| `Intent` | `High`, `Medium`, or `Low` |
| `Lead Type` | `Potential Buyer` or `IT Service Provider` |
| `Lead Score` | Numerical quality score |

### `rejected_leads.csv`
Stores discarded entries with their `Rejection Reason` for debugging and transparency.

---

## ⚖️ Ethics, Compliance & Limitations

1. **Public Information Only**: Crawls only publicly accessible web pages without authentication or login walls.
2. **No Anti-Bot Bypass**: Complies with anti-bot policies. If search engines throttle or present verification challenges, the script logs an informative message and falls back to standard public search endpoints.
3. **No Buying Guarantees**: A `Potential Buyer` classification indicates automated textual evidence of need or hiring intent; it is **not a guarantee of a confirmed transaction**.
4. **Courteous Scraping**: Enforces `REQUEST_DELAY` between visits to minimize server load.

---

## ⚡ Modern Next.js UI Hub (`frontend/`)

A state-of-the-art Next.js web application UI for managing leads, triggering multi-channel scrapers, and conducting cold outreach campaigns.

### Features
- **Leads CRM & Table**: Instant debounced search, filtering by intent/outreach/status, pagination, and bulk actions.
- **Cold Email Outreach**: Personalized email composer modal with chips (`{company}`, `{name}`, `{location}`), batch sender with delay throttling, and live signature preview.
- **WhatsApp Integration**: Direct click-to-chat deep links with prefilled templates.
- **Live Scraper Console**: 12-channel harvester control room with real-time streaming terminal logs.
- **Lead Importer**: Extract leads from live search queries, exported WhatsApp chats (`.txt`/`.zip`), or raw notes.
- **Company & SMTP Settings**: Configure Gmail SMTP credentials, company profile, and verify delivery via test emails.

### Quick Start
1. Launch via double-clicking [`run_nextjs_ui.bat`](file:///e:/MyWork/mini-ecommerce-interview-practical/test-demo/run_nextjs_ui.bat)
2. Or run via PowerShell:
   ```powershell
   cd frontend
   npm.cmd run dev -- -p 3001
   ```
3. Open in browser: **http://localhost:3001**

