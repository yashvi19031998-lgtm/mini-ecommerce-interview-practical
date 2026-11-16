"""
Master Cron Engine — Autonomous 4-in-1 Continuous Scheduler
===========================================================
Orchestrates the 4 vital autonomous lead & client acquisition operations:

  [1] General Multi-Source Scraper      -> Runs every 60 minutes
  [2] AI Concept-Wise Email Outreach     -> Runs every 60 minutes (Updates DB & Supabase upon send)
  [3] Freelance & Project Leads Scraper  -> Runs every 30 minutes
  [4] Daily Summary & Pipeline Report    -> Runs daily at 20:00 (8:00 PM)

Features:
- Single CMD command start: 'run_cron_engine.bat' or 'python master_cron_runner.py'
- Process isolation: Each job runs safely in its own subprocess without memory leaks
- Live status dashboard in terminal with real-time countdown to next runs
- Instant DB & Supabase sync verification after each outreach dispatch
- Graceful shutdown on Ctrl + C
"""

import os
import sys
import time
import argparse
import subprocess
import datetime
from typing import Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

PYTHON_EXE = sys.executable or "python"

# Default intervals (in seconds)
INTERVAL_SCRAPER = int(os.getenv("INTERVAL_SCRAPER_SECONDS", 3600))        # 60 mins
INTERVAL_FREELANCE = int(os.getenv("INTERVAL_FREELANCE_SECONDS", 1800))    # 30 mins
INTERVAL_OUTREACH = int(os.getenv("INTERVAL_OUTREACH_SECONDS", 3600))      # 60 mins
REPORT_HOUR = int(os.getenv("DAILY_REPORT_HOUR", 20))                      # 20:00 (8:00 PM)


