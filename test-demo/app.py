import os
import sys
import time
import json
import threading
import subprocess
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file
from settings_manager import load_settings, save_settings, format_signature
from email_service import send_smtp_email
import sync_to_supabase

from api_auth import init_auth
import followup_store

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Bind to localhost by default so the API isn't reachable from the LAN.
# Set FLASK_HOST=0.0.0.0 only when deploying behind auth + HTTPS.
BIND_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
init_auth(app, BIND_HOST)

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_PATH = os.path.join(BASE_DIR, "all_leads_master.csv")
LEADS_CSV = MASTER_PATH if os.path.exists(MASTER_PATH) else os.path.join(BASE_DIR, "leads_new.csv")

# Global state for background scraper process
scraper_process = None
scraper_logs = []
scraper_lock = threading.Lock()

def ensure_csv_status_column():
    """Ensure workflow columns exist (canonical snake_case names for the master CSV)."""
    if os.path.exists(LEADS_CSV):
        try:
            df = pd.read_csv(LEADS_CSV)
            is_master = "lead_id" in df.columns
            defaults = (
                {"status": "NEW", "email_status": "NOT_SENT", "email_sent_at": ""}
                if is_master else
                {"Status": "NEW", "Email Status": "NOT_SENT", "Email Sent At": ""}
            )
            missing = {k: v for k, v in defaults.items() if k not in df.columns}
            if missing:
                for k, v in missing.items():
                    df[k] = v
                df.to_csv(LEADS_CSV, index=False, encoding="utf-8-sig")
        except Exception:
            pass

ensure_csv_status_column()

_cached_leads_data = {}

def read_leads(source_file=None):
    global _cached_leads_data
    target = source_file or LEADS_CSV
    if not os.path.exists(target):
        # Fallback to all_leads_master.csv if leads_new.csv is absent
        if os.path.exists("all_leads_master.csv"):
            target = "all_leads_master.csv"
        else:
            return []
    try:
        current_mtime = os.path.getmtime(target)
        cache_entry = _cached_leads_data.get(target)
        if cache_entry and cache_entry.get("mtime") == current_mtime:
            return [dict(x) for x in cache_entry["leads"]]

        df = pd.read_csv(target)
        df = df.fillna("")
        leads = df.to_dict(orient="records")
        seen_ids = set()
        for idx, item in enumerate(leads):
            base_id = str(item.get("lead_id") or item.get("No") or (idx + 1))
            if base_id in seen_ids:
                base_id = f"{base_id}-{idx + 1}"
            seen_ids.add(base_id)
            item["id"] = base_id
            # Standardize names if reading from master format
            if "Company Name" not in item and "company_name" in item:
                item["Company Name"] = item["company_name"]
            if "Website URL" not in item and "website" in item:
                item["Website URL"] = item["website"]
            if "Email" not in item and "email" in item:
                item["Email"] = item["email"]
            if "Mobile Number" not in item and "mobile_number" in item:
                item["Mobile Number"] = item["mobile_number"]
            if "Address" not in item and "location" in item:
                item["Address"] = item["location"]
            if "Intent" not in item and "intent_score" in item:
                item["Intent"] = "High" if str(item.get("intent_score")) in ("10", "High") else "Medium"
            if "Lead Type" not in item and "lead_type" in item:
                item["Lead Type"] = item["lead_type"]
            item["Status"] = str(item.get("status") or item.get("Status") or "NEW").upper()

            # Standardize Lead Source
            raw_src = item.get("Source") or item.get("source") or item.get("Search Query") or "Google Search"
            clean_src = str(raw_src).strip().strip('"').strip("'")
            if "Search Engine" in clean_src:
                parts = clean_src.split("|")
                clean_src = parts[0].strip().strip('"') if parts else "Google Search"
            item["Source"] = clean_src or "Google Search"

            # Standardize Email Status (SENT vs PENDING)
            curr_email_status = str(item.get("Email Status") or item.get("email_status") or "").strip().upper()
            curr_status = str(item.get("Status", "")).strip().upper()
            if curr_email_status in ("SENT", "EMAIL_SENT") or curr_status == "EMAIL_SENT":
                item["Email Status"] = "SENT"
            else:
                item["Email Status"] = "PENDING"

        _cached_leads_data[target] = {"mtime": current_mtime, "leads": leads}
        return [dict(x) for x in leads]
    except Exception as e:
        print(f"Error reading leads: {e}")
        return []

# UI field names -> canonical master CSV column names
MASTER_COLUMN_MAP = {"Status": "status", "Email Status": "email_status", "Email Sent At": "email_sent_at"}


