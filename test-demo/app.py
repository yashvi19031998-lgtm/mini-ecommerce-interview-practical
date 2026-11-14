import os
import sys
import csv
import time
import json
import uuid
import threading
import subprocess
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.exceptions import HTTPException
from settings_manager import load_settings, save_settings, format_signature, auto_send_state
from email_service import send_smtp_email
import sync_to_supabase
import datastore

from api_auth import init_auth
import followup_store

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Bind to localhost by default so the API isn't reachable from the LAN.
# Set FLASK_HOST=0.0.0.0 only when deploying behind auth + HTTPS.
BIND_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
init_auth(app, BIND_HOST)


# ------------------------------------------------------------------------------
# API input / error safety net: every /api/* answer is JSON, and bad input is a
# clear 400 instead of a crash page. (Registered after init_auth, so it runs only
# for signed-in requests.)
# ------------------------------------------------------------------------------
@app.before_request
def _require_json_object():
    """A JSON body sent to /api/* must be an object ({...}); lists, text and broken JSON are refused."""
    if not request.path.startswith("/api/") or request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return None
    if request.files or not request.get_data(cache=True):
        return None  # file upload, or no body at all (routes that need no input)
    if request.mimetype in ("multipart/form-data", "application/x-www-form-urlencoded"):
        return None
    data = request.get_json(silent=True, force=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Send the request as a JSON object."}), 400
    return None


@app.errorhandler(HTTPException)
def _http_error(err):
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "error": err.description or err.name}), err.code
    return err


@app.errorhandler(Exception)
def _unexpected_error(err):
    if isinstance(err, HTTPException):
        return _http_error(err)
    app.logger.exception("Unhandled error on %s %s", request.method, request.path)
    if request.path.startswith("/api/"):
        # Wrong value types in the request (text where a list was expected, ...) surface as these
        if isinstance(err, (TypeError, AttributeError, KeyError)) and request.method != "GET":
            return jsonify({"success": False, "error": "The request has a value of the wrong type."}), 400
        return jsonify({"success": False, "error": "Something went wrong on the server. Please try again."}), 500
    return "Internal Server Error", 500


def _json_body():
    """The request's JSON object, or {} when there is none."""
    data = request.get_json(silent=True, force=True)
    return data if isinstance(data, dict) else {}


LEAD_STATUSES = {"NEW", "CONTACTED", "EMAIL_SENT", "REPLIED", "MEETING", "WON", "LOST", "DISQUALIFIED"}


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
# One lock for every writer of the leads file (status changes, saves, cleanup, enrichment): the file is
# read, changed and rewritten whole, so two writers at once would silently drop one of the changes.
leads_write_lock = threading.RLock()
MAX_BULK_EMAILS = 200

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
    with leads_write_lock:
        return _update_lead_record_locked(lead_id, updates)


def _update_lead_record_locked(lead_id, updates):
    global _cached_leads_data
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
    data = _json_body()
    new_status = str(data.get("status") or "").strip().upper()
    if not new_status:
        return jsonify({"success": False, "error": "status is required"}), 400
    if new_status not in LEAD_STATUSES:
        return jsonify({"success": False, "error": f"Unknown status. Use one of: {', '.join(sorted(LEAD_STATUSES))}."}), 400
    lead = _lead_info(lead_id)
    if not lead:
        return jsonify({"success": False, "error": "Lead not found"}), 404
    old_status = str(lead.get("status") or "NEW").upper()
    with leads_write_lock:
        success = update_lead_record(lead_id, {"Status": new_status})
    if not success:
        return jsonify({"success": False, "error": "Could not write the leads file."}), 500
    if new_status != old_status:
        followup_store.safe_log(lead_id, "status_change", f"Status: {old_status} → {new_status}",
                                source="dashboard", lead_name=lead.get("name", ""),
                                lead_email=lead.get("email", ""))
    return jsonify({"success": True})

