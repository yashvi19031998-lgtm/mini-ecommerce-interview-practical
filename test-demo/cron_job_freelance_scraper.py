"""
CRON JOB 4: Specialized Freelancing & Project Leads Scraper
===========================================================
Specialized high-frequency scraper targeting direct client project postings,
freelance gigs, and urgent developer hiring requests:
- Freelancer & Upwork project feeds
- Reddit r/forhire, r/freelance_forhire, r/jobbit
- Hacker News 'Who is Hiring'
- WeWorkRemotely & RemoteOK contractor openings
- Telegram tech lead channels

Recommended Schedule: Every 30 to 60 minutes (e.g. '*/30 * * * *')
"""

import os
import sys
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from run_all_scrapers import run_all_scrapers

def main():
    start_ts = datetime.datetime.now()
    print("=" * 68)
    print(f"[{start_ts.strftime('%Y-%m-%d %H:%M:%S')}] ⚡ CRON JOB 4: FREELANCE & PROJECT LEADS SCRAPER STARTED")
    print("=" * 68)

    try:
        # Run exclusively freelance group without immediate email dispatch
        run_all_scrapers(send_email=False, group="freelance")
        duration = (datetime.datetime.now() - start_ts).total_seconds()
        print("\n" + "=" * 68)
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ CRON JOB 4 FINISHED (Duration: {duration:.1f}s)")
        print("=" * 68)
        sys.exit(0)
    except SystemExit as se:
        if se.code != 0:
            print(f"[CRON-FREELANCE] Exited with code {se.code}")
        sys.exit(se.code)
    except Exception as e:
        print(f"\n[CRON-FREELANCE ERROR] Fatal exception during freelance scraper cron: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

