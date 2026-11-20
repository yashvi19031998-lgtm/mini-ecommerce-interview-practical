"""
Automated Festival Schedule Dispatcher Cron Job
Sangeeta Infotech Digital Media Automation
Executes daily, checks upcoming festivals within 24 hours, and prepares/dispatches
branded festival posts to enrolled active clients.
"""

import sys
import os
import json
from datetime import datetime, date, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import festival_offers_engine as engine

def run_festival_daily_check():
    today_str = date.today().isoformat()
    tomorrow_str = (date.today() + timedelta(days=1)).isoformat()
    
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🎨 Checking Festival Dispatches for {today_str}...")

    schedules = engine.get_all_schedules()
    clients = {c["id"]: c for c in engine.get_all_clients()}
    
    dispatched_count = 0
    due_items = [
        s for s in schedules 
        if s.get("status") == "SCHEDULED" and s.get("dispatch_date") in [today_str, tomorrow_str]
    ]

    print(f"[*] Found {len(due_items)} festival dispatches due today/tomorrow.")

    for item in due_items:
        cid = item.get("client_id")
        client = clients.get(cid)
        if not client or client.get("status") != "PAID_ACTIVE":
            continue

        fid = item.get("festival_id")
        # Generate SVG creative
        svg = engine.generate_festival_creative_svg(client, fid)
        svg_filename = f"creative_{cid}_{fid}.svg"
        out_path = os.path.join(engine.DATA_DIR, svg_filename)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(svg)

        item["status"] = "DISPATCHED"
        item["dispatched_at"] = datetime.now().isoformat()
        item["creative_file"] = svg_filename
        dispatched_count += 1
        print(f"[+] Dispatched festival {fid} for client '{client.get('business_name')}' to {client.get('phone')}")

    # Save updated schedules
    with open(engine.SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(schedules, f, indent=2, ensure_ascii=False)

    print(f"[*] Completed festival check. {dispatched_count} creatives dispatched.")
    return dispatched_count

if __name__ == "__main__":
    run_festival_daily_check()