@app.route("/api/leads/send-email", methods=["POST"])
def send_single_lead_email():
    data = _json_body()
    lead_id = data.get("id")
    to_email = data.get("to")
    subject = data.get("subject")
    message = data.get("message")

    if not to_email or not subject or not message:
        return jsonify({"success": False, "error": "to, subject, and message required"}), 400
    if not all(isinstance(v, str) for v in (to_email, subject, message)):
        return jsonify({"success": False, "error": "to, subject, and message must be text"}), 400

    # User manually clicked Send in UI: allow manual test/send with bypass_duplicate_check=True.
    # The do-not-contact list is never bypassed: the lead's company name goes to the shield too.
    result = send_smtp_email(to_email, subject, message, bypass_duplicate_check=True, verify="lenient",
                             company_name=(_lead_info(lead_id) or {}).get("name", ""))
    if result.get("excluded"):
        return jsonify({"success": False, "error": result.get("error"), "excluded": True}), 403
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
    """Starts a bulk e-mail job in the background and returns at once with a job id.

    Each mailbox is checked before sending, so a batch takes minutes; running it inside the request made
    the browser give up after 2 minutes ("bulk e-mail does not work") while mails were still going out.
    Poll GET /api/leads/bulk-email/<job_id> for progress. Send "wait": true to run it inline (scripts/tests).
    """
    data = _json_body()
    lead_ids = data.get("lead_ids", [])
    subject_tpl = data.get("subject", "")
    message_tpl = data.get("message", "")
    try:
        delay_ms = max(0, min(60000, int(data.get("delay_ms", 1500))))
    except (TypeError, ValueError):
        delay_ms = 1500

    if not lead_ids or not subject_tpl or not message_tpl:
        return jsonify({"success": False, "error": "lead_ids, subject, and message are required"}), 400
    if not isinstance(lead_ids, list) or not isinstance(subject_tpl, str) or not isinstance(message_tpl, str):
        return jsonify({"success": False, "error": "lead_ids must be a list; subject and message must be text"}), 400
    if len(lead_ids) > MAX_BULK_EMAILS:
        return jsonify({"success": False, "error": f"Send to at most {MAX_BULK_EMAILS} leads at a time."}), 400

    with _bulk_lock:
        running = [j for j in _bulk_jobs.values() if not j["done"]]
        if running:
            return jsonify({"success": False, "error": "A bulk e-mail is already being sent. Wait for it to finish.",
                            "job_id": running[0]["job_id"]}), 409
        job = {"job_id": uuid.uuid4().hex[:12], "total": len(lead_ids), "processed": 0, "sent": 0, "failed": 0,
               "not_verified": 0, "skipped": 0, "done": False, "stopped_reason": "", "results": [],
               "started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "finished_at": ""}
        _bulk_jobs[job["job_id"]] = job
        for old in list(_bulk_jobs)[:-10]:          # keep the last 10 jobs only
            if _bulk_jobs[old]["done"]:
                _bulk_jobs.pop(old, None)

    args = (job, [str(x) for x in lead_ids], subject_tpl, message_tpl, delay_ms)
    if data.get("wait"):
        _run_bulk_job(*args)
        return jsonify({"success": True, **_bulk_snapshot(job)})
    threading.Thread(target=_run_bulk_job, args=args, daemon=True).start()
    return jsonify({"success": True, "job_id": job["job_id"], "total": job["total"]})


@app.route("/api/leads/bulk-email/<job_id>", methods=["GET"])
def bulk_email_status(job_id):
    job = _bulk_jobs.get(str(job_id))
    if not job:
        return jsonify({"success": False, "error": "Unknown bulk e-mail job."}), 404
    return jsonify({"success": True, **_bulk_snapshot(job)})


_bulk_jobs = {}
_bulk_lock = threading.Lock()
BULK_MAX_FAILURES_IN_ROW = 3


def _bulk_snapshot(job):
    with _bulk_lock:
        snap = dict(job)
        snap["results"] = list(job["results"])
    return snap


def _bulk_note(job, lid, email, ok, reason, error=""):
    with _bulk_lock:
        job["results"].append({"id": lid, "email": email, "success": ok, "reason": reason, "error": error})
        job["processed"] += 1
        if ok:
            job["sent"] += 1
        elif reason == "not_verified":
            job["not_verified"] += 1
        elif reason in ("no_email", "already_sent", "excluded", "daily_limit", "stopped"):
            job["skipped"] += 1
        else:
            job["failed"] += 1


def _run_bulk_job(job, lead_ids, subject_tpl, message_tpl, delay_ms):
    try:
        all_leads = {str(l["id"]): l for l in read_leads()}
        settings = load_settings()
        sig = format_signature(settings)
        try:
            import run_all_scrapers as _r
            daily_cap, sent_today = _r.MAX_EMAILS_PER_DAY, _r.emails_sent_today()
        except Exception:
            daily_cap, sent_today = 50, 0
        failures_in_row = 0
        for idx, lid in enumerate(lead_ids):
            lead = all_leads.get(lid)
            if not lead:
                _bulk_note(job, lid, "", False, "no_email", "Lead not found")
                continue
            to_email = str(lead.get("Email", "")).split(",")[0].strip()
            if not to_email or "@" not in to_email or to_email == "N/A":
                _bulk_note(job, lid, to_email, False, "no_email", "No valid e-mail")
                continue
            if job["stopped_reason"]:
                _bulk_note(job, lid, to_email, False, "stopped", job["stopped_reason"])
                continue
            if sent_today + job["sent"] >= daily_cap:
                job["stopped_reason"] = f"Daily limit of {daily_cap} e-mails reached - the rest can go tomorrow."
                _bulk_note(job, lid, to_email, False, "daily_limit", job["stopped_reason"])
                continue

            comp = str(lead.get("Company Name") or "")
            # A job-post title is never used as a name in the e-mail text (see followup_sequence.outreach_names)
            name, msg_company = followup_sequence.outreach_names(comp)
            loc = str(lead.get("Address") or "").strip() or "your region"
            sub = subject_tpl.replace("{company}", msg_company).replace("{name}", name).replace("{location}", loc)
            body = message_tpl.replace("{company}", msg_company).replace("{name}", name).replace("{location}", loc)
            if sig and sig.strip()[:20] not in body:
                body = f"{body}\n\n---\n{sig.strip()}"

            res = send_smtp_email(to_email, sub, body, company_name=comp)
            if res.get("success"):
                failures_in_row = 0
                update_lead_record(lid, {"Email Status": "SENT", "Email Sent At": time.strftime("%Y-%m-%d %H:%M:%S"),
                                         "Status": "EMAIL_SENT"})
                followup_store.safe_log(lid, "email_sent", f"Email sent: {sub}", details=body,
                                        source="bulk email", lead_name=comp, lead_email=to_email)
                _bulk_note(job, lid, to_email, True, "sent")
                if idx < len(lead_ids) - 1 and delay_ms > 0:
                    time.sleep(delay_ms / 1000.0)
            elif res.get("verify"):
                if res.get("invalid"):
                    update_lead_record(lid, {"Email Status": "INVALID"})   # would bounce: never try again
                _bulk_note(job, lid, to_email, False, "not_verified", res.get("error", ""))
                if "port 25" in str(res.get("error", "")):
                    job["stopped_reason"] = "This computer cannot check mailboxes (port 25 blocked), so nothing is sent."
            elif res.get("already_sent"):
                _bulk_note(job, lid, to_email, False, "already_sent", res.get("error", ""))
            elif res.get("excluded"):
                _bulk_note(job, lid, to_email, False, "excluded", res.get("error", ""))
            else:
                failures_in_row += 1
                _bulk_note(job, lid, to_email, False, "error", res.get("error", "SMTP send failed"))
                if failures_in_row >= BULK_MAX_FAILURES_IN_ROW:
                    job["stopped_reason"] = (f"Stopped after {failures_in_row} failed sends in a row - check the Gmail "
                                             f"login (Settings -> Send Test Verification Email).")
    except Exception as err:  # never leave a job "running" forever
        job["stopped_reason"] = f"Bulk e-mail stopped: {err}"
    finally:
        with _bulk_lock:
            job["done"] = True
            job["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

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

    data = _json_body()
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
            synced = sync_to_supabase.sync(csv_filepath=target_csv, lock=leads_write_lock)
            with scraper_lock:
                scraper_logs.append(f"[{time.strftime('%H:%M:%S')}] " + ("Saved to the database." if synced else "Database sync skipped (see Settings)."))
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
    """Sync all app data with the database (one table, see datastore.py) right now."""
    if not datastore.configured():
        return jsonify({"success": False, "error": "Database not set up: add SUPABASE_URL and SUPABASE_KEY in .env."}), 400
    report = datastore.sync(lock=leads_write_lock)
    if not report.get("ok"):
        return jsonify({"success": False, "error": f"Database sync failed: {report.get('error')}"}), 502
    return jsonify({"success": True, "message": f"Database up to date ({sync_to_supabase.summary(report)}).",
                    "report": report})


@app.route("/api/datastore/status", methods=["GET"])
def datastore_status():
    return jsonify({"success": True, "configured": datastore.configured(), "last_sync": datastore.last_status()})

@app.route("/api/settings", methods=["GET", "POST"])
def handle_settings():
    if request.method == "POST":
        data = _json_body()
        if not data:
            return jsonify({"success": False, "error": "No settings were sent."}), 400
        saved = save_settings(data)  # merges into the saved file; never stores passwords
        return jsonify({"success": True, "settings": saved})
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
    result = send_smtp_email(to_email, subject, body, verify=None)  # our own inbox
    return jsonify(result)

@app.route("/api/export-csv")
def export_csv():
    if os.path.exists(LEADS_CSV):
        return send_file(LEADS_CSV, as_attachment=True, download_name="sangeeta_infotech_leads.csv")
    return "No leads CSV found", 404

# ==============================================================================
# 1-HOUR AUTO SCRAPER & SCHEDULER STATUS
# ==============================================================================
@app.route("/api/scheduler/status", methods=["GET"])
def get_scheduler_status():
    settings = load_settings()
    is_running = os.path.exists(os.path.join(BASE_DIR, ".scraper_runner.lock"))

    # logs/scraper_runs.csv has one row per scraper; a "run" is every row sharing a run_id.
    rows = []
    runs_file = os.path.join(BASE_DIR, "logs", "scraper_runs.csv")
    if os.path.exists(runs_file):
        try:
            with open(runs_file, mode="r", encoding="utf-8-sig", newline="") as f:
                rows = [r for r in csv.reader(f) if len(r) >= 9 and r[0] != "run_id"]
        except (OSError, csv.Error) as e:
            print(f"[WARN] Error reading scraper runs log: {e}")

    def _num(v):
        try:
            return int(v or 0)
        except ValueError:
            return 0

    run_ids = {r[0] for r in rows}
    recent = [{
        "run_id": r[0], "start_time": r[1], "end_time": r[2], "scraper_name": r[3], "status": r[4],
        "records": r[5], "added": r[6], "updated": r[7], "duplicates": r[8],
        "error_summary": r[9] if len(r) > 9 else "",
    } for r in reversed(rows[-50:])]
    auto_send, auto_send_reason = auto_send_state(settings)

    return jsonify({
        "success": True,
        "is_running": is_running,
        "schedule": "Hourly (Automated 1-Hr Workflow)",
        "cron": "23 * * * *",
        "last_run": rows[-1][1] if rows else "",
        "total_runs": len(run_ids),
        "total_scraper_rows": len(rows),
        "total_added": sum(_num(r[6]) for r in rows),
        "auto_send_email": auto_send,
        "auto_send_reason": auto_send_reason,
        "smtp_configured": bool(os.getenv("SMTP_USER") and os.getenv("SMTP_PASS")),
        "max_pending_emails": settings.get("maxPendingEmailsPerRun", 5),
        "max_emails_per_day": int(os.getenv("MAX_EMAILS_PER_DAY")) if str(os.getenv("MAX_EMAILS_PER_DAY") or "").isdigit() and int(os.getenv("MAX_EMAILS_PER_DAY")) > 0 else 50,
        "default_keywords": settings.get("defaultKeywords", []),
        "default_city": settings.get("defaultCity", "Ahmedabad"),
        "default_state": settings.get("defaultState", "Gujarat"),
        "excluded_companies": settings.get("excludedCompanies", ["8dots"]),
        "runs": recent
    })


_scheduler_thread = None


@app.route("/api/scheduler/trigger", methods=["POST"])
def trigger_scheduler_run():
    global _scheduler_thread
    lock_file = os.path.join(BASE_DIR, ".scraper_runner.lock")
    # The lock file appears a moment after the script starts: also refuse while our own thread is
    # alive, or two quick clicks would start two runs (and e-mail the same leads twice).
    if os.path.exists(lock_file) or (_scheduler_thread is not None and _scheduler_thread.is_alive()):
        return jsonify({"success": False, "error": "A 1-hour scraper job is already executing right now."}), 409

    def _run_bg():
        try:
            py_bin = sys.executable or "python"
            subprocess.run([py_bin, os.path.join(BASE_DIR, "run_all_scrapers.py")], cwd=BASE_DIR, check=False)
            _cached_leads_data.clear()
        except Exception as err:
            print(f"[ERROR] Failed to run automated scraper in background: {err}")
            
    _scheduler_thread = threading.Thread(target=_run_bg, daemon=True)
    _scheduler_thread.start()
    return jsonify({"success": True, "message": "1-Hour Lead Scraper & Auto-Outreach triggered successfully."})

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
            chat_text = _json_body().get("text", "")
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

        if not isinstance(chat_text, str) or not chat_text.strip():
            return jsonify({"success": False, "error": "No chat content or file uploaded."}), 400

        leads = lead_importer.parse_whatsapp_chat(chat_text)
        enriched = lead_importer.check_duplicates_against_master(leads, master_csv=LEADS_CSV)
        return jsonify({"success": True, "leads": enriched, "count": len(enriched)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/import/raw-text", methods=["POST"])
def import_raw_text():
    try:
        data = _json_body()
        raw_text = data.get("text", "")
        raw_text = raw_text.strip() if isinstance(raw_text, str) else ""
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
        data = _json_body()
        leads = data.get("leads", [])
        send_outreach_email = bool(data.get("send_outreach_email", False))

        if not isinstance(leads, list) or not leads:
            return jsonify({"success": False, "error": "No leads selected to import."}), 400
        leads = [l for l in leads if isinstance(l, dict)]
        if not leads:
            return jsonify({"success": False, "error": "The selected leads are not valid records."}), 400

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
job_save_lock = leads_write_lock


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


SCORE_BANDS = {"high": (7, 10), "medium": (4, 6), "low": (0, 3)}


def _score_of(lead):
    """AI score 0-10 (falls back to the scraper's intent score); None when the lead was never scored."""
    for key in ("ai_score", "intent_score"):
        try:
            return max(0, min(10, int(round(float(str(lead.get(key, "")).strip())))))
        except ValueError:
            continue
    return None


def _band_of(score):
    if score is None:
        return "unscored"
    return next(b for b, (lo, hi) in SCORE_BANDS.items() if lo <= score <= hi)


@app.route("/api/followups/untouched", methods=["GET"])
def followups_untouched():
    """New leads nobody has contacted yet: no e-mail sent, no activity logged, still open.
    ?band=all|high|medium|low|unscored  ?has_email=1 (only leads with an e-mail address)"""
    band = request.args.get("band", "all").lower()
    if band not in ("all", "unscored", *SCORE_BANDS):
        return jsonify({"success": False, "error": "band must be all, high, medium, low or unscored"}), 400
    only_email = request.args.get("has_email") == "1"
    touched = followup_store.touched_lead_ids()
    counts = {"all": 0, "high": 0, "medium": 0, "low": 0, "unscored": 0}
    items = []
    for l in read_leads():
        lid = str(l.get("id"))
        status = str(l.get("Status") or "NEW").upper()
        if lid in touched or status not in ("NEW", "", "NAN") or str(l.get("Email Status", "")).upper() in ("SENT", "INVALID"):
            continue
        email = str(l.get("Email") or "").split(",")[0].strip()
        if email in ("N/A", "nan"):
            email = ""
        if only_email and "@" not in email:
            continue
        score = _score_of(l)
        b = _band_of(score)
        counts["all"] += 1
        counts[b] += 1
        if band != "all" and b != band:
            continue
        items.append({
            "id": lid,
            "name": str(l.get("Company Name") or l.get("full_name") or ""),
            "email": email,
            "phone": str(l.get("Mobile Number") or "").split(",")[0].strip().replace("N/A", ""),
            "source": str(l.get("Source") or ""),
            "score": score, "band": b,
            "summary": str(l.get("ai_summary") or l.get("description") or "")[:200],
            "found_at": str(l.get("first_seen_at") or ""),
        })
    items.sort(key=lambda i: i["found_at"], reverse=True)                                  # newest first...
    items.sort(key=lambda i: i["score"] if i["score"] is not None else -1, reverse=True)  # ...within highest score first
    return jsonify({"success": True, "items": items[:500], "total": len(items), "counts": counts})


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
    company_by_email = {str(i.get("email", "")).strip().lower(): i.get("lead_name", "") for i in due}
    result = followup_sequence.send(
        due, lambda to, sub, body: send_smtp_email(to, sub, body, bypass_duplicate_check=True, verify=None,
                                                   company_name=company_by_email.get(str(to).strip().lower(), "")),
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


# ==============================================================================
# Bulk Contacts (module: bulk_contacts.py) - website contacts, e-mail verifier, phone cleaner, CSV import
# ==============================================================================
import bulk_contacts

BULK_MAX_REQUEST = 6 * 1024 * 1024


def _bulk_json():
    if (request.content_length or 0) > BULK_MAX_REQUEST:
        raise ValueError("The request is larger than 6 MB - split the file")
    return request.get_json(silent=True) or {}


def _bulk(fn):
    try:
        return jsonify({"success": True, **fn(_bulk_json())})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/bulk-contacts", methods=["GET"])
def bulk_contacts_catalog():
    b = bulk_contacts
    return jsonify({"success": True, "maxUrlsPerCall": b.MAX_URLS_PER_CALL, "maxEmails": b.MAX_EMAILS,
                    "maxPhones": b.MAX_PHONES, "maxCsvRows": b.MAX_CSV_ROWS, "maxCsvBytes": b.MAX_CSV_BYTES,
                    "maxSaveRows": b.MAX_SAVE_ROWS, "fields": b.LEAD_FIELDS})


@app.route("/api/bulk-contacts/websites", methods=["POST"])
def bulk_contacts_websites():
    return _bulk(lambda d: bulk_contacts.website_contacts(d.get("urls")))


@app.route("/api/bulk-contacts/emails", methods=["POST"])
def bulk_contacts_emails():
    return _bulk(lambda d: bulk_contacts.verify_emails(d.get("emails"), master_path=MASTER_PATH))


@app.route("/api/bulk-contacts/phones", methods=["POST"])
def bulk_contacts_phones():
    return _bulk(lambda d: bulk_contacts.clean_phones(d.get("text"), master_path=MASTER_PATH))


@app.route("/api/bulk-contacts/import/preview", methods=["POST"])
def bulk_contacts_import_preview():
    return _bulk(lambda d: bulk_contacts.preview_csv(d.get("text")))


@app.route("/api/bulk-contacts/import/check", methods=["POST"])
def bulk_contacts_import_check():
    return _bulk(lambda d: bulk_contacts.check_csv(d.get("text"), d.get("mapping"), d.get("source"), master_path=MASTER_PATH))


@app.route("/api/bulk-contacts/save", methods=["POST"])
def bulk_contacts_save():
    """kind = 'import' (checked CSV rows) or 'websites' (website-contact results)."""
    global _cached_leads_data
    try:
        data = _bulk_json()
        rows = data.get("rows")
        if data.get("kind") == "websites":
            rows = bulk_contacts.website_rows_to_leads(rows)
        elif data.get("kind") != "import":
            raise ValueError("Unknown kind")
        with job_save_lock:
            counts = bulk_contacts.save_rows(rows, MASTER_PATH)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except IOError as e:
        return jsonify({"success": False, "error": str(e)}), 500
    _cached_leads_data.clear()
    return jsonify({"success": True, **counts})


# ==============================================================================
# Web Crawler (module: web_crawler.py) - site crawler, link harvester, keyword finder, sitemap explorer
# Results are saved through /api/bulk-contacts/save (kind "websites").
# ==============================================================================
import web_crawler


@app.route("/api/web-crawler", methods=["GET"])
def web_crawler_catalog():
    w = web_crawler
    return jsonify({"success": True, "pageChoices": list(w.PAGE_CHOICES), "depthChoices": list(w.DEPTH_CHOICES),
                    "maxSeeds": w.MAX_SEEDS, "maxKeywords": w.MAX_KEYWORDS, "timeBudget": w.TIME_BUDGET,
                    "maxSitemapUrls": w.MAX_SITEMAP_URLS, "bulkBatch": bulk_contacts.MAX_URLS_PER_CALL})


@app.route("/api/web-crawler/<tool>", methods=["POST"])
def web_crawler_run(tool):
    fn = {"site": web_crawler.site_crawl, "links": web_crawler.harvest_links,
          "keywords": web_crawler.find_keywords, "sitemap": web_crawler.sitemap}.get(tool)
    if not fn:
        return jsonify({"success": False, "error": "Unknown tool"}), 404
    return _bulk(fn)


# ==============================================================================
# File Uploads (module: file_uploads.py) - contacts from Excel, vCard, Word, e-mail, PDF, text and card photos.
# Excel sheets continue in the Contact Import flow; results are saved through /api/bulk-contacts/save (kind "import").
# ==============================================================================
import file_uploads


@app.route("/api/file-uploads", methods=["GET"])
def file_uploads_catalog():
    return jsonify({"success": True, "types": file_uploads.TYPES, "maxFileBytes": file_uploads.MAX_FILE_BYTES,
                    "ocr": {k: v for k, v in file_uploads.ocr_status().items() if k != "exe"}})


@app.route("/api/file-uploads/parse", methods=["POST"])
def file_uploads_parse():
    if (request.content_length or 0) > 15 * 1024 * 1024:
        return jsonify({"success": False, "error": "The file is larger than 10 MB"}), 400
    data = request.get_json(silent=True) or {}
    try:
        return jsonify({"success": True, **file_uploads.parse_upload(data.get("name"), data.get("data"), master_path=MASTER_PATH)})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


# ==============================================================================
# Utilities -> Website Analyzer (module: website_analyzer.py). Save goes through /api/bulk-contacts/save
# (kind "websites"); the problems found are stored in the lead's website_signals column.
# ==============================================================================
import website_analyzer


@app.route("/api/utilities/website-analyzer", methods=["POST"])
def utilities_website_analyzer():
    return _bulk(lambda d: website_analyzer.analyze(d.get("urls")))


# ==============================================================================
# Domain Tools (module: domain_tools.py) - age & expiry (RDAP), email & DNS, new domains, availability.
# Save goes through /api/bulk-contacts/save (kind "websites").
# ==============================================================================
import domain_tools


@app.route("/api/domain-tools", methods=["GET"])
def domain_tools_catalog():
    d = domain_tools
    return jsonify({"success": True, "maxDomains": d.MAX_DOMAINS, "dayChoices": list(d.DAY_CHOICES),
                    "newTlds": d.NEW_TLDS, "availTlds": d.AVAIL_TLDS, "maxNewKeywords": d.MAX_NEW_KEYWORDS})


@app.route("/api/domain-tools/<tool>", methods=["POST"])
def domain_tools_run(tool):
    fn = {"age": lambda d: domain_tools.age_report(d.get("domains")),
          "dns": lambda d: domain_tools.dns_report(d.get("domains")),
          "new": domain_tools.new_domains, "available": domain_tools.availability}.get(tool)
    if not fn:
        return jsonify({"success": False, "error": "Unknown tool"}), 404
    return _bulk(fn)


# ==============================================================================
# Lead Care -> Data Cleanup (module: lead_cleanup.py). Never deletes: fills empty fields only, backs up the leads
# file first, logs every change, and can undo.
# ==============================================================================
import lead_cleanup


@app.route("/api/lead-care/cleanup", methods=["GET"])
def lead_care_cleanup_scan():
    return jsonify({"success": True, **lead_cleanup.scan(MASTER_PATH)})


@app.route("/api/lead-care/cleanup/apply", methods=["POST"])
def lead_care_cleanup_apply():
    global _cached_leads_data
    data = request.get_json(silent=True) or {}
    try:
        with job_save_lock:
            res = lead_cleanup.apply(MASTER_PATH, data.get("fixes"))
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except IOError as e:
        return jsonify({"success": False, "error": str(e)}), 500
    _cached_leads_data.clear()
    return jsonify({"success": True, **res})


@app.route("/api/lead-care/cleanup/undo", methods=["POST"])
def lead_care_cleanup_undo():
    global _cached_leads_data
    data = request.get_json(silent=True) or {}
    try:
        with job_save_lock:
            res = lead_cleanup.undo(MASTER_PATH, data.get("log_id"))
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except IOError as e:
        return jsonify({"success": False, "error": str(e)}), 500
    _cached_leads_data.clear()
    return jsonify({"success": True, **res})


# ==============================================================================
# Lead Care -> Lead Enrichment (module: lead_enrichment.py). Proposals only until the owner saves; saving fills
# EMPTY fields with backup + change log + undo (shared with Data Cleanup).
# ==============================================================================
import lead_enrichment


@app.route("/api/lead-care/enrichment/candidates", methods=["POST"])
def lead_care_enrichment_candidates():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify({"success": True, **lead_enrichment.candidates(MASTER_PATH, data)})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/lead-care/enrichment/run", methods=["POST"])
def lead_care_enrichment_run():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify({"success": True, **lead_enrichment.enrich(MASTER_PATH, data.get("lead_ids"), data.get("steps"),
                                                                  str(data.get("engine") or "auto"))})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/lead-care/enrichment/save", methods=["POST"])
def lead_care_enrichment_save():
    global _cached_leads_data
    data = request.get_json(silent=True) or {}
    try:
        with job_save_lock:
            res = lead_enrichment.save(MASTER_PATH, data.get("changes"))
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except IOError as e:
        return jsonify({"success": False, "error": str(e)}), 500
    _cached_leads_data.clear()
    return jsonify({"success": True, **res})


# REPORTS (reports_engine.py)
import reports_engine

def _report_context():
    """Helper to load data files using BASE_DIR without writing anything."""
    leads = read_leads()
    runs_path = os.path.join(BASE_DIR, "logs", "scraper_runs.csv")
    sent_path = os.path.join(BASE_DIR, "logs", "sent_emails.csv")
    act_path = os.path.join(BASE_DIR, "logs", "followup_activity.csv")
    runs = reports_engine.load_runs(runs_path)
    sent = reports_engine.load_sent(sent_path)
    acts = reports_engine.load_activities(act_path)
    return leads, runs, sent, acts

def _report_filters():
    return {
        "preset": request.args.get("preset"),
        "date_from": request.args.get("date_from"),
        "date_to": request.args.get("date_to"),
        "source": request.args.get("source"),
        "status": request.args.get("status"),
    }

@app.route("/api/reports/summary", methods=["GET"])
def report_summary_endpoint():
    try:
        leads, runs, sent, acts = _report_context()
        res = reports_engine.summary(leads, runs, acts, sent, _report_filters())
        return jsonify({"success": True, **res})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/reports/scrapers", methods=["GET"])
def report_scrapers_endpoint():
    try:
        _, runs, _, _ = _report_context()
        res = reports_engine.scraper_report(runs, _report_filters())
        return jsonify({"success": True, **res})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/reports/sources", methods=["GET"])
def report_sources_endpoint():
    try:
        leads, _, _, acts = _report_context()
        res = reports_engine.source_report_rows(leads, acts, _report_filters())
        return jsonify({"success": True, **res})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/reports/followups", methods=["GET"])
def report_followups_endpoint():
    try:
        leads, _, sent, acts = _report_context()
        quiet_days_raw = request.args.get("quiet_days", 5)
        try:
            quiet_days = int(quiet_days_raw)
        except (ValueError, TypeError):
            raise ValueError("quiet_days must be an integer between 1 and 60.")
        if quiet_days < 1 or quiet_days > 60:
            raise ValueError("quiet_days must be between 1 and 60.")

        seq_plan = followup_sequence.plan(_lead_index())
        settings = load_settings()
        res = reports_engine.followup_watchlist(leads, acts, sent, seq_plan, settings, quiet_days=quiet_days)
        return jsonify({"success": True, **res})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/reports/pipeline", methods=["GET"])
def report_pipeline_endpoint():
    try:
        leads, _, _, acts = _report_context()
        res = reports_engine.pipeline(leads, acts, _report_filters())
        return jsonify({"success": True, **res})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/reports/outreach", methods=["GET"])
def report_outreach_endpoint():
    try:
        leads, _, sent, acts = _report_context()
        settings = load_settings()
        res = reports_engine.outreach(leads, acts, sent, settings, _report_filters())
        return jsonify({"success": True, **res})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/reports/data-health", methods=["GET"])
def report_data_health_endpoint():
    try:
        leads, _, _, _ = _report_context()
        res = reports_engine.data_health(leads)
        return jsonify({"success": True, **res})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/reports/activity", methods=["GET"])
def report_activity_endpoint():
    try:
        leads, runs, sent, acts = _report_context()
        day = request.args.get("day")
        res = reports_engine.activity_log(runs, acts, sent, leads, day_str=day)
        return jsonify({"success": True, **res})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/reports/options", methods=["GET"])
def report_options_endpoint():
    try:
        leads = read_leads()
        res = reports_engine.get_filter_options(leads)
        return jsonify({"success": True, **res})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


# ==============================================================================
# IN-APP CHAT ASSISTANT (chat_assistant.py) - read-only answers about leads, e-mails, scrapers
# ==============================================================================
import chat_assistant


def _chat_context():
    leads, runs, sent, acts = _report_context()
    return {"leads": leads, "runs": runs, "sent": sent, "acts": acts, "settings": load_settings()}


@app.route("/api/chat", methods=["POST"])
def chat_endpoint():
    data = _json_body()
    try:
        res = chat_assistant.answer(data.get("message"), _chat_context)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    return jsonify({"success": True, **res})


# ==============================================================================
# WEBSITE CHATBOT (website_chatbot.py) - PUBLIC: no login. Lives outside /api/ on purpose
# (the login guard covers /api/ only); protected by an origin allow-list, size limits and rate limits.
# ==============================================================================
import re
import website_chatbot
from flask import Response

WIDGET_DIR = os.path.join(BASE_DIR, "widget")
MAX_PUBLIC_BODY = 8 * 1024


def _widget_origin_ok(origin: str) -> bool:
    if not origin:
        return True  # same-origin request (the demo page served by this backend)
    return origin.rstrip("/") in website_chatbot.allowed_origins() or (
        BIND_HOST in ("127.0.0.1", "localhost", "::1") and re.match(r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$", origin))


def _cors(resp, origin: str):
    if origin and _widget_origin_ok(origin):
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Max-Age"] = "600"
    resp.headers["Vary"] = "Origin"
    return resp


def _save_website_lead(lead: dict) -> str:
    """Adds the visitor as a lead (normal duplicate check) and tells the owner by e-mail. Returns the lead id."""
    global _cached_leads_data
    contact = lead.get("email") or lead.get("phone") or ""
    raw = {
        # Never one shared placeholder name: the duplicate check would merge different visitors into one lead
        "company_name": lead.get("name") or f"Website enquiry - {contact}",
        "full_name": lead.get("name", ""),
        "email": lead.get("email", ""),
        "mobile_number": lead.get("phone", ""),
        # The page goes in the description, not source_url: every visitor of one page shares that URL, and the
        # duplicate check matches leads on source_url.
        "description": f"Website chat enquiry: {lead.get('requirement', '')}"
                       + (f" (page: {lead.get('page')})" if lead.get("page") else ""),
        "source": "Website Chatbot",
        "lead_type": "inbound",
    }
    with leads_write_lock:
        registry = MasterLeadRegistry(MASTER_PATH)
        outcome, saved = registry.add_lead(raw, default_source="Website Chatbot")
        if outcome == "skipped_invalid" or not registry.save_master_safely():
            return ""
    _cached_leads_data.clear()
    lead_id = (saved or {}).get("lead_id", "") if isinstance(saved, dict) else ""
    followup_store.safe_log(lead_id, "note", "Website chat enquiry", details=lead.get("requirement", ""),
                            source="website chatbot", lead_name=raw["company_name"], lead_email=raw["email"])

    def _notify():
        try:
            owner = load_settings().get("email") or os.getenv("SMTP_USER", "")
            if owner:
                body = (f"New enquiry from the website chatbot.\n\nName: {lead.get('name') or '-'}\n"
                        f"E-mail: {lead.get('email') or '-'}\nPhone: {lead.get('phone') or '-'}\n"
                        f"Page: {lead.get('page') or '-'}\nLead ID: {lead_id}\n\nRequirement:\n{lead.get('requirement')}")
                send_smtp_email(owner, f"New website enquiry: {lead.get('name') or lead.get('email') or lead.get('phone')}",
                                body, bypass_duplicate_check=True, verify=None)
        except Exception as err:
            print(f"[website chatbot] owner notification failed: {err}")
    threading.Thread(target=_notify, daemon=True).start()
    return lead_id or "saved"


@app.route("/public/chat", methods=["POST", "OPTIONS"])
def public_chat():
    origin = request.headers.get("Origin", "")
    if request.method == "OPTIONS":
        return _cors(Response(status=204), origin)
    if not _widget_origin_ok(origin):
        return _cors(jsonify({"success": False, "error": "This website is not allowed to use the chat."}), origin), 403
    if (request.content_length or 0) > MAX_PUBLIC_BODY:
        return _cors(jsonify({"success": False, "error": "Message too long."}), origin), 413
    payload = request.get_json(silent=True, force=True)
    ip = request.remote_addr or "unknown"
    try:
        res = website_chatbot.handle(payload, load_settings(), ip, _save_website_lead)
    except PermissionError as e:
        return _cors(jsonify({"success": False, "error": str(e)}), origin), 429
    except ValueError as e:
        return _cors(jsonify({"success": False, "error": str(e)}), origin), 400
    return _cors(jsonify({"success": True, **res}), origin)


@app.route("/widget/chatbot.js", methods=["GET"])
def widget_script():
    with open(os.path.join(WIDGET_DIR, "chatbot.js"), encoding="utf-8") as fh:
        return Response(fh.read(), mimetype="application/javascript")


@app.route("/widget/demo", methods=["GET"])
def widget_demo():
    """A test page for the website chatbot - only when the backend runs on this computer."""
    if BIND_HOST not in ("127.0.0.1", "localhost", "::1"):
        return "Not found", 404
    return ("<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,"
            "initial-scale=1'><title>Website chatbot demo</title></head><body style='font-family:system-ui;padding:24px'>"
            "<h1>Website chatbot demo</h1><p>This page stands in for the company website. Use the chat button "
            "at the bottom right.</p><script src='/widget/chatbot.js' defer></script></body></html>")


if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", "5000"))
    print("\n" + "=" * 60)
    print("SANGEETA INFOTECH - ALL-IN-ONE LEAD & OUTREACH HUB")
    print(f">> URL: http://127.0.0.1:{port}  (bound to {BIND_HOST})")
    print("=" * 60 + "\n")
    # All data lives in the database (one table): load it now, then keep both sides in step every 2 minutes
    if datastore.configured():
        print("[DB] Loading data from the database...")
        first = datastore.sync(lock=leads_write_lock)
        print(f"[DB] {'OK - ' + sync_to_supabase.summary(first) if first.get('ok') else 'NOT synced: ' + str(first.get('error'))}")
        later = threading.Timer(120, lambda: datastore.start_background_sync(lock=leads_write_lock))
        later.daemon = True
        later.start()
    else:
        print("[DB] SUPABASE_URL / SUPABASE_KEY missing - data is kept in local files only.")
    app.run(host=BIND_HOST, port=port, debug=False, threaded=True)
