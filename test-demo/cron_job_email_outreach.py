"""
CRON JOB 2: Dedicated AI Cold Email Outreach Dispatcher
=======================================================
Dispatches high-conversion, requirement-tailored cold outreach emails:
- Filters candidate leads by quality score & deliverability
- Strictly enforces Do-Not-Contact / Excluded Companies shield (e.g. 8dots)
- Generates tailored email copy via AI Email Generator (React, Python, Mobile, Ecommerce)
- STRICT 100% Sangeeta Infotech signature guarantee on every email
- Safely throttles SMTP dispatch (1500ms delay) to maintain 99%+ deliverability
- Logs to logs/sent_emails.csv, followup_store, and syncs status to Supabase

Recommended Schedule: Hourly during office hours (e.g. '0 10-18 * * 1-5')
"""

import os
import sys
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from run_all_scrapers import run_outreach_only

def main():
    start_ts = datetime.datetime.now()
    print("=" * 68)
    print(f"[{start_ts.strftime('%Y-%m-%d %H:%M:%S')}] ✉️ CRON JOB 2: AI COLD EMAIL OUTREACH DISPATCHER STARTED")
    print("=" * 68)

    try:
        run_outreach_only()
        duration = (datetime.datetime.now() - start_ts).total_seconds()
        print("\n" + "=" * 68)
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ CRON JOB 2 FINISHED (Duration: {duration:.1f}s)")
        print("=" * 68)
        sys.exit(0)
    except SystemExit as se:
        if se.code != 0:
            print(f"[CRON-OUTREACH] Exited with code {se.code}")
        sys.exit(se.code)
    except Exception as e:
        print(f"\n[CRON-OUTREACH ERROR] Fatal exception during outreach cron: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

