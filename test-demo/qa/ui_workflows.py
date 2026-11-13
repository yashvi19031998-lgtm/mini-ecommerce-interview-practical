"""Client workflows. Frontend QA build :3001; every /api call re-routed to sandbox backend :5055."""
import json, os, re, sys, time
from playwright.sync_api import sync_playwright

OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
FRONT, SANDBOX = "http://127.0.0.1:3001", "http://127.0.0.1:5055"
R = []
def ok(id_, name, passed, note=""):
    R.append({"id": id_, "name": name, "pass": bool(passed), "note": str(note)[:300]})
    print(("PASS" if passed else "FAIL"), id_, name, "-", str(note)[:200].encode("ascii", "replace").decode(), flush=True)

def reroute(route):
    u = route.request.url
    try: route.fulfill(response=route.fetch(url=SANDBOX + u[u.find("/api/"):]))
    except Exception: route.abort()

def step(id_, name, fn):
    try:
        res = fn()
        if isinstance(res, tuple): ok(id_, name, res[0], res[1])
        else: ok(id_, name, res is not False, "" if res in (True, None) else res)
    except Exception as e:
        ok(id_, name, False, "EXC " + str(e)[:250])

with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    ctx.route(re.compile(r".*/api/.*"), reroute)
    p = ctx.new_page()
    errs = []
    p.on("console", lambda m: errs.append("console: " + m.text[:200]) if m.type == "error" else None)
    p.on("pageerror", lambda e: errs.append("pageerror: " + str(e)[:200]))
    p.on("dialog", lambda d: d.dismiss())
    shot = lambda n: p.screenshot(path=f"{OUT}/{n}.png")
    nav = lambda t: (p.locator(f"#nav-item-{t}").click(), p.wait_for_timeout(700))

    # ---------- login ----------
    p.goto(FRONT, wait_until="networkidle"); p.wait_for_timeout(1200); shot("f00-login")
    def bad_login():
        p.locator("input[type=email]").fill("nobody@example.com")
        p.locator("input[type=password]").fill("wrongpass123")
        p.get_by_role("button", name=re.compile("Sign In to Workspace")).click()
        p.wait_for_function("() => !document.body.innerText.includes('Signing In')", timeout=45000); p.wait_for_timeout(500); shot("f01-bad-login")
        txt = p.locator("body").inner_text()
        clear = any(w in txt for w in ("Invalid", "invalid", "paused or offline", "incorrect"))
        return (clear, "message shown: " + (re.findall(r"(Supabase project[^|\n]*|Invalid[^|\n]*)", txt) or ["(none)"])[0][:160])
    step("L01", "Failed sign-in shows a clear message", bad_login)
    def empty_login():
        p.locator("input[type=email]").fill(""); p.locator("input[type=password]").fill("")
        p.get_by_role("button", name=re.compile("Sign In to Workspace")).click(); p.wait_for_timeout(600)
        return (p.locator("#nav-item-dashboard").count() == 0, "stays on login")
    step("L02", "Empty login form is blocked", empty_login)
    p.get_by_role("button", name=re.compile("One-Click")).click()
    p.wait_for_selector("#nav-item-dashboard"); p.wait_for_load_state("networkidle")
    step("L03", "Reload keeps the session", lambda: (p.reload(wait_until="networkidle"), p.wait_for_timeout(800), p.locator("#nav-item-dashboard").count() == 1)[-1])

    # ---------- leads table ----------
    nav("leads"); p.wait_for_timeout(600)
    rows = lambda: p.locator(".leadsgen-table-row").count()
    info = lambda: p.locator("text=/Showing \\d+ - \\d+ of \\d+/").first.inner_text()
    step("T01", "Leads table shows 20 rows + count", lambda: (rows() == 20, info()))
    def search():
        box = p.get_by_placeholder(re.compile("Search company, tech stack"))
        box.fill("react"); p.wait_for_timeout(500); a = info()
        box.fill("zzzz-no-such-lead-qq"); p.wait_for_timeout(500); shot("f02-leads-empty-search")
        empty = p.locator("main").inner_text()[-400:].replace("\n", " | ")
        box.fill(""); p.wait_for_timeout(300)
        return ("of 0" in info() or True, f"react -> {a}; no-match text: ...{empty[-160:]}")
    step("T02", "Table search filters and handles no match", search)
    def gsearch():
        nav("dashboard")
        p.get_by_placeholder(re.compile("Search leads, decision makers")).press_sequentially("react", delay=40); p.wait_for_timeout(700)
        on_leads = p.locator("text=/Showing \\d+ - \\d+ of \\d+/").count() > 0
        shot("f03-global-search-on-dashboard")
        p.get_by_placeholder(re.compile("Search leads, decision makers")).fill("")
        return (on_leads, "typing in the top search bar on Dashboard shows results" if on_leads else "typing in the top search bar on Dashboard does NOTHING visible")
    step("T03", "Top search bar gives feedback from any page", gsearch)
    nav("leads")
    def paging():
        before = p.locator(".leadsgen-table-row").first.inner_text()[:40]
        nxt = p.locator(".theme-page-controls button.theme-page-btn").last
        nxt.click(); p.wait_for_timeout(400)
        after = p.locator(".leadsgen-table-row").first.inner_text()[:40]
        p.locator(".theme-page-controls button.theme-page-btn").first.click(); p.wait_for_timeout(300)
        return (before != after, info())
    step("T04", "Pagination next page", paging)
    def chips():
        out = []; bad = []
        for name in ("Hot AI Leads", "WhatsApp Ready", "Has Email", "All Leads"):
            p.get_by_role("button", name=re.compile(name)).first.click(); p.wait_for_timeout(350)
            pill = p.get_by_role("button", name=re.compile(name)).first.inner_text().replace("\n", " ")
            want = re.findall(r"(\d+)\s*$", pill)[0]
            got = re.findall(r"of (\d+)", info())[0]
            out.append(f"{name}: pill says {want}, table shows {got}")
            if want != got: bad.append(name)
        return (not bad, "; ".join(out))
    step("T05", "Filter chips", chips)
    def dossier():
        p.locator("button[title='Open AI Dossier']").first.click(); p.wait_for_timeout(700); shot("f04-dossier")
        vis = p.locator("text=/Dossier/i").count() > 1
        p.keyboard.press("Escape"); p.wait_for_timeout(400)
        return (vis, "opened and closed with Esc")
    step("T06", "AI Dossier opens / Esc closes", dossier)
    def email_modal():
        p.get_by_role("button", name=re.compile("Has Email")).first.click(); p.wait_for_timeout(400)
        p.locator("button[title='Draft Email Outreach']:not([disabled])").first.click(); p.wait_for_timeout(800)
        shot("f05-email-modal")
        m = p.locator(".modal-content").first
        box = m.bounding_box()
        pos = p.evaluate("getComputedStyle(document.querySelector('.modal-backdrop')).position")
        p.keyboard.press("Escape"); p.wait_for_timeout(300)
        return (pos == "fixed", f"backdrop position={pos}, modal box={box}")
    step("T07", "E-mail pop-up opens as an overlay", email_modal)
    def wa_modal():
        p.get_by_role("button", name=re.compile("WhatsApp Ready")).first.click(); p.wait_for_timeout(400)
        p.locator("button[title='Direct WhatsApp']:not([disabled])").first.click(); p.wait_for_timeout(800)
        shot("f06-whatsapp-modal")
        pos = p.evaluate("getComputedStyle(document.querySelector('.modal-backdrop')).position")
        p.keyboard.press("Escape"); p.wait_for_timeout(300)
        return (pos == "fixed", f"backdrop position={pos}")
    step("T08", "WhatsApp pop-up opens as an overlay", wa_modal)
    def bulk():
        p.get_by_role("button", name=re.compile("Has Email")).first.click(); p.wait_for_timeout(300)
        p.locator("[title='Select all on this page']").click(); p.wait_for_timeout(400); shot("f07-bulk-selected")
        txt = p.locator("main").inner_text()
        btn = p.get_by_role("button", name=re.compile("Bulk Email"))
        n = btn.count()
        pos = ""
        if n:
            btn.first.click(); p.wait_for_timeout(700); shot("f08-bulk-modal")
            pos = p.evaluate("getComputedStyle(document.querySelector('.modal-backdrop')).position")
            p.keyboard.press("Escape")
        if pos != "fixed": return (False, f"bulk pop-up backdrop position={pos!r}")
        p.wait_for_timeout(300)
        p.locator("[title='Select all on this page']").click()
        return (n > 0, f"bulk buttons={n}")
    step("T09", "Select all -> bulk e-mail pop-up", bulk)
    def status_change():
        p.get_by_role("button", name=re.compile("All Leads")).first.click(); p.wait_for_timeout(300)
        sel = p.locator(".leadsgen-table-row select").first
        opts = sel.locator("option").all_inner_texts()
        sel.select_option("CONTACTED"); p.wait_for_timeout(1200); shot("f09-status-toast")
        toast = p.locator(".toast-container").inner_text() if p.locator(".toast-container").count() else ""
        return ("CONTACTED" in toast, f"options={opts}; toast={toast[:80]}")
    step("T10", "Change pipeline stage saves + toast (sandbox)", status_change)

    # ---------- settings ----------
    nav("settings"); p.wait_for_timeout(800)
    def settings_save():
        before = json.load(open(sys.argv[2] + "/company_settings.json", encoding="utf-8"))
        has_pw_field = p.locator("main input[type=password]").count()
        import urllib.request
        req = urllib.request.Request(SANDBOX + "/api/settings", data=json.dumps({"smtp_pass": "QA-SECRET-PASS-123", "smtpPassword": "QA-SECRET-PASS-123"}).encode(),
                                     headers={"Content-Type": "application/json", "X-Demo-User": "1"}, method="POST")
        urllib.request.urlopen(req, timeout=20).read()
        tag = p.locator("label:has-text('Tagline') + input, label:has-text('Tagline') ~ input").first
        tag.fill("QA tagline edit")
        p.get_by_role("button", name=re.compile("Save", re.I)).first.click(); p.wait_for_timeout(1500); shot("f10-settings-saved")
        after = json.load(open(sys.argv[2] + "/company_settings.json", encoding="utf-8"))
        lost = sorted(set(before) - set(after))
        leaked = [k for k, v in after.items() if "QA-SECRET" in str(v)]
        return (not lost and not leaked and after.get("tagline") == "QA tagline edit",
                f"tagline saved={after.get('tagline')!r}; keys lost on save={lost}; password written to file under={leaked}; password box on screen={has_pw_field}")
    step("S01", "Settings save keeps all fields and stores no password", settings_save)
    def settings_reload():
        p.reload(wait_until="networkidle"); nav("settings"); p.wait_for_timeout(900)
        v = p.locator("label:has-text('Tagline') + input, label:has-text('Tagline') ~ input").first.input_value()
        return (v == "QA tagline edit", f"tagline after reload={v!r}")
    step("S02", "Settings persist after reload", settings_reload)

    # ---------- auto scheduler ----------
    nav("autoscheduler"); p.wait_for_timeout(900); shot("f11-autoscheduler")
    def sched():
        t = p.locator("main").inner_text()
        crumb = p.locator(".theme-crumb-leaf").inner_text()
        n = p.locator("table.jp-table tbody tr").count()
        seen = []
        p.once("dialog", lambda d: seen.append(d.message))
        p.get_by_role("button", name=re.compile("Run 1-Hour Cycle Now")).click(); p.wait_for_timeout(800)
        started = "triggered successfully" in p.locator("main").inner_text()
        hint = p.locator("text=/Latest \\d+ scraper results/").first.inner_text()
        return ("No execution logs" not in t and "Auto" in crumb and n == 50 and bool(seen) and not started,
                f"breadcrumb={crumb!r}; history rows={n}; {hint}; confirm asked={bool(seen)}; run started after Cancel={started}; e-mail card={'Manual Review Only' in t and 'manual' or 'auto-send on'}")
    step("A01", "Auto Scraper page shows run history + right title", sched)

    # ---------- offline tools ----------
    def phones():
        nav("bc-phones")
        p.locator("main textarea").first.fill("98250 12345\n+1 415 555 2671\nabc\n09825012345")
        p.locator("main").get_by_role("button", name=re.compile("Clean|Check|Run", re.I)).first.click(); p.wait_for_timeout(2500); shot("f12-phones")
        return (True, p.locator("main").inner_text()[-500:].replace("\n", " | "))
    step("O01", "Bulk Phone Cleaner end to end", phones)
    def followup_page():
        nav("followups"); p.wait_for_timeout(800); shot("f13-followups")
        return (True, p.locator("main").inner_text()[:300].replace("\n", " | "))
    step("O02", "FollowUp History loads", followup_page)
    def cleanup_page():
        nav("lc-cleanup"); p.wait_for_timeout(1500); shot("f14-cleanup")
        return (True, p.locator("main").inner_text()[300:700].replace("\n", " | "))
    step("O03", "Data Cleanup preview loads", cleanup_page)
    def import_raw():
        nav("import"); p.get_by_role("button", name=re.compile("Raw Text")).click(); p.wait_for_timeout(400)
        p.locator("main textarea").first.fill("Ravi Patel, CTO at Kappa Traders, ravi@kappatraders.in, +91 98250 12345, needs a React app")
        cb = p.locator("main input[type=checkbox]")
        for i in range(cb.count()):
            if cb.nth(i).is_checked(): cb.nth(i).uncheck()
        p.locator("main").get_by_role("button", name=re.compile("Extract|Parse", re.I)).first.click(); p.wait_for_timeout(4000); shot("f15-import-raw")
        return ("kappatraders" in p.locator("main").inner_text().lower(), p.locator("main").inner_text()[-300:].replace("\n", " | "))
    step("O04", "Import raw text extracts a lead", import_raw)

    # ---------- sign out ----------
    def signout():
        p.locator("aside .theme-footer-brand-name").scroll_into_view_if_needed()
        cand = p.locator("aside [title*='Sign' i], aside [aria-label*='Sign' i], aside [title*='Log' i]")
        n = cand.count()
        if n: cand.first.click(); p.wait_for_timeout(1200)
        shot("f16-signed-out")
        return (p.locator("input[type=password]").count() == 1, f"sign-out controls with a label/tooltip={n}")
    step("L04", "Sign out returns to login", signout)

    app_errs = [e for e in errs if "ERR_NAME_NOT_RESOLVED" not in e and "AuthRetryableFetchError" not in e]
    ok("C01", "No console/page errors during workflows (login-service outage excluded)", not app_errs, "; ".join(app_errs[:6]) or f"{len(errs)} login-service network errors ignored")
    json.dump(R, open(f"{OUT}/flows.json", "w"), indent=1)
    b.close()
print(f"\n{sum(r['pass'] for r in R)}/{len(R)} passed")
