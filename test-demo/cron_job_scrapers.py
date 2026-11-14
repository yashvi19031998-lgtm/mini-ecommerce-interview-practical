"""
CRON JOB 1: Multi-Source Business Lead Scraper
==============================================
Runs the complete multi-source business scraper suite:
- Google Maps, Justdial, YellowPages, Quora, DuckDuckGo, SearXNG, Business Directories.
- Performs deduplication, deep website contact extraction, and normalization.
- Safely commits new unique leads to all_leads_master.csv and syncs with Supabase.
- Does NOT send cold emails directly (outreach is isolated to CronJob 2).

Recommended Schedule: Every 2 to 4 hours (e.g. '0 */3 * * *')
"""

import os
import sys
import time
import datetime

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from run_all_scrapers import run_all_scrapers, acquire_run_lock, release_run_lock

def main():
    start_ts = datetime.datetime.now()
    print("=" * 68)
    print(f"[{start_ts.strftime('%Y-%m-%d %H:%M:%S')}] 🚀 CRON JOB 1: MULTI-SOURCE LEAD SCRAPER STARTED")
    print("=" * 68)

    try:
        # Run all general scrapers with send_email=False
        run_all_scrapers(send_email=False, group=None)
        duration = (datetime.datetime.now() - start_ts).total_seconds()
        print("\n" + "=" * 68)
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ CRON JOB 1 FINISHED (Duration: {duration:.1f}s)")
        print("=" * 68)
        sys.exit(0)
    except SystemExit as se:
        if se.code != 0:
            print(f"[CRON-SCRAPER] Exited with code {se.code}")
        sys.exit(se.code)
    except Exception as e:
        print(f"\n[CRON-SCRAPER ERROR] Fatal exception during scraper cron: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

