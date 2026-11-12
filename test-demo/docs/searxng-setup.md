# SearXNG — Search Without Any API Key

**Status:**
- **Done:** app code and unit tests.
- **UNVERIFIED:** live search through a real SearXNG server. Docker is not installed on the development PC yet.
- **Updated:** 2026-11-12.

---

## English

### What it is
SearXNG is a free, open-source **metasearch engine** that you run on your own computer. It asks Google, Bing, DuckDuckGo and others, and merges their results.

The app talks to it like any other search engine, but it needs **no API key and no account**.

### Which modules use it
Every Scraping / Mining module that searches the web:
- Search Engines, Social Media, WhatsApp Groups, Ecommerce, Ad Library
- the property portals in Real Estate
- website discovery in Deep Search

**Auto** picks engines in this order: Brave → Serper → **SearXNG** → DuckDuckGo. You can also choose SearXNG directly in the "Search engine" dropdown.

### Using a Brave key and SearXNG together (recommended)
Set both `BRAVE_SEARCH_API_KEY` and `SEARXNG_URL`.
- **Brave answers first.**
- **Fallback:** if Brave is rate limited, out of free credits, rejects the key, or does not answer, **the same query goes to SearXNG** automatically. If SearXNG is not running either, the query goes to DuckDuckGo.
- **Cooldown:** an engine that failed is skipped for 10 minutes, so later queries do not waste a request on it.
- The Flask log shows a line such as `[search] Brave Search unavailable - used SearXNG instead`.
- This happens in one place (`search_engine.run_with_fallback`), so every module gets it.

### Setup (one time, about 15 minutes)
1. **Install Docker Desktop (Windows).**
   - Download it from https://www.docker.com/products/docker-desktop/.
   - It asks to install **WSL 2**. Allow it; this needs administrator rights and a restart.
   - Start Docker Desktop and wait until it shows "Engine running".
2. **Create the secret file** `test-demo/searxng/.env`. It is git-ignored and never committed. Put this one line in it:
   ```
   SEARXNG_SECRET=<any long random text>
   ```
   PowerShell can make a random value: `[guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")`
3. **Start SearXNG:**
   ```
   cd test-demo/searxng
   docker compose up -d
   ```
   Then open http://localhost:8888. You should see the SearXNG search page.
4. **Connect the app.** Add this line to `test-demo/.env`, then restart Flask:
   ```
   SEARXNG_URL=http://localhost:8888
   ```
5. **Check it.** Open **Settings → API Keys**. "SearXNG" should show as configured.

To stop SearXNG, run `docker compose down`. It starts again by itself with Docker unless you stop it.

### Safety
- The port is bound to `127.0.0.1`, so only this computer can reach it. It is never exposed to the office network or the internet.
- The app sends **no key** and only reads JSON results. `SEARXNG_URL` must start with `http://` or `https://`.
- **Limits:** SearXNG asks the big engines for you, so heavy use can make them pause it for a while (you'll see a rate-limit message).
  - The app already waits between queries and stops on a rate limit while keeping the results found so far.
  - Do not use public SearXNG instances. They block apps, and sending your searches there is not private.

### Errors you may see
| Message | Fix |
|---|---|
| "SearXNG is not running at …" | Start Docker Desktop, then run `docker compose up -d` |
| "SearXNG refused JSON output" | `settings.yml` must list `json` under `search.formats` (it does by default here) |
| "SearXNG needs SEARXNG_URL in .env" | Add `SEARXNG_URL` (step 4) and restart Flask |

---

## ગુજરાતી

### આ શું છે
SearXNG એક free, open-source search engine છે, જે તમારા પોતાના computer પર ચાલે છે. એ Google, Bing અને DuckDuckGo માંથી results ભેગાં કરે છે. એમાં **કોઈ API key કે account જોઈતું નથી.**

### Brave key અને SearXNG બંને સાથે (ભલામણ)
`.env` માં `BRAVE_SEARCH_API_KEY` અને `SEARXNG_URL` બંને લખો.
- પહેલાં **Brave** જવાબ આપે છે.
- Brave ની free limit પૂરી થાય, key ખોટી હોય કે Brave જવાબ ન આપે, તો એ જ search **આપોઆપ SearXNG પર** જાય છે.
- SearXNG પણ બંધ હોય તો search DuckDuckGo પર જાય છે.
- જે engine fail થયું હોય એ 10 મિનિટ સુધી પૂછવામાં નથી આવતું.

### Setup (એક જ વાર, લગભગ 15 મિનિટ)
1. **Docker Desktop install કરો:** https://www.docker.com/products/docker-desktop/
   - એ WSL 2 install કરવાનું કહેશે. એ માટે admin rights અને restart જોઈશે.
2. **Secret file બનાવો:** `test-demo/searxng/.env` બનાવો અને એમાં આ એક line લખો: `SEARXNG_SECRET=<લાંબું random લખાણ>`
   - આ file git માં ક્યારેય નહીં જાય.
3. **SearXNG ચાલુ કરો:** `test-demo/searxng` folder માં `docker compose up -d` ચલાવો.
   - પછી http://localhost:8888 ખોલો. ત્યાં SearXNG નું search page દેખાવું જોઈએ.
4. **App સાથે જોડો:** `test-demo/.env` માં `SEARXNG_URL=http://localhost:8888` ઉમેરો અને Flask restart કરો.
5. **તપાસો:** Settings → API Keys માં SearXNG "configured" દેખાવું જોઈએ.

### ધ્યાન રાખવું
- SearXNG ફક્ત આ computer પરથી જ ખૂલે છે, network પર નહીં.
- બહુ વધારે searches થાય તો Google વગેરે થોડી વાર માટે રોકી શકે છે. ત્યારે app અત્યાર સુધી મળેલાં results રાખે છે અને message બતાવે છે.
- Public SearXNG sites વાપરવી નહીં.