def update_lead_record(lead_id, updates):
    """Update one lead (matched by lead_id, legacy 'No', or row number) in the leads CSV."""
    global _cached_leads_data
    if not os.path.exists(LEADS_CSV):
        return False
    try:
        df = pd.read_csv(LEADS_CSV, dtype=str, keep_default_na=False)
        is_master = "lead_id" in df.columns
        for idx in range(len(df)):
            row = df.iloc[idx]
            curr_id = str(row.get("lead_id") or row.get("No") or (idx + 1))
            if curr_id != str(lead_id):
                continue
            for k, v in updates.items():
                col = MASTER_COLUMN_MAP.get(k, k) if is_master else k
                if col not in df.columns:
                    df[col] = ""
                df.at[df.index[idx], col] = v
            if is_master and "last_updated_at" in df.columns:
                df.at[df.index[idx], "last_updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            tmp = LEADS_CSV + ".tmp"
            df.to_csv(tmp, index=False, encoding="utf-8-sig")
            os.replace(tmp, LEADS_CSV)
            _cached_leads_data.clear()
            return True
    except Exception as e:
        print(f"Error updating {LEADS_CSV}: {e}")
    return False

def _lead_index():
    """lead id -> {"id", "name", "email", "status", "source", "phone"} from the leads file."""
    index = {}
    for l in read_leads():
        index[str(l.get("id"))] = {
            "id": str(l.get("id")),
            "name": str(l.get("Company Name") or l.get("company_name") or l.get("full_name") or ""),
            "email": str(l.get("Email") or "").split(",")[0].strip(),
            "status": str(l.get("Status") or "NEW"),
            "source": str(l.get("Source") or ""),
            # some scraped rows hold hundreds of numbers - show only the first one
            "phone": str(l.get("Mobile Number") or "").split(",")[0].strip(),
        }
    return index


def _lead_info(lead_id):
    return _lead_index().get(str(lead_id)) if lead_id not in (None, "") else None


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/leads", methods=["GET"])
def get_leads():
    leads = read_leads()
    return jsonify({"success": True, "leads": leads, "total": len(leads)})

@app.route("/api/leads/<lead_id>/status", methods=["PATCH"])
def patch_lead_status(lead_id):
    data = request.json or {}
    new_status = data.get("status")
    if not new_status:
        return jsonify({"success": False, "error": "status is required"}), 400
    lead = _lead_info(lead_id)
    old_status = str((lead or {}).get("status") or "NEW").upper()
    success = update_lead_record(lead_id, {"Status": new_status})
    if success and str(new_status).upper() != old_status:
        followup_store.safe_log(lead_id, "status_change", f"Status: {old_status} → {str(new_status).upper()}",
                                source="dashboard", lead_name=(lead or {}).get("name", ""),
                                lead_email=(lead or {}).get("email", ""))
    return jsonify({"success": success})

@app.route("/api/leads/send-email", methods=["POST"])
def send_single_lead_email():
    data = request.json or {}
    lead_id = data.get("id")
    to_email = data.get("to")
    subject = data.get("subject")
    message = data.get("message")

    if not to_email or not subject or not message:
        return jsonify({"success": False, "error": "to, subject, and message required"}), 400

    # User manually clicked Send in UI: allow manual test/send with bypass_duplicate_check=True
    result = send_smtp_email(to_email, subject, message, bypass_duplicate_check=True)
    if result.get("success"):
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        update_lead_record(lead_id, {
            "Email Status": "SENT",
            "Email Sent At": now_str,
            "Status": "EMAIL_SENT"
        })
        lead = _lead_info(lead_id) or {}
        followup_store.safe_log(lead_id, "email_sent", f"Email sent: {subject}", details=message,
                                source="dashboard", lead_name=lead.get("name", ""), lead_email=to_email)
        return jsonify({"success": True, "message": "Email sent successfully via Gmail SMTP!"})
    else:
        return jsonify({"success": False, "error": result.get("error", "SMTP send failed")}), 500

@app.route("/api/leads/bulk-email", methods=["POST"])
def send_bulk_leads_email():
    data = request.json or {}
    lead_ids = data.get("lead_ids", [])
    subject_tpl = data.get("subject", "")
    message_tpl = data.get("message", "")
    delay_ms = int(data.get("delay_ms", 1500))

    if not lead_ids or not subject_tpl or not message_tpl:
        return jsonify({"success": False, "error": "lead_ids, subject, and message are required"}), 400

    all_leads = {l["id"]: l for l in read_leads()}
    settings = load_settings()
    sig = format_signature(settings)

    results = []
    sent_count = 0
    failed_count = 0

    for idx, lid in enumerate(lead_ids):
        lead = all_leads.get(str(lid))
        if not lead:
            continue

        raw_emails = str(lead.get("Email", "")).split(",")
        to_email = raw_emails[0].strip() if raw_emails else ""

        if not to_email or "@" not in to_email or to_email == "N/A":
            results.append({"id": lid, "email": to_email, "success": False, "error": "No valid email"})
            failed_count += 1
            continue

        comp = lead.get("Company Name", "your company")
        name = comp
        loc = lead.get("Address", "your region")

        sub = (subject_tpl
               .replace("{company}", comp)
               .replace("{name}", name)
               .replace("{location}", loc))

        body = (message_tpl
                .replace("{company}", comp)
                .replace("{name}", name)
                .replace("{location}", loc))

        if sig and sig.strip()[:20] not in body:
            body = f"{body}\n\n---\n{sig.strip()}"

        res = send_smtp_email(to_email, sub, body)
        if res.get("success"):
            sent_count += 1
            now_str = time.strftime("%Y-%m-%d %H:%M:%S")
            update_lead_record(lid, {
                "Email Status": "SENT",
                "Email Sent At": now_str,
                "Status": "EMAIL_SENT"
            })
            followup_store.safe_log(lid, "email_sent", f"Email sent: {sub}", details=body,
                                    source="bulk email", lead_name=comp, lead_email=to_email)
            results.append({"id": lid, "email": to_email, "success": True})
        else:
            failed_count += 1
            results.append({"id": lid, "email": to_email, "success": False, "error": res.get("error")})

        if idx < len(lead_ids) - 1 and delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

    return jsonify({
        "success": True,
        "total": len(lead_ids),
        "sent": sent_count,
        "failed": failed_count,
        "results": results
    })

@app.route("/api/scraper/status", methods=["GET"])
def get_scraper_status():
    global scraper_process, scraper_logs
    is_running = scraper_process is not None and scraper_process.poll() is None
    with scraper_lock:
        logs_slice = scraper_logs[-100:]
    return jsonify({
        "running": is_running,
        "logs": logs_slice
    })

@app.route("/api/scraper/start", methods=["POST"])
def start_scraper():
    global scraper_process, scraper_logs
    if scraper_process is not None and scraper_process.poll() is None:
        return jsonify({"success": False, "error": "Scraper is already running!"}), 400

    data = request.json or {}
    mode = data.get("mode", "quick")  # "quick" -> scraper.py, "all" -> run_all_scrapers.py
    script_to_run = "run_all_scrapers.py" if mode == "all" else "scraper.py"

    def run_worker():
        global scraper_process, scraper_logs
        with scraper_lock:
            scraper_logs = [f"[{time.strftime('%H:%M:%S')}] Launching {script_to_run} ({'All 12 Harvesters (Includes Maps & Telegram)' if mode == 'all' else 'Live Search Scraper'})..."]
        
        proc = subprocess.Popen(
            [sys.executable, script_to_run],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        scraper_process = proc

        for line in proc.stdout:
            clean = line.strip()
            if clean:
                with scraper_lock:
                    scraper_logs.append(clean)
                    if len(scraper_logs) > 300:
                        scraper_logs.pop(0)

        proc.wait()
        with scraper_lock:
            scraper_logs.append(f"[{time.strftime('%H:%M:%S')}] {script_to_run} finished with return code {proc.returncode}.")
            scraper_logs.append(f"[{time.strftime('%H:%M:%S')}] Finalizing Supabase Database Sync...")
        
        try:
            target_csv = "all_leads_master.csv" if mode == "all" else "leads_new.csv"
            sync_to_supabase.sync(csv_filepath=target_csv)
            with scraper_lock:
                scraper_logs.append(f"[{time.strftime('%H:%M:%S')}] Supabase sync completed successfully!")
        except Exception as e:
            with scraper_lock:
                scraper_logs.append(f"[{time.strftime('%H:%M:%S')}] Supabase sync notice: {e}")

        with scraper_lock:
            scraper_logs.append(f"[{time.strftime('%H:%M:%S')}] 🛑 Scraper engine automatically stopped & finished.")
        scraper_process = None

    t = threading.Thread(target=run_worker, daemon=True)
    t.start()
    return jsonify({"success": True, "message": f"{script_to_run} started in background!", "mode": mode})

@app.route("/api/scraper/stop", methods=["POST"])
def stop_scraper():
    global scraper_process, scraper_logs
    if scraper_process is not None and scraper_process.poll() is None:
        try:
            scraper_process.terminate()
            scraper_process = None
            with scraper_lock:
                scraper_logs.append(f"[{time.strftime('%H:%M:%S')}] 🛑 Background scraper stopped by user.")
            return jsonify({"success": True, "message": "Scraper stopped successfully."})
        except Exception as e:
            scraper_process = None
            return jsonify({"success": False, "error": str(e)}), 500
    scraper_process = None
    return jsonify({"success": True, "message": "Scraper is already stopped."})

@app.route("/api/sync-supabase", methods=["POST"])
def trigger_supabase_sync():
    try:
        if sync_to_supabase.sync() is False:
            return jsonify({"success": False, "error": "Supabase sync did not run: add SUPABASE_URL and a Supabase key in .env."}), 400
        return jsonify({"success": True, "message": "Leads synced to Supabase successfully!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/settings", methods=["GET", "POST"])
def handle_settings():
    if request.method == "POST":
        data = request.json or {}
        save_settings(data)
        return jsonify({"success": True, "settings": data})
    else:
        settings = load_settings()
        sig = format_signature(settings)
        return jsonify({"success": True, "settings": settings, "formattedSignature": sig})

@app.route("/api/settings/api-keys", methods=["GET"])
def api_keys_status():
    """Which API keys are set in .env (never returns the values)."""
    from api_keys_catalog import integration_status
    return jsonify({"success": True, **integration_status()})

@app.route("/api/settings/test-email", methods=["POST"])
def test_company_email():
    settings = load_settings()
    sig = format_signature(settings)
    to_email = settings.get("email", "sangeetainfotech19@gmail.com")
    subject = "[Test] Sangeeta Infotech Outreach Signature Verification"
    body = (
        "Hello,\n\n"
        "This is an automated test confirming that your Sangeeta Infotech signature and SMTP settings "
        "are active and delivering properly.\n\n"
        f"---\n{sig}"
    )
    result = send_smtp_email(to_email, subject, body)
    return jsonify(result)

@app.route("/api/export-csv")
def export_csv():
    if os.path.exists(LEADS_CSV):
        return send_file(LEADS_CSV, as_attachment=True, download_name="sangeeta_infotech_leads.csv")
    return "No leads CSV found", 404

# ==============================================================================
# IMPORT LEADS & AUTOMATION ENGINE ROUTES
# ==============================================================================
import lead_importer

# Live Search moved to Scraping / Mining -> Search Engines (/api/search-engine/*).

@app.route("/api/import/chat", methods=["POST"])
def import_chat():
    try:
        chat_text = ""
        if "file" in request.files:
            file = request.files["file"]
            raw_bytes = file.read()
            filename = (file.filename or "").lower()
            if filename.endswith(".zip") or raw_bytes.startswith(b"PK\x03\x04"):
                import zipfile, io
                try:
                    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
                        txt_files = [n for n in z.namelist() if n.lower().endswith(".txt")]
                        if not txt_files:
                            return jsonify({"success": False, "error": "No .txt chat file found inside the uploaded ZIP archive."}), 400
                        # Prefer _chat.txt or the largest .txt file in the archive
                        target_name = "_chat.txt" if "_chat.txt" in txt_files else max(txt_files, key=lambda n: z.getinfo(n).file_size)
                        chat_text = z.read(target_name).decode("utf-8", errors="ignore")
                except Exception as ze:
                    return jsonify({"success": False, "error": f"Failed to unzip chat archive: {ze}"}), 400
            else:
                chat_text = raw_bytes.decode("utf-8", errors="ignore")
        elif request.is_json:
            chat_text = request.json.get("text", "")
        elif request.form and "text" in request.form:
            chat_text = request.form.get("text", "")

        # Also support if text was read as latin-1/binary zip string
        if isinstance(chat_text, str) and chat_text.startswith("PK\x03\x04"):
            import zipfile, io
            try:
                with zipfile.ZipFile(io.BytesIO(chat_text.encode("latin-1"))) as z:
                    txt_files = [n for n in z.namelist() if n.lower().endswith(".txt")]
                    if txt_files:
                        target_name = "_chat.txt" if "_chat.txt" in txt_files else max(txt_files, key=lambda n: z.getinfo(n).file_size)
                        chat_text = z.read(target_name).decode("utf-8", errors="ignore")
            except Exception:
                pass

        if not chat_text.strip():
            return jsonify({"success": False, "error": "No chat content or file uploaded."}), 400

        leads = lead_importer.parse_whatsapp_chat(chat_text)
        enriched = lead_importer.check_duplicates_against_master(leads, master_csv=LEADS_CSV)
        return jsonify({"success": True, "leads": enriched, "count": len(enriched)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/import/raw-text", methods=["POST"])
def import_raw_text():
    try:
        data = request.json or {}
        raw_text = data.get("text", "").strip()
        crawl_urls = bool(data.get("crawl_urls", True))

        if not raw_text:
            return jsonify({"success": False, "error": "Text content or URLs required."}), 400

        leads = lead_importer.parse_raw_text(raw_text, crawl_urls=crawl_urls)
        enriched = lead_importer.check_duplicates_against_master(leads, master_csv=LEADS_CSV)
        return jsonify({"success": True, "leads": enriched, "count": len(enriched)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/import/commit", methods=["POST"])
def import_commit():
    try:
        global _cached_leads_data
        data = request.json or {}
        leads = data.get("leads", [])
        send_outreach_email = bool(data.get("send_outreach_email", False))

        if not leads:
            return jsonify({"success": False, "error": "No leads selected to import."}), 400

        result = lead_importer.commit_imported_leads(
            leads_to_commit=leads,
            send_outreach_email=send_outreach_email,
            master_csv=LEADS_CSV
        )
        # Invalidate read_leads cache so UI immediately refreshes
        _cached_leads_data.clear()

        return jsonify({"success": True, "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==============================================================================
# JOB PORTAL SCRAPER (job_portals.py)
# ==============================================================================
import job_portals
from lead_normalizer import MasterLeadRegistry

MAX_JOBS_PER_SAVE = 500
job_save_lock = threading.Lock()


@app.route("/api/job-portals", methods=["GET"])
def get_job_portals():
    return jsonify({
        "success": True,
        "portals": job_portals.list_portals(),
        "states": [job_portals.ALL_INDIA] + sorted(job_portals.INDIAN_STATES.keys()),
        "maxTitles": job_portals.MAX_TITLES,
    })


@app.route("/api/job-portals/search", methods=["POST"])
def search_job_portals():
    data = request.get_json(silent=True) or {}
    try:
        params = {"titles": data.get("titles"), "state": data.get("state"), "portals": data.get("portals")}
        result = search_cache.cached_search(
            "jobportals", params, lambda: job_portals.search_jobs(params["titles"], params["state"], params["portals"]),
            status_key="portals", refresh=bool(data.get("refresh")))
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    return jsonify({"success": True, **result})


@app.route("/api/job-portals/save", methods=["POST"])
def save_job_portal_results():
    global _cached_leads_data
    data = request.get_json(silent=True) or {}
    jobs = data.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        return jsonify({"success": False, "error": "Select at least one job to save."}), 400
    if len(jobs) > MAX_JOBS_PER_SAVE:
        return jsonify({"success": False, "error": f"Save at most {MAX_JOBS_PER_SAVE} jobs at a time."}), 400
    valid = [j for j in jobs if isinstance(j, dict) and (j.get("company") or j.get("title")) and j.get("url")]
    if not valid:
        return jsonify({"success": False, "error": "The selected jobs have no company/title or link."}), 400

    counts = {"added": 0, "updated": 0, "duplicate": 0, "skipped_invalid": len(jobs) - len(valid)}
    with job_save_lock:
        registry = MasterLeadRegistry(MASTER_PATH)
        for job in valid:
            outcome, _ = registry.add_lead(job_portals.job_to_raw_lead(job), default_source="Job Portal")
            counts[outcome] = counts.get(outcome, 0) + 1
        if not registry.save_master_safely():
            return jsonify({"success": False, "error": "Could not write the leads file."}), 500
    _cached_leads_data.clear()
    return jsonify({"success": True, **counts})


# ==============================================================================
# FOLLOWUP HISTORY (followup_store.py) - Phase 1: activity log + follow-up queue
# ==============================================================================

def _with_lead(rows, leads=None):
    """Adds current lead details (name, status, ...) to activity/follow-up rows."""
    leads = leads if leads is not None else _lead_index()
    out = []
    for r in rows:
        lead = leads.get(r.get("lead_id")) or {}
        out.append({**r, "lead": lead, "lead_name": lead.get("name") or r.get("lead_name", ""),
                    "lead_exists": bool(lead)})
    return out


@app.route("/api/followups/summary", methods=["GET"])
def followups_summary():
    return jsonify({"success": True, **followup_store.summary()})


@app.route("/api/followups/queue", methods=["GET"])
def followups_queue():
    try:
        rows = followup_store.queue(request.args.get("bucket", "all"))
    except followup_store.FollowupError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    last = followup_store.last_contact_by_lead()
    items = _with_lead(rows)
    for item in items:
        contact = last.get(item["lead_id"])
        item["last_contact"] = {"type": contact["type"], "summary": contact["summary"],
                                "occurred_at": contact["occurred_at"]} if contact else None
    return jsonify({"success": True, "items": items, "total": len(items)})


@app.route("/api/followups/history", methods=["GET"])
def followups_history():
    try:
        types = [t for t in request.args.get("types", "").split(",") if t]
        res = followup_store.history(lead_id=request.args.get("lead_id", ""), types=types,
                                     q=request.args.get("q", ""), limit=request.args.get("limit", 100),
                                     offset=request.args.get("offset", 0))
    except (followup_store.FollowupError, ValueError) as e:
        return jsonify({"success": False, "error": str(e)}), 400
    return jsonify({"success": True, "items": _with_lead(res["items"]), "total": res["total"]})


@app.route("/api/leads/<lead_id>/timeline", methods=["GET"])
def lead_timeline(lead_id):
    lead = _lead_info(lead_id)
    res = followup_store.history(lead_id=lead_id, limit=500)
    if not lead and not res["total"]:
        return jsonify({"success": False, "error": "Lead not found"}), 404
    pending = [r for r in followup_store.queue("all") if r["lead_id"] == str(lead_id)]
    return jsonify({"success": True, "lead": lead or {"id": lead_id, "name": ""},
                    "items": res["items"], "pending_followup": pending[0] if pending else None})


@app.route("/api/followups/activities", methods=["POST"])
def followups_add_activity():
    data = request.get_json(silent=True) or {}
    lead = _lead_info(data.get("lead_id"))
    if not lead:
        return jsonify({"success": False, "error": "Select a valid lead"}), 400
    try:
        activity = followup_store.add_activity(
            lead["id"], data.get("type", ""), data.get("summary", ""), details=data.get("details", ""),
            occurred_at=data.get("occurred_at", ""), source="manual",
            lead_name=lead["name"], lead_email=lead["email"])
        followup = None
        if data.get("next_followup_at"):
            followup = followup_store.schedule_followup(
                lead["id"], data["next_followup_at"], data.get("next_followup_note", ""),
                lead_name=lead["name"], lead_email=lead["email"])
    except followup_store.FollowupError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    return jsonify({"success": True, "activity": activity, "followup": followup})


@app.route("/api/followups/schedule", methods=["POST"])
def followups_schedule():
    data = request.get_json(silent=True) or {}
    lead = _lead_info(data.get("lead_id"))
    if not lead:
        return jsonify({"success": False, "error": "Select a valid lead"}), 400
    try:
        row = followup_store.schedule_followup(lead["id"], data.get("due_at", ""), data.get("note", ""),
                                               lead_name=lead["name"], lead_email=lead["email"])
    except followup_store.FollowupError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    return jsonify({"success": True, "followup": row})


@app.route("/api/followups/<activity_id>", methods=["PATCH"])
def followups_update(activity_id):
    data = request.get_json(silent=True) or {}
    try:
        row = followup_store.update_followup(activity_id, data.get("action", ""), data.get("due_at", ""))
    except LookupError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except followup_store.FollowupError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    return jsonify({"success": True, "followup": row})


@app.route("/api/followups/import-sent-emails", methods=["POST"])
def followups_import_sent_emails():
    by_email = {}
    for l in read_leads():  # a lead can have several emails: match on any of them
        name = str(l.get("Company Name") or l.get("company_name") or "")
        for email in str(l.get("Email") or "").split(","):
            email = email.strip().lower()
            if email and "@" in email:
                by_email.setdefault(email, {"id": str(l.get("id")), "name": name})
    return jsonify({"success": True, **followup_store.import_sent_emails(by_email)})


# ------------------------------------------------------------------------------
# FOLLOWUP PHASE 2: automatic sequence, Gmail reply check, reply-rate report
# ------------------------------------------------------------------------------
import followup_sequence
import reply_checker

# A reply only moves a lead forward from these statuses (never downgrades MEETING / WON / ...)
REPLY_UPGRADEABLE = {"", "NEW", "CONTACTED", "EMAIL_SENT"}


def _source_family(source):
    return str(source or "Unknown").split("|")[0].split(" (")[0].strip() or "Unknown"


def _apply_lead_updates(updates, leads):
    """Applies reply_checker updates to the leads file; returns how many leads changed."""
    changed = 0
    for u in updates:
        lead = leads.get(str(u["lead_id"]))
        if not lead:
            continue
        if u.get("status") and lead["status"].upper() in REPLY_UPGRADEABLE:
            if update_lead_record(lead["id"], {"Status": u["status"]}):
                followup_store.safe_log(lead["id"], "status_change", f"Status: {lead['status'].upper()} → {u['status']}",
                                        source="gmail", lead_name=lead["name"], lead_email=lead["email"])
                lead["status"] = u["status"]
                changed += 1
        if u.get("email_status") and update_lead_record(lead["id"], {"Email Status": u["email_status"]}):
            changed += 1
    return changed


@app.route("/api/followups/sequence", methods=["GET"])
def followups_sequence():
    plan = followup_sequence.plan(_lead_index())
    signature = format_signature(load_settings())
    due = [{**item, "preview": followup_sequence.render(item, signature)} for item in plan["due"]]
    return jsonify({
        "success": True,
        "config": followup_sequence.config(),
        "imap_configured": reply_checker.is_configured(),
        "last_checked_at": reply_checker.last_checked_at(),
        "due": due,
        "waiting": plan["waiting"][:50], "waiting_total": len(plan["waiting"]),
        "stopped": plan["stopped"][:50], "stopped_total": len(plan["stopped"]),
    })


@app.route("/api/followups/sequence/send", methods=["POST"])
def followups_sequence_send():
    data = request.get_json(silent=True) or {}
    lead_ids = data.get("lead_ids")
    if not isinstance(lead_ids, list) or not lead_ids:
        return jsonify({"success": False, "error": "Select at least one follow-up to send."}), 400
    if len(lead_ids) > 50:
        return jsonify({"success": False, "error": "Send at most 50 follow-ups at a time."}), 400
    wanted = {str(x) for x in lead_ids}
    due = [i for i in followup_sequence.plan(_lead_index())["due"] if i["lead_id"] in wanted]
    if not due:
        return jsonify({"success": False, "error": "None of the selected follow-ups are due any more."}), 400
    # Follow-ups go to an address we already emailed, so the one-email-per-address shield is bypassed
    # here on purpose - only for steps the sequence planner marked as due.
    result = followup_sequence.send(
        due, lambda to, sub, body: send_smtp_email(to, sub, body, bypass_duplicate_check=True),
        signature=format_signature(load_settings()))
    return jsonify({"success": True, **result, "not_due": len(wanted) - len(due)})


@app.route("/api/followups/sequence/stop", methods=["POST"])
def followups_sequence_stop():
    data = request.get_json(silent=True) or {}
    lead = _lead_info(data.get("lead_id"))
    if not lead:
        return jsonify({"success": False, "error": "Select a valid lead"}), 400
    try:
        row = followup_sequence.stop(lead["id"], data.get("reason", ""), lead["name"], lead["email"])
    except followup_store.FollowupError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    return jsonify({"success": True, "activity": row})


@app.route("/api/followups/check-replies", methods=["POST"])
def followups_check_replies():
    if not reply_checker.is_configured():
        return jsonify({"success": False, "error": "Gmail reply check is not set up. Add IMAP_USER and "
                                                   "IMAP_PASSWORD (a Gmail App Password) to .env."}), 400
    leads = _lead_index()
    email_to_lead = {}
    for l in read_leads():
        for em in str(l.get("Email") or "").split(","):
            em = em.strip().lower()
            if em and "@" in em:
                email_to_lead.setdefault(em, leads.get(str(l.get("id")), {}))
    try:
        events = reply_checker.fetch_events(reply_checker.contacted_emails())
    except RuntimeError as e:
        return jsonify({"success": False, "error": str(e)}), 502
    result = reply_checker.record_events(events, email_to_lead)
    changed = _apply_lead_updates(result["updates"], leads)
    counts = {t: sum(1 for e in events if e["type"] == t) for t in ("reply", "opted_out", "bounce")}
    return jsonify({"success": True, "checked_at": reply_checker.last_checked_at(), "new_events": result["logged"],
                    "already_known": result["skipped"], "leads_updated": changed, **counts})


@app.route("/api/followups/templates", methods=["GET", "PUT", "DELETE"])
def followups_templates():
    try:
        if request.method == "PUT":
            data = request.get_json(silent=True) or {}
            templates = followup_sequence.save_templates(data.get("templates"))
        elif request.method == "DELETE":
            templates = followup_sequence.reset_templates()
        else:
            templates = followup_sequence.load_templates()
    except followup_sequence.TemplateError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    return jsonify({
        "success": True, "templates": templates,
        "customized": followup_sequence.templates_customized(),
        "defaults": followup_sequence.DEFAULT_TEMPLATES,
        "placeholders": list(followup_sequence.PLACEHOLDERS),
        "opt_out_line": followup_sequence.OPT_OUT_LINE,
    })


@app.route("/api/followups/report", methods=["GET"])
def followups_report():
    sources = {lid: _source_family(l["source"]) for lid, l in _lead_index().items()}
    return jsonify({"success": True, **followup_store.report(sources)})


# ==============================================================================
# CRM SOURCES (crm_sources.py): business directories + B2B contact databases
# ==============================================================================
import crm_sources
import search_cache


@app.route("/api/crm-sources", methods=["GET"])
def get_crm_sources():
    return jsonify({
        "success": True,
        "sources": crm_sources.list_sources(),
        "states": [job_portals.ALL_INDIA] + sorted(job_portals.INDIAN_STATES.keys()),
        "maxKeywords": crm_sources.MAX_KEYWORDS, "maxTitles": crm_sources.MAX_TITLES,
    })


@app.route("/api/crm-sources/search", methods=["POST"])
def search_crm_sources():
    data = request.get_json(silent=True) or {}
    try:
        params = {k: data.get(k) for k in ("keywords", "titles", "state", "city", "sources")}
        result = search_cache.cached_search(
            "crmsources", params, lambda: crm_sources.search(params["keywords"], params["titles"], params["state"],
                                                             params["city"] or "", params["sources"]),
            status_key="sources", refresh=bool(data.get("refresh")))
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    return jsonify({"success": True, **result})


@app.route("/api/crm-sources/save", methods=["POST"])
def save_crm_source_results():
    global _cached_leads_data
    data = request.get_json(silent=True) or {}
    rows = data.get("results")
    if not isinstance(rows, list) or not rows:
        return jsonify({"success": False, "error": "Select at least one result to save."}), 400
    if len(rows) > MAX_JOBS_PER_SAVE:
        return jsonify({"success": False, "error": f"Save at most {MAX_JOBS_PER_SAVE} results at a time."}), 400
    valid = [r for r in rows if isinstance(r, dict) and (r.get("company") or r.get("contact_name"))
             and (r.get("url") or r.get("website") or r.get("email") or r.get("phone"))]
    if not valid:
        return jsonify({"success": False, "error": "The selected results have no name or contact details."}), 400
    counts = {"added": 0, "updated": 0, "duplicate": 0, "skipped_invalid": len(rows) - len(valid)}
    with job_save_lock:
        registry = MasterLeadRegistry(MASTER_PATH)
        for r in valid:
            outcome, _ = registry.add_lead(crm_sources.result_to_raw_lead(r), default_source="CRM Source")
            counts[outcome] = counts.get(outcome, 0) + 1
        if not registry.save_master_safely():
            return jsonify({"success": False, "error": "Could not write the leads file."}), 500
    _cached_leads_data.clear()
    return jsonify({"success": True, **counts})



# ==============================================================================
# Scraping / Mining -> Search Engines (+ Deep Search)
# ==============================================================================
import search_engine
import deep_search


@app.route("/api/search-engine", methods=["GET"])
def get_search_engine_options():
    return jsonify({
        "success": True,
        "engines": search_engine.list_engines(),
        "modes": search_engine.list_modes(),
        "states": [job_portals.ALL_INDIA] + sorted(job_portals.INDIAN_STATES.keys()),
        "maxKeywords": search_engine.MAX_KEYWORDS,
        "maxAudience": search_engine.MAX_AUDIENCE,
        "maxResultsChoices": list(search_engine.MAX_RESULTS_CHOICES),
        "timeFilters": list(search_engine.TIME_FILTERS.keys()),
        "deepBatch": deep_search.MAX_ITEMS_PER_CALL,
        "hunterAvailable": bool(os.getenv("HUNTER_API_KEY", "").strip()),
    })


@app.route("/api/search-engine/search", methods=["POST"])
def run_search_engine():
    data = request.get_json(silent=True) or {}
    keys = ("keywords", "audience", "mode", "custom_query", "state", "city", "engine", "time", "max_results", "exclude_sites")
    params = {k: data.get(k) for k in keys}
    # the engine actually used is part of the cache key (adding a key changes "auto")
    params["engine_used"] = search_engine.resolve_engine(str(data.get("engine") or "auto"))
    try:
        result = search_cache.cached_search(
            "searchengine", params, lambda: search_engine.search(params),
            status_key="engines", refresh=bool(data.get("refresh")))
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    # "already in leads" must reflect the database now, also for saved results
    for r in result.get("results", []):
        r["in_leads"], r["match"] = False, ""
    search_engine.mark_existing(result.get("results", []), MASTER_PATH)
    return jsonify({"success": True, **result})


@app.route("/api/search-engine/deep", methods=["POST"])
def run_deep_search():
    data = request.get_json(silent=True) or {}
    try:
        result = deep_search.deep_search(data.get("items"), str(data.get("engine") or "auto"),
                                         bool(data.get("use_hunter")), str(data.get("place") or ""))
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    return jsonify({"success": True, **result})


@app.route("/api/search-engine/save", methods=["POST"])
def save_search_engine_results():
    global _cached_leads_data
    data = request.get_json(silent=True) or {}
    rows = data.get("results")
    if not isinstance(rows, list) or not rows:
        return jsonify({"success": False, "error": "Select at least one result to save."}), 400
    if len(rows) > MAX_JOBS_PER_SAVE:
        return jsonify({"success": False, "error": f"Save at most {MAX_JOBS_PER_SAVE} results at a time."}), 400
    valid = [r for r in rows if isinstance(r, dict) and r.get("company")
             and (r.get("url") or r.get("website") or r.get("email") or r.get("phone"))]
    if not valid:
        return jsonify({"success": False, "error": "The selected results have no name or link."}), 400
    leads = [search_engine.result_to_raw_lead(r) for r in valid]
    with job_save_lock:
        res = lead_importer.commit_imported_leads(leads, send_outreach_email=bool(data.get("send_outreach_email")),
                                                  master_csv=MASTER_PATH)
    if not res.get("success"):
        return jsonify({"success": False, "error": "Could not write the leads file."}), 500
    _cached_leads_data.clear()
    return jsonify({"success": True, "added": res["added"], "updated": res["updated"],
                    "duplicate": res["duplicates"], "skipped_invalid": len(rows) - len(valid),
                    "emails_sent": res["emails_sent"], "supabase_synced": res["supabase_synced"]})


# ==============================================================================
# Scraping / Mining -> Global Directories (module: global_directories.py)
# ==============================================================================
import global_directories


@app.route("/api/global-directories", methods=["GET"])
def get_global_directories():
    return jsonify({"success": True, "sources": global_directories.list_sources(),
                    "countries": global_directories.COUNTRIES, "maxKeywords": global_directories.MAX_KEYWORDS})


@app.route("/api/global-directories/search", methods=["POST"])
def search_global_directories():
    data = request.get_json(silent=True) or {}
    params = {k: data.get(k) for k in ("keywords", "audience", "country", "region", "city", "sources")}
    try:
        result = search_cache.cached_search("globaldirectories", params, lambda: global_directories.search(params),
                                            status_key="sources", refresh=bool(data.get("refresh")))
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    for r in result.get("results", []):
        r["in_leads"], r["match"] = False, ""
    search_engine.mark_existing(result.get("results", []), MASTER_PATH)
    return jsonify({"success": True, **result})


@app.route("/api/global-directories/save", methods=["POST"])
def save_global_directory_results():
    global _cached_leads_data
    data = request.get_json(silent=True) or {}
    rows = data.get("results")
    if not isinstance(rows, list) or not rows:
        return jsonify({"success": False, "error": "Select at least one result to save."}), 400
    if len(rows) > MAX_JOBS_PER_SAVE:
        return jsonify({"success": False, "error": f"Save at most {MAX_JOBS_PER_SAVE} results at a time."}), 400
    valid = [r for r in rows if isinstance(r, dict) and r.get("company")
             and (r.get("url") or r.get("website") or r.get("email") or r.get("phone"))]
    if not valid:
        return jsonify({"success": False, "error": "The selected results have no name or contact details."}), 400
    counts = {"added": 0, "updated": 0, "duplicate": 0, "skipped_invalid": len(rows) - len(valid)}
    with job_save_lock:
        registry = MasterLeadRegistry(MASTER_PATH)
        for r in valid:
            outcome, _ = registry.add_lead(global_directories.result_to_raw_lead(r), default_source="Global Directory")
            counts[outcome] = counts.get(outcome, 0) + 1
        if not registry.save_master_safely():
            return jsonify({"success": False, "error": "Could not write the leads file."}), 500
    _cached_leads_data.clear()
    return jsonify({"success": True, **counts})


# ==============================================================================
# Scraping / Mining -> Google Maps (module: maps_sources.py)
# ==============================================================================
import maps_sources


@app.route("/api/maps", methods=["GET"])
def get_maps_sources():
    return jsonify({"success": True, "sources": maps_sources.list_sources(),
                    "states": [job_portals.ALL_INDIA] + sorted(job_portals.INDIAN_STATES.keys()),
                    "maxKeywords": maps_sources.MAX_KEYWORDS, "minRatings": list(maps_sources.MIN_RATINGS),
                    "deepBatch": deep_search.MAX_ITEMS_PER_CALL})


@app.route("/api/maps/search", methods=["POST"])
def search_maps():
    data = request.get_json(silent=True) or {}
    params = {k: data.get(k) for k in ("keywords", "audience", "state", "city", "sources", "min_rating", "website")}
    try:
        result = search_cache.cached_search("maps", params, lambda: maps_sources.search(params),
                                            status_key="sources", refresh=bool(data.get("refresh")))
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    for r in result.get("results", []):
        r["in_leads"], r["match"] = False, ""
    search_engine.mark_existing(result.get("results", []), MASTER_PATH)
    return jsonify({"success": True, **result})


@app.route("/api/maps/save", methods=["POST"])
def save_maps_results():
    global _cached_leads_data
    data = request.get_json(silent=True) or {}
    rows = data.get("results")
    if not isinstance(rows, list) or not rows:
        return jsonify({"success": False, "error": "Select at least one result to save."}), 400
    if len(rows) > MAX_JOBS_PER_SAVE:
        return jsonify({"success": False, "error": f"Save at most {MAX_JOBS_PER_SAVE} results at a time."}), 400
    valid = [r for r in rows if isinstance(r, dict) and r.get("company")
             and (r.get("url") or r.get("website") or r.get("email") or r.get("phone"))]
    if not valid:
        return jsonify({"success": False, "error": "The selected results have no name or contact details."}), 400
    counts = {"added": 0, "updated": 0, "duplicate": 0, "skipped_invalid": len(rows) - len(valid)}
    with job_save_lock:
        registry = MasterLeadRegistry(MASTER_PATH)
        for r in valid:
            outcome, _ = registry.add_lead(maps_sources.result_to_raw_lead(r), default_source="Google Maps")
            counts[outcome] = counts.get(outcome, 0) + 1
        if not registry.save_master_safely():
            return jsonify({"success": False, "error": "Could not write the leads file."}), 500
    _cached_leads_data.clear()
    return jsonify({"success": True, **counts})


# ==============================================================================
# Scraping / Mining -> Ecommerce Platforms (module: ecommerce_sources.py)
# ==============================================================================
import ecommerce_sources


@app.route("/api/ecommerce", methods=["GET"])
def get_ecommerce_sources():
    return jsonify({"success": True, "sources": ecommerce_sources.list_sources(),
                    "engines": search_engine.list_engines(),
                    "states": [job_portals.ALL_INDIA] + sorted(job_portals.INDIAN_STATES.keys()),
                    "maxKeywords": ecommerce_sources.MAX_KEYWORDS, "deepBatch": deep_search.MAX_ITEMS_PER_CALL})


@app.route("/api/ecommerce/search", methods=["POST"])
def search_ecommerce():
    data = request.get_json(silent=True) or {}
    params = {k: data.get(k) for k in ("keywords", "audience", "state", "city", "sources", "engine")}
    params["engine_used"] = search_engine.resolve_engine(str(data.get("engine") or "auto"))
    try:
        result = search_cache.cached_search("ecommerce", params, lambda: ecommerce_sources.search(params),
                                            status_key="sources", refresh=bool(data.get("refresh")))
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    for r in result.get("results", []):
        r["in_leads"], r["match"] = False, ""
    search_engine.mark_existing(result.get("results", []), MASTER_PATH)
    return jsonify({"success": True, **result})


@app.route("/api/ecommerce/save", methods=["POST"])
def save_ecommerce_results():
    global _cached_leads_data
    data = request.get_json(silent=True) or {}
    rows = data.get("results")
    if not isinstance(rows, list) or not rows:
        return jsonify({"success": False, "error": "Select at least one result to save."}), 400
    if len(rows) > MAX_JOBS_PER_SAVE:
        return jsonify({"success": False, "error": f"Save at most {MAX_JOBS_PER_SAVE} results at a time."}), 400
    valid = [r for r in rows if isinstance(r, dict) and r.get("company")
             and (r.get("url") or r.get("website") or r.get("email") or r.get("phone"))]
    if not valid:
        return jsonify({"success": False, "error": "The selected results have no name or contact details."}), 400
    counts = {"added": 0, "updated": 0, "duplicate": 0, "skipped_invalid": len(rows) - len(valid)}
    with job_save_lock:
        registry = MasterLeadRegistry(MASTER_PATH)
        for r in valid:
            outcome, _ = registry.add_lead(ecommerce_sources.result_to_raw_lead(r), default_source="Ecommerce")
            counts[outcome] = counts.get(outcome, 0) + 1
        if not registry.save_master_safely():
            return jsonify({"success": False, "error": "Could not write the leads file."}), 500
    _cached_leads_data.clear()
    return jsonify({"success": True, **counts})


# ==============================================================================
# Scraping / Mining -> Real Estate (module: realestate_sources.py)
# ==============================================================================
import realestate_sources


@app.route("/api/realestate", methods=["GET"])
def get_realestate_sources():
    return jsonify({"success": True, "sources": realestate_sources.list_sources(),
                    "engines": search_engine.list_engines(),
                    "states": [job_portals.ALL_INDIA] + sorted(job_portals.INDIAN_STATES.keys()),
                    "maxKeywords": realestate_sources.MAX_KEYWORDS, "deepBatch": deep_search.MAX_ITEMS_PER_CALL})


@app.route("/api/realestate/search", methods=["POST"])
def search_realestate():
    data = request.get_json(silent=True) or {}
    params = {k: data.get(k) for k in ("keywords", "audience", "state", "city", "sources", "looking_for", "engine")}
    params["engine_used"] = search_engine.resolve_engine(str(data.get("engine") or "auto"))
    try:
        result = search_cache.cached_search("realestate", params, lambda: realestate_sources.search(params),
                                            status_key="sources", refresh=bool(data.get("refresh")))
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    for r in result.get("results", []):
        r["in_leads"], r["match"] = False, ""
    search_engine.mark_existing(result.get("results", []), MASTER_PATH)
    return jsonify({"success": True, **result})


@app.route("/api/realestate/save", methods=["POST"])
def save_realestate_results():
    global _cached_leads_data
    data = request.get_json(silent=True) or {}
    rows = data.get("results")
    if not isinstance(rows, list) or not rows:
        return jsonify({"success": False, "error": "Select at least one result to save."}), 400
    if len(rows) > MAX_JOBS_PER_SAVE:
        return jsonify({"success": False, "error": f"Save at most {MAX_JOBS_PER_SAVE} results at a time."}), 400
    valid = [r for r in rows if isinstance(r, dict) and r.get("company")
             and (r.get("url") or r.get("website") or r.get("email") or r.get("phone"))]
    if not valid:
        return jsonify({"success": False, "error": "The selected results have no name or contact details."}), 400
    counts = {"added": 0, "updated": 0, "duplicate": 0, "skipped_invalid": len(rows) - len(valid)}
    with job_save_lock:
        registry = MasterLeadRegistry(MASTER_PATH)
        for r in valid:
            outcome, _ = registry.add_lead(realestate_sources.result_to_raw_lead(r), default_source="Real Estate")
            counts[outcome] = counts.get(outcome, 0) + 1
        if not registry.save_master_safely():
            return jsonify({"success": False, "error": "Could not write the leads file."}), 500
    _cached_leads_data.clear()
    return jsonify({"success": True, **counts})


# ==============================================================================
# Scraping / Mining -> SocialMedia (module: social_sources.py)
# ==============================================================================
import social_sources


@app.route("/api/social", methods=["GET"])
def get_social_sources_catalog():
    return jsonify({"success": True, "sources": social_sources.list_sources(),
                    "engines": search_engine.list_engines(),
                    "states": [job_portals.ALL_INDIA] + sorted(job_portals.INDIAN_STATES.keys()),
                    "maxKeywords": social_sources.MAX_KEYWORDS, "deepBatch": deep_search.MAX_ITEMS_PER_CALL})


@app.route("/api/social/search", methods=["POST"])
def search_social_sources():
    data = request.get_json(silent=True) or {}
    params = {k: data.get(k) for k in ('keywords', 'audience', 'state', 'city', 'sources', 'engine')}
    params["engine_used"] = search_engine.resolve_engine(str(data.get("engine") or "auto"))
    try:
        result = search_cache.cached_search("social", params, lambda: social_sources.search(params),
                                            status_key="sources", refresh=bool(data.get("refresh")))
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    for r in result.get("results", []):
        r["in_leads"], r["match"] = False, ""
    search_engine.mark_existing(result.get("results", []), MASTER_PATH)
    return jsonify({"success": True, **result})


@app.route("/api/social/save", methods=["POST"])
def save_social_sources_results():
    global _cached_leads_data
    data = request.get_json(silent=True) or {}
    rows = data.get("results")
    if not isinstance(rows, list) or not rows:
        return jsonify({"success": False, "error": "Select at least one result to save."}), 400
    if len(rows) > MAX_JOBS_PER_SAVE:
        return jsonify({"success": False, "error": f"Save at most {MAX_JOBS_PER_SAVE} results at a time."}), 400
    valid = [r for r in rows if isinstance(r, dict) and (r.get("company") or r.get("handle"))
             and (r.get("url") or r.get("profile_url") or r.get("website") or r.get("email") or r.get("phone"))]
    if not valid:
        return jsonify({"success": False, "error": "The selected results have no name or link."}), 400
    counts = {"added": 0, "updated": 0, "duplicate": 0, "skipped_invalid": len(rows) - len(valid)}
    with job_save_lock:
        registry = MasterLeadRegistry(MASTER_PATH)
        for r in valid:
            outcome, _ = registry.add_lead(social_sources.result_to_raw_lead(r), default_source="Social Media")
            counts[outcome] = counts.get(outcome, 0) + 1
        if not registry.save_master_safely():
            return jsonify({"success": False, "error": "Could not write the leads file."}), 500
    _cached_leads_data.clear()
    return jsonify({"success": True, **counts})


# ==============================================================================
# Scraping / Mining -> AdLibrary (module: adlibrary_sources.py)
# ==============================================================================
import adlibrary_sources


@app.route("/api/adlibrary", methods=["GET"])
def get_adlibrary_sources_catalog():
    return jsonify({"success": True, "sources": adlibrary_sources.list_sources(),
                    "engines": search_engine.list_engines(),
                    "states": [job_portals.ALL_INDIA] + sorted(job_portals.INDIAN_STATES.keys()),
                    "maxKeywords": adlibrary_sources.MAX_KEYWORDS, "deepBatch": deep_search.MAX_ITEMS_PER_CALL})


@app.route("/api/adlibrary/search", methods=["POST"])
def search_adlibrary_sources():
    data = request.get_json(silent=True) or {}
    params = {k: data.get(k) for k in ('keywords', 'audience', 'state', 'city', 'sources', 'engine')}
    params["engine_used"] = search_engine.resolve_engine(str(data.get("engine") or "auto"))
    try:
        result = search_cache.cached_search("adlibrary", params, lambda: adlibrary_sources.search(params),
                                            status_key="sources", refresh=bool(data.get("refresh")))
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    for r in result.get("results", []):
        r["in_leads"], r["match"] = False, ""
    search_engine.mark_existing(result.get("results", []), MASTER_PATH)
    return jsonify({"success": True, **result})


@app.route("/api/adlibrary/save", methods=["POST"])
def save_adlibrary_sources_results():
    global _cached_leads_data
    data = request.get_json(silent=True) or {}
    rows = data.get("results")
    if not isinstance(rows, list) or not rows:
        return jsonify({"success": False, "error": "Select at least one result to save."}), 400
    if len(rows) > MAX_JOBS_PER_SAVE:
        return jsonify({"success": False, "error": f"Save at most {MAX_JOBS_PER_SAVE} results at a time."}), 400
    valid = [r for r in rows if isinstance(r, dict) and (r.get("company") or r.get("handle"))
             and (r.get("url") or r.get("profile_url") or r.get("website") or r.get("email") or r.get("phone"))]
    if not valid:
        return jsonify({"success": False, "error": "The selected results have no name or link."}), 400
    counts = {"added": 0, "updated": 0, "duplicate": 0, "skipped_invalid": len(rows) - len(valid)}
    with job_save_lock:
        registry = MasterLeadRegistry(MASTER_PATH)
        for r in valid:
            outcome, _ = registry.add_lead(adlibrary_sources.result_to_raw_lead(r), default_source="Ad Library")
            counts[outcome] = counts.get(outcome, 0) + 1
        if not registry.save_master_safely():
            return jsonify({"success": False, "error": "Could not write the leads file."}), 500
    _cached_leads_data.clear()
    return jsonify({"success": True, **counts})


# ==============================================================================
# Scraping / Mining -> WhatsAppGroups (module: whatsapp_sources.py)
# ==============================================================================
import whatsapp_sources


@app.route("/api/whatsapp", methods=["GET"])
def get_whatsapp_sources_catalog():
    return jsonify({"success": True, "sources": whatsapp_sources.list_sources(),
                    "engines": search_engine.list_engines(),
                    "states": [job_portals.ALL_INDIA] + sorted(job_portals.INDIAN_STATES.keys()),
                    "maxKeywords": whatsapp_sources.MAX_KEYWORDS, "deepBatch": deep_search.MAX_ITEMS_PER_CALL})


@app.route("/api/whatsapp/search", methods=["POST"])
def search_whatsapp_sources():
    data = request.get_json(silent=True) or {}
    params = {k: data.get(k) for k in ('keywords', 'audience', 'state', 'city', 'sources', 'engine')}
    params["engine_used"] = search_engine.resolve_engine(str(data.get("engine") or "auto"))
    try:
        result = search_cache.cached_search("whatsapp", params, lambda: whatsapp_sources.search(params),
                                            status_key="sources", refresh=bool(data.get("refresh")))
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    for r in result.get("results", []):
        r["in_leads"], r["match"] = False, ""
    search_engine.mark_existing(result.get("results", []), MASTER_PATH)
    return jsonify({"success": True, **result})


@app.route("/api/whatsapp/save", methods=["POST"])
def save_whatsapp_sources_results():
    global _cached_leads_data
    data = request.get_json(silent=True) or {}
    rows = data.get("results")
    if not isinstance(rows, list) or not rows:
        return jsonify({"success": False, "error": "Select at least one result to save."}), 400
    if len(rows) > MAX_JOBS_PER_SAVE:
        return jsonify({"success": False, "error": f"Save at most {MAX_JOBS_PER_SAVE} results at a time."}), 400
    valid = [r for r in rows if isinstance(r, dict) and (r.get("company") or r.get("handle"))
             and (r.get("url") or r.get("profile_url") or r.get("website") or r.get("email") or r.get("phone"))]
    if not valid:
        return jsonify({"success": False, "error": "The selected results have no name or link."}), 400
    counts = {"added": 0, "updated": 0, "duplicate": 0, "skipped_invalid": len(rows) - len(valid)}
    with job_save_lock:
        registry = MasterLeadRegistry(MASTER_PATH)
        for r in valid:
            outcome, _ = registry.add_lead(whatsapp_sources.result_to_raw_lead(r), default_source="WhatsApp Groups")
            counts[outcome] = counts.get(outcome, 0) + 1
        if not registry.save_master_safely():
            return jsonify({"success": False, "error": "Could not write the leads file."}), 500
    _cached_leads_data.clear()
    return jsonify({"success": True, **counts})


# ==============================================================================
# Data Extraction -> Indian Directories (module: indian_directories.py)
# ==============================================================================
import indian_directories


@app.route("/api/indian-directories", methods=["GET"])
def get_indian_directories_catalog():
    return jsonify({"success": True, "sources": indian_directories.list_sources(),
                    "states": [job_portals.ALL_INDIA] + sorted(job_portals.INDIAN_STATES.keys()),
                    "maxKeywords": indian_directories.MAX_KEYWORDS, "deepBatch": deep_search.MAX_ITEMS_PER_CALL})


@app.route("/api/indian-directories/search", methods=["POST"])
def search_indian_directories():
    data = request.get_json(silent=True) or {}
    params = {k: data.get(k) for k in ('keywords', 'audience', 'state', 'city', 'sources')}
    try:
        result = search_cache.cached_search("indiandirectories", params, lambda: indian_directories.search(params),
                                            status_key="sources", refresh=bool(data.get("refresh")))
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    for r in result.get("results", []):
        r["in_leads"], r["match"] = False, ""
    search_engine.mark_existing(result.get("results", []), MASTER_PATH)
    return jsonify({"success": True, **result})


@app.route("/api/indian-directories/save", methods=["POST"])
def save_indian_directories_results():
    global _cached_leads_data
    data = request.get_json(silent=True) or {}
    rows = data.get("results")
    if not isinstance(rows, list) or not rows:
        return jsonify({"success": False, "error": "Select at least one result to save."}), 400
    if len(rows) > MAX_JOBS_PER_SAVE:
        return jsonify({"success": False, "error": f"Save at most {MAX_JOBS_PER_SAVE} results at a time."}), 400
    valid = [r for r in rows if isinstance(r, dict) and (r.get("company") or r.get("handle"))
             and (r.get("url") or r.get("profile_url") or r.get("website") or r.get("email") or r.get("phone"))]
    if not valid:
        return jsonify({"success": False, "error": "The selected results have no name or link."}), 400
    counts = {"added": 0, "updated": 0, "duplicate": 0, "skipped_invalid": len(rows) - len(valid)}
    with job_save_lock:
        registry = MasterLeadRegistry(MASTER_PATH)
        for r in valid:
            outcome, _ = registry.add_lead(indian_directories.result_to_raw_lead(r), default_source="Indian Directories")
            counts[outcome] = counts.get(outcome, 0) + 1
        if not registry.save_master_safely():
            return jsonify({"success": False, "error": "Could not write the leads file."}), 500
    _cached_leads_data.clear()
    return jsonify({"success": True, **counts})


# ==============================================================================
# Data Extraction -> Corporate Registries (module: corporate_registries.py)
# ==============================================================================
import corporate_registries


@app.route("/api/corporate-registries", methods=["GET"])
def get_corporate_registries_catalog():
    return jsonify({"success": True, **corporate_registries.catalog(),
                    "states": [job_portals.ALL_INDIA] + sorted(job_portals.INDIAN_STATES.keys()),
                    "deepBatch": deep_search.MAX_ITEMS_PER_CALL})


@app.route("/api/corporate-registries/search", methods=["POST"])
def search_corporate_registries():
    data = request.get_json(silent=True) or {}
    keys = ("mode", "keywords", "audience", "state", "city", "company_type", "status", "age", "industry", "pages",
            "max_sellers", "gstins")
    params = {k: data.get(k) for k in keys if k in data}
    try:
        corporate_registries.validate_request(params)          # fail fast with a clear message (400)
        if params.get("mode") == "gst_check":                  # offline - nothing to cache
            result = {**corporate_registries.search(params), "cache": {"hit": False}}
        else:
            result = search_cache.cached_search("corporateregistries", params, lambda: corporate_registries.search(params),
                                                status_key="sources", refresh=bool(data.get("refresh")))
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    for r in result.get("results", []):
        r["in_leads"], r["match"] = False, ""
    search_engine.mark_existing([r for r in result.get("results", []) if r.get("url")], MASTER_PATH)
    return jsonify({"success": True, **result})


@app.route("/api/corporate-registries/details", methods=["POST"])
def corporate_registries_details():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify({"success": True, **corporate_registries.details(data.get("items"))})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/corporate-registries/save", methods=["POST"])
def save_corporate_registries_results():
    global _cached_leads_data
    data = request.get_json(silent=True) or {}
    rows = data.get("results")
    if not isinstance(rows, list) or not rows:
        return jsonify({"success": False, "error": "Select at least one result to save."}), 400
    if len(rows) > MAX_JOBS_PER_SAVE:
        return jsonify({"success": False, "error": f"Save at most {MAX_JOBS_PER_SAVE} results at a time."}), 400
    valid = [r for r in rows if isinstance(r, dict) and r.get("company") and r.get("url")]
    if not valid:
        return jsonify({"success": False, "error": "The selected results have no company name or link."}), 400
    counts = {"added": 0, "updated": 0, "duplicate": 0, "skipped_invalid": len(rows) - len(valid)}
    with job_save_lock:
        registry = MasterLeadRegistry(MASTER_PATH)
        for r in valid:
            outcome, _ = registry.add_lead(corporate_registries.result_to_raw_lead(r), default_source="Corporate Registries")
            counts[outcome] = counts.get(outcome, 0) + 1
        if not registry.save_master_safely():
            return jsonify({"success": False, "error": "Could not write the leads file."}), 500
    _cached_leads_data.clear()
    return jsonify({"success": True, **counts})

if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", "5000"))
    print("\n" + "=" * 60)
    print("SANGEETA INFOTECH - ALL-IN-ONE LEAD & OUTREACH HUB")
    print(f">> URL: http://127.0.0.1:{port}  (bound to {BIND_HOST})")
    print("=" * 60 + "\n")
    app.run(host=BIND_HOST, port=port, debug=False, threaded=True)
