"""Client-eye walkthrough of every screen. Frontend: QA build on :3001. ALL /api calls are re-routed to the
sandbox backend on :5055, so the owner's real backend (:5000) and real leads are never touched."""
import json, os, re, sys, time
from playwright.sync_api import sync_playwright

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
FRONT = "http://127.0.0.1:3001"
SANDBOX = "http://127.0.0.1:5055"

TABS = ["dashboard", "searchengines", "mining-maps", "mining-social", "mining-adlibrary", "mining-ecommerce", "jobportal",
        "mining-directories", "mining-whatsapp", "mining-realestate",
        "dx-mlmdiary", "dx-indiamart", "dx-justdial", "dx-sulekha", "dx-tradeindia", "dx-exportersindia",
        "cr-company", "cr-pvtltd", "cr-gst", "bc-websites", "bc-emails", "bc-phones", "bc-import",
        "wc-site", "wc-links", "wc-keywords", "wc-sitemap", "dt-age", "dt-dns", "dt-new", "dt-available",
        "ut-analyzer", "fileuploads", "followups", "crmsources", "lc-cleanup", "lc-enrich", "leads", "scraper",
        "autoscheduler", "import", "settings"]
BAD_TEXT = re.compile(r"\bundefined\b|\bNaN\b|\[object Object\]|Invalid Date|\bnull\b")

def reroute(route):
    req = route.request
    url = req.url
    i = url.find("/api/")
    try:
        resp = route.fetch(url=SANDBOX + url[i:])
        route.fulfill(response=resp)
    except Exception as e:
        route.abort()

def run(pw, name, viewport, mobile=False):
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport=viewport, is_mobile=mobile, has_touch=mobile, device_scale_factor=1)
    ctx.route(re.compile(r".*/api/.*"), reroute)
    page = ctx.new_page()
    events = []
    cur = {"tab": "login"}
    page.on("console", lambda m: events.append({"tab": cur["tab"], "kind": "console." + m.type, "text": m.text[:300]}) if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: events.append({"tab": cur["tab"], "kind": "pageerror", "text": str(e)[:300]}))
    page.on("response", lambda r: events.append({"tab": cur["tab"], "kind": "http", "text": f"{r.status} {r.request.method} {r.url[-90:]}"}) if r.status >= 400 else None)
    page.on("requestfailed", lambda r: events.append({"tab": cur["tab"], "kind": "reqfailed", "text": r.url[-120:]}))

    page.goto(FRONT, wait_until="networkidle")
    page.screenshot(path=f"{OUT}/{name}-00-login.png", full_page=True)
    results = []
    # one-click local login
    btn = page.get_by_role("button", name=re.compile("local|demo|one-click|admin", re.I))
    results.append({"tab": "login", "login_buttons": btn.count(), "title": page.title()})
    btn.first.click()
    page.wait_for_selector("#nav-item-dashboard", timeout=15000)
    page.wait_for_load_state("networkidle")

    for n, tab in enumerate(TABS, 1):
        cur["tab"] = tab
        t0 = time.time()
        try:
            if mobile:
                if not page.locator("aside.theme-sidebar.mobile-open").count():
                    page.locator("button.theme-collapse-toggle").click(timeout=4000)
                    page.wait_for_selector("aside.theme-sidebar.mobile-open", timeout=4000)
                    page.wait_for_timeout(300)
            loc = page.locator(f"#nav-item-{tab}")
            loc.scroll_into_view_if_needed(timeout=4000)
            loc.click(timeout=4000)
            try:
                page.wait_for_load_state("networkidle", timeout=12000)
            except Exception:
                pass
            page.wait_for_timeout(500)
            info = page.evaluate("""() => {
                const de = document.documentElement;
                const main = document.querySelector('main') || document.body;
                const wide = [];
                document.querySelectorAll('main *').forEach(el => {
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && r.right > window.innerWidth + 2 && !el.closest('.theme-table-scroll, [style*="overflow"]')) wide.push(el.tagName + '.' + String(el.className).slice(0,40));
                });
                const small = [];
                document.querySelectorAll('main button, main a, main input, main select').forEach(el => {
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0 && r.height < 24) small.push(el.tagName + ':' + (el.innerText||el.placeholder||el.type||'').slice(0,20) + ':' + Math.round(r.height));
                });
                const noLabel = [];
                document.querySelectorAll('main button').forEach(el => {
                    if (!(el.innerText||'').trim() && !el.getAttribute('aria-label') && !el.title) noLabel.push(String(el.className).slice(0,40));
                });
                return {scrollW: de.scrollWidth, clientW: de.clientWidth, text: main.innerText.slice(0, 6000),
                        h1: [...document.querySelectorAll('main h1, main h2, .theme-panel-title')].map(e => e.innerText.slice(0,60)).slice(0,4),
                        wide: wide.slice(0,5), small: small.slice(0,6), noLabel: noLabel.slice(0,6),
                        inputsNoLabel: [...document.querySelectorAll('main input:not([type=checkbox]):not([type=hidden]), main select, main textarea')].filter(el => !el.labels?.length && !el.getAttribute('aria-label') && !el.placeholder).length};
            }""")
            bad = sorted(set(BAD_TEXT.findall(info["text"])))
            page.screenshot(path=f"{OUT}/{name}-{n:02d}-{tab}.png", full_page=True)
            results.append({"tab": tab, "ms": int((time.time() - t0) * 1000), "overflowX": info["scrollW"] - info["clientW"],
                            "titles": info["h1"], "badText": bad, "wide": info["wide"], "small": info["small"],
                            "noLabelBtns": info["noLabel"], "inputsNoLabel": info["inputsNoLabel"],
                            "textLen": len(info["text"])})
        except Exception as e:
            results.append({"tab": tab, "error": str(e)[:300]})
            try: page.screenshot(path=f"{OUT}/{name}-{n:02d}-{tab}-ERROR.png")
            except Exception: pass
    json.dump({"results": results, "events": events}, open(f"{OUT}/{name}.json", "w"), indent=1)
    browser.close()
    return results, events

with sync_playwright() as pw:
    for name, vp, mob in (("desktop", {"width": 1440, "height": 900}, False), ("mobile", {"width": 390, "height": 844}, True)):
        if len(sys.argv) > 2 and sys.argv[2] != name:
            continue
        res, ev = run(pw, name, vp, mob)
        print(f"== {name}: {len(res)} screens, {len(ev)} events")
        for r in res:
            flags = []
            if r.get("error"): flags.append("ERROR " + r["error"][:150])
            if r.get("overflowX", 0) > 2: flags.append(f"overflowX={r['overflowX']}")
            if r.get("badText"): flags.append(f"badText={r['badText']}")
            if r.get("wide"): flags.append(f"wide={r['wide'][:2]}")
            if r.get("noLabelBtns"): flags.append(f"unlabelledBtns={len(r['noLabelBtns'])}")
            if r.get("textLen", 1) < 40 and r["tab"] != "login": flags.append("nearly empty")
            print((f"  {r['tab']:24} {r.get('ms','')!s:>6} {r.get('titles', [''])[:1]} {' | '.join(flags)}").encode('ascii','replace').decode())
        seen = set()
        for e in ev:
            key = (e["kind"], e["text"][:120])
            if key in seen: continue
            seen.add(key)
            print(f"  [{e['tab']}] {e['kind']}: {e['text'][:220]}".encode('ascii','replace').decode())