class ScheduledJob:
    def __init__(self, name: str, script_name: str, interval_sec: int, description: str, is_daily: bool = False, daily_hour: int = 20):
        self.name = name
        self.script_name = script_name
        self.script_path = os.path.join(BASE_DIR, script_name)
        self.interval_sec = interval_sec
        self.description = description
        self.is_daily = is_daily
        self.daily_hour = daily_hour
        self.last_run: Optional[datetime.datetime] = None
        self.last_status: str = "PENDING"
        self.last_duration: float = 0.0
        self.next_run: datetime.datetime = self.calculate_next_run(initial=True)

    def calculate_next_run(self, initial: bool = False) -> datetime.datetime:
        now = datetime.datetime.now()
        if self.is_daily:
            target = now.replace(hour=self.daily_hour, minute=0, second=0, microsecond=0)
            if initial and target > now:
                return target
            if target <= now:
                target += datetime.timedelta(days=1)
            return target
        else:
            if initial:
                # Stagger startup slightly so jobs don't all slam the CPU at millisecond zero
                offset = 0
                if "Freelance" in self.name:
                    offset = 2
                elif "Outreach" in self.name:
                    offset = 4
                return now + datetime.timedelta(seconds=offset)
            return now + datetime.timedelta(seconds=self.interval_sec)

    def is_due(self) -> bool:
        return datetime.datetime.now() >= self.next_run

    def execute(self) -> bool:
        start_ts = datetime.datetime.now()
        self.last_run = start_ts
        print("\n" + "=" * 70)
        print(f"[{start_ts.strftime('%Y-%m-%d %H:%M:%S')}] ⚡ EXECUTING: {self.name.upper()}")
        print(f"Script: {self.script_name} | {self.description}")
        print("=" * 70)

        success = False
        try:
            # Execute script in isolated subprocess with live stdout
            proc = subprocess.run([PYTHON_EXE, self.script_path], cwd=BASE_DIR, check=False)
            self.last_duration = (datetime.datetime.now() - start_ts).total_seconds()
            if proc.returncode == 0:
                self.last_status = "SUCCESS"
                success = True
                print(f"\n[*] ✅ {self.name} completed successfully in {self.last_duration:.1f}s")
            else:
                self.last_status = f"ERROR (exit code {proc.returncode})"
                print(f"\n[!] ⚠️ {self.name} finished with error code: {proc.returncode}")
        except Exception as e:
            self.last_duration = (datetime.datetime.now() - start_ts).total_seconds()
            self.last_status = f"FAILED: {e}"
            print(f"\n[!] ❌ Exception executing {self.name}: {e}")

        self.next_run = self.calculate_next_run(initial=False)
        print(f"[*] Next run scheduled at: {self.next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70 + "\n")
        return success


def print_banner(jobs: list):
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("\n" + "█" * 70)
    print("  SANGEETA INFOTECH — AUTONOMOUS 4-IN-1 MASTER CRON ENGINE")
    print(f"  Live Status: 🟢 ACTIVE | Current Time: {now_str}")
    print("█" * 70)
    print("  Active Scheduled Jobs:")
    for idx, j in enumerate(jobs, start=1):
        freq = f"Daily at {j.daily_hour}:00" if j.is_daily else f"Every {j.interval_sec // 60}m"
        next_in = max(0, int((j.next_run - datetime.datetime.now()).total_seconds()))
        mins, secs = divmod(next_in, 60)
        status_label = f"[{j.last_status}]" if j.last_run else "[READY]"
        print(f"  [{idx}] {j.name:<28} | {freq:<14} | Next in: {mins:02d}m {secs:02d}s {status_label}")
    print("─" * 70)
    print("  Press Ctrl + C at any time to safely stop.")
    print("█" * 70 + "\n")


def build_jobs(run_now: bool = False) -> list:
    jobs = [
        ScheduledJob(
            name="General Multi-Source Scraper",
            script_name="cron_job_scrapers.py",
            interval_sec=INTERVAL_SCRAPER,
            description="Scrapes Google Maps, Justdial, YellowPages, Quora & Search Engines"
        ),
        ScheduledJob(
            name="Freelance & Project Scraper",
            script_name="cron_job_freelance_scraper.py",
            interval_sec=INTERVAL_FREELANCE,
            description="Gathers direct client hiring & project gigs from Upwork, Reddit, HN, Telegram"
        ),
        ScheduledJob(
            name="AI Cold Email Outreach",
            script_name="cron_job_email_outreach.py",
            interval_sec=INTERVAL_OUTREACH,
            description="Personalizes email by tech requirement, sends via Gmail SMTP & updates DB"
        ),
        ScheduledJob(
            name="Daily Summary Report",
            script_name="cron_job_daily_report.py",
            interval_sec=86400,
            description="Generates daily operations report & emails executive summary to admin",
            is_daily=True,
            daily_hour=REPORT_HOUR
        ),
    ]

    if run_now:
        now = datetime.datetime.now()
        for idx, j in enumerate(jobs):
            j.next_run = now + datetime.timedelta(seconds=idx * 2)

    return jobs


def run_continuous_loop(jobs: list):
    print_banner(jobs)
    last_banner_time = time.time()

    while True:
        try:
            # Check each job in order
            for job in jobs:
                if job.is_due():
                    job.execute()
                    print_banner(jobs)
                    last_banner_time = time.time()

            # Refresh banner every 5 minutes if idle
            if time.time() - last_banner_time > 300:
                print_banner(jobs)
                last_banner_time = time.time()

            time.sleep(2)
        except KeyboardInterrupt:
            print("\n\n" + "█" * 70)
            print("  🛑 Master Cron Engine stopped by user (Ctrl + C). Exiting cleanly.")
            print("█" * 70 + "\n")
            break


def main():
    parser = argparse.ArgumentParser(description="Autonomous 4-in-1 Master Cron Engine")
    parser.add_argument("--run-now", action="store_true", help="Execute all 4 jobs immediately on startup")
    parser.add_argument("--once", action="store_true", help="Run all 4 jobs once and exit (no loop)")
    parser.add_argument("--job", choices=["scraper", "freelance", "outreach", "report"], help="Run only one specific job")
    args = parser.parse_args()

    # Map single job
    if args.job:
        job_map = {
            "scraper": ("cron_job_scrapers.py", "General Multi-Source Scraper"),
            "freelance": ("cron_job_freelance_scraper.py", "Freelance & Project Scraper"),
            "outreach": ("cron_job_email_outreach.py", "AI Cold Email Outreach"),
            "report": ("cron_job_daily_report.py", "Daily Summary Report")
        }
        script, label = job_map[args.job]
        print(f"[*] Executing single job: {label} ({script})...")
        proc = subprocess.run([PYTHON_EXE, os.path.join(BASE_DIR, script)], cwd=BASE_DIR)
        sys.exit(proc.returncode)

    jobs = build_jobs(run_now=args.run_now)

    if args.once:
        print("[*] Running all 4 jobs once (--once mode)...")
        for j in jobs:
            j.execute()
        print("[*] All jobs finished. Exiting.")
        sys.exit(0)

    run_continuous_loop(jobs)


if __name__ == "__main__":
    main()
