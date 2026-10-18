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

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

LEADS_CSV = "leads_new.csv"

# Global state for background scraper process
scraper_process = None
scraper_logs = []
scraper_lock = threading.Lock()

def ensure_csv_status_column():
    """Ensure Status and Email Sent columns exist in CSV."""
    if os.path.exists(LEADS_CSV):
        try:
            df = pd.read_csv(LEADS_CSV)
            modified = False
            if "Status" not in df.columns:
                df["Status"] = "NEW"
                modified = True
            if "Email Status" not in df.columns:
                df["Email Status"] = "NOT_SENT"
                modified = True
            if "Email Sent At" not in df.columns:
                df["Email Sent At"] = ""
                modified = True
            if modified:
                df.to_csv(LEADS_CSV, index=False, encoding="utf-8")
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
        for idx, item in enumerate(leads):
            item["id"] = str(item.get("No") or item.get("lead_id") or (idx + 1))
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
            if not item.get("Status"):
                item["Status"] = "NEW"

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

def update_lead_record(lead_id, updates):
    global _cached_leads_data
    updated = False
    if os.path.exists(LEADS_CSV):
        try:
            df = pd.read_csv(LEADS_CSV)
            matched = False
            for idx, row in df.iterrows():
                curr_id = str(row.get("No") or (idx + 1))
                if curr_id == str(lead_id):
                    for k, v in updates.items():
                        if k not in df.columns:
                            df[k] = ""
                        df.at[idx, k] = v
                    matched = True
                    break
            if matched:
                df.to_csv(LEADS_CSV, index=False, encoding="utf-8")
                updated = True
        except Exception as e:
            print(f"Error updating {LEADS_CSV}: {e}")

    if os.path.exists("all_leads_master.csv"):
        try:
            mdf = pd.read_csv("all_leads_master.csv")
            m_matched = False
            for idx, row in mdf.iterrows():
                curr_id = str(row.get("lead_id") or row.get("No") or (idx + 1))
                if curr_id == str(lead_id):
                    if "Email Status" in updates and "email_status" in mdf.columns:
                        mdf.at[idx, "email_status"] = updates["Email Status"]
                    if "Email Sent At" in updates and "email_sent_at" in mdf.columns:
                        mdf.at[idx, "email_sent_at"] = updates["Email Sent At"]
                    m_matched = True
                    break
            if m_matched:
                mdf.to_csv("all_leads_master.csv", index=False, encoding="utf-8")
                updated = True
        except Exception as e:
            print(f"Error updating all_leads_master.csv: {e}")

    if updated:
        _cached_leads_data.clear()

    return updated

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
    success = update_lead_record(lead_id, {"Status": new_status})
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
        sync_to_supabase.sync()
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

if __name__ == "__main__":
    port = 5000
    print("\n" + "=" * 60)
    print("SANGEETA INFOTECH - ALL-IN-ONE LEAD & OUTREACH HUB")
    print(f">> ULTRA-FAST LOCAL URL: http://127.0.0.1:{port}")
    print(f">> Network / Hostname:   http://localhost:{port}")
    print("=" * 60 + "\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
