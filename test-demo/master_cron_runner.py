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
import json
import argparse
import threading
import subprocess
import datetime
from typing import Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

PYTHON_EXE = sys.executable or "python"

# Default intervals (in seconds)
INTERVAL_SCRAPER = int(os.getenv("INTERVAL_SCRAPER_SECONDS", 3600))        # 60 mins
INTERVAL_FREELANCE = int(os.getenv("INTERVAL_FREELANCE_SECONDS", 7200))    # 2 hours (Reddit blocks faster polling)
INTERVAL_OUTREACH = int(os.getenv("INTERVAL_OUTREACH_SECONDS", 3600))      # 60 mins
REPORT_HOUR = int(os.getenv("DAILY_REPORT_HOUR", 20))                      # 20:00 (8:00 PM)

# A job that runs longer than this is stopped, so one hung scraper (e.g. a stuck browser) never blocks the rest.
JOB_TIMEOUTS = {
    "cron_job_scrapers.py": int(os.getenv("TIMEOUT_SCRAPER_SECONDS", 2700)),        # 45 min
    "cron_job_freelance_scraper.py": int(os.getenv("TIMEOUT_FREELANCE_SECONDS", 1200)),
    "cron_job_email_outreach.py": int(os.getenv("TIMEOUT_OUTREACH_SECONDS", 2400)),
    "cron_job_daily_report.py": int(os.getenv("TIMEOUT_REPORT_SECONDS", 600)),
}
# Outreach e-mail only on these days / hours (local time): people read mail at work, night mail looks like spam.
OUTREACH_DAYS = {int(d) for d in os.getenv("OUTREACH_DAYS", "0,1,2,3,4,5").split(",") if d.strip().isdigit()}  # Mon=0
OUTREACH_HOURS = os.getenv("OUTREACH_HOURS", "10-19")                                                          # from-to
LOG_DIR = os.path.join(BASE_DIR, "logs", "cron")
STATUS_FILE = os.path.join(BASE_DIR, "logs", "cron_status.json")
CHILD_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}


def _log_line(path: str, text: str) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    except OSError:
        pass


def sync_database(required: bool) -> bool:
    """Pull the latest data (leads, sent-mail log) from the database before a job. False when it failed."""
    try:
        proc = subprocess.run([PYTHON_EXE, os.path.join(BASE_DIR, "datastore.py"), "sync"] + (["--required"] if required else []),
                              cwd=BASE_DIR, env=CHILD_ENV, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=300)
        return proc.returncode == 0
    except Exception:
        return False


def _hours():
    try:
        lo, hi = (int(x) for x in OUTREACH_HOURS.split("-")[:2])
        return lo, hi
    except ValueError:
        return 10, 19


def in_outreach_window(now: Optional[datetime.datetime] = None) -> bool:
    now = now or datetime.datetime.now()
    lo, hi = _hours()
    return now.weekday() in OUTREACH_DAYS and lo <= now.hour < hi


def next_outreach_window(now: Optional[datetime.datetime] = None) -> datetime.datetime:
    now = now or datetime.datetime.now()
    t = now.replace(minute=0, second=0, microsecond=0)
    for _ in range(24 * 8):
        t += datetime.timedelta(hours=1)
        if in_outreach_window(t):
            return t
    return now + datetime.timedelta(hours=1)


