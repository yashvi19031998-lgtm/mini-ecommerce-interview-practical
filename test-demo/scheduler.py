import time
import subprocess
import sys
import os
from datetime import datetime

# Schedule configuration
INTERVAL_HOURS = 2
INTERVAL_SECONDS = INTERVAL_HOURS * 3600

# Choose default scraper script:
# "scraper.py" for fast targeted web search
# "run_all_scrapers.py" for complete 10-harvester multi-source crawl
SCRAPER_SCRIPT = os.getenv("AUTO_SCRAPER_SCRIPT", "run_all_scrapers.py")

def run_scheduled_job():
    start_time = datetime.now()
    now_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
    
    print("\n" + "=" * 65)
    print(f"[{now_str}] ⚡ STARTING AUTOMATED 2-HOUR RUN: {SCRAPER_SCRIPT}")
    print("Features: Direct Email Outreach + Supabase Cloud DB Sync")
    print("=" * 65 + "\n")
    
    try:
        # Run scraper process with live standard output
        proc = subprocess.run([sys.executable, SCRAPER_SCRIPT], check=False)
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        print("\n" + "=" * 65)
        print(f"[{end_time.strftime('%Y-%m-%d %H:%M:%S')}] Job Finished! (Duration: {duration:.1f}s, Exit Code: {proc.returncode})")
        print("=" * 65)
    except Exception as e:
        print(f"[ERROR] Failed to execute scheduled scraper: {e}")

    next_run = datetime.fromtimestamp(time.time() + INTERVAL_SECONDS).strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n⏰ Next automated run scheduled at: {next_run}")
    print(f"💤 Sleeping for {INTERVAL_HOURS} hours...\n")

def main():
    print(f"============================================================")
    print(f"   SANGEETA INFOTECH - 2-HOUR AUTONOMOUS LEAD ENGINE")
    print(f"   Script: {SCRAPER_SCRIPT} | Interval: Every {INTERVAL_HOURS} Hours")
    print(f"============================================================")
    print("Press Ctrl + C at any time to pause or stop.\n")
    
    while True:
        run_scheduled_job()
        try:
            time.sleep(INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\nAutomated 2-hour scheduler stopped by user.")
            break

if __name__ == "__main__":
    main()