def _kill_tree(proc: subprocess.Popen) -> None:
    """Stop a job and everything it started (browsers, helper processes)."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=30)
        else:
            proc.kill()
    except Exception:
        pass


def run_logged(cmd: list, log_path: str, timeout: int) -> int:
    """Runs a job, shows its output live and keeps it in log_path. Exit code; 124 = stopped at its time limit."""
    _log_line(log_path, f"\n===== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} START {os.path.basename(cmd[-1])}")
    proc = subprocess.Popen(cmd, cwd=BASE_DIR, env=CHILD_ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", bufsize=1)

    def pump():
        for line in proc.stdout:
            line = line.rstrip("\n")
            try:
                print(line, flush=True)
            except UnicodeEncodeError:
                print(line.encode("ascii", "replace").decode(), flush=True)
            _log_line(log_path, line)

    reader = threading.Thread(target=pump, daemon=True)
    reader.start()
    try:
        code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        code = 124
        _log_line(log_path, f"[CRON] stopped after {timeout}s (time limit)")
        print(f"[CRON] {os.path.basename(cmd[-1])} stopped after {timeout}s (time limit)")
    reader.join(timeout=10)
    _log_line(log_path, f"===== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} END exit={code}")
    return code


_ALL_JOBS: list = []


def write_status(jobs: list) -> None:
    """logs/cron_status.json: what each job did last and when it runs next."""
    try:
        os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
        data = {"updated_at": f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}", "pid": os.getpid(), "jobs": [
            {"name": j.name, "script": j.script_name,
             "last_run": f"{j.last_run:%Y-%m-%d %H:%M:%S}" if j.last_run else "",
             "last_status": j.last_status, "last_duration_s": round(j.last_duration, 1),
             "next_run": f"{j.next_run:%Y-%m-%d %H:%M:%S}"} for j in jobs]}
        tmp = STATUS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1)
        os.replace(tmp, STATUS_FILE)
    except OSError:
        pass


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
        is_outreach = self.script_name == "cron_job_email_outreach.py"
        log_path = os.path.join(LOG_DIR, f"{os.path.splitext(self.script_name)[0]}_{start_ts:%Y-%m-%d}.log")
        if is_outreach and not in_outreach_window(start_ts):
            self.last_status = "WAITING (outside office hours)"
            self.next_run = next_outreach_window(start_ts)
            print(f"[*] Outreach e-mail waits for office hours; next try {self.next_run:%Y-%m-%d %H:%M}")
            write_status(_ALL_JOBS)
            return False
        try:
            # Latest leads and sent-mail log first: otherwise a lead found elsewhere is added again, or a lead
            # e-mailed from GitHub / the app gets a second mail. For outreach the sync is required.
            if not sync_database(required=is_outreach) and is_outreach:
                self.last_status = "SKIPPED (database sync failed - no mail sent)"
                print("[!] Database sync failed - outreach skipped so nobody gets a second mail. Tried again next round.")
            else:
                code = run_logged([PYTHON_EXE, self.script_path], log_path, JOB_TIMEOUTS.get(self.script_name, 3600))
                self.last_duration = (datetime.datetime.now() - start_ts).total_seconds()
                if code == 0:
                    self.last_status = "SUCCESS"
                    success = True
                    print(f"\n[*] ✅ {self.name} completed successfully in {self.last_duration:.1f}s")
                elif code == 124:
                    self.last_status = "STOPPED (time limit)"
                    print(f"\n[!] ⚠️ {self.name} was stopped at its time limit - see {log_path}")
                else:
                    self.last_status = f"ERROR (exit code {code})"
                    print(f"\n[!] ⚠️ {self.name} finished with error code: {code} - see {log_path}")
        except Exception as e:
            self.last_duration = (datetime.datetime.now() - start_ts).total_seconds()
            self.last_status = f"FAILED: {e}"
            print(f"\n[!] ❌ Exception executing {self.name}: {e}")

        self.next_run = self.calculate_next_run(initial=False)
        write_status(_ALL_JOBS)
        print(f"[*] Next run scheduled at: {self.next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70 + "\n")
        return success


def print_banner(jobs: list):
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("\n" + "█" * 70)
    print("  TEST-DEMO — AUTONOMOUS 4-IN-1 MASTER CRON ENGINE")
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
    _ALL_JOBS[:] = jobs
    write_status(jobs)
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
        except Exception as e:  # the engine itself must keep running
            print(f"[CRON] loop error: {e} - continuing in 30s")
            time.sleep(30)


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

    _ALL_JOBS[:] = jobs
    if args.once:
        print("[*] Running all 4 jobs once (--once mode)...")
        for j in jobs:
            j.execute()
        print("[*] All jobs finished. Exiting.")
        sys.exit(0)

    run_continuous_loop(jobs)


if __name__ == "__main__":
    main()
