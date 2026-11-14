"""Saves the app data to Supabase. Kept for the old call sites (scraper runs, lead import, the
"Sync with Supabase" button); the work is done by datastore.py, which keeps EVERYTHING in one
table (public.app_data). The old per-lead upload into the 'leads' table is no longer used."""
import os

import env_loader  # noqa: F401  (loads .env)
import datastore

SUPABASE_URL = (os.getenv("NEXT_PUBLIC_SUPABASE_URL") or os.getenv("SUPABASE_URL") or "").rstrip("/ ")
SUPABASE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY") or "").strip()

_MASTER = os.path.join(datastore.BASE_DIR, "all_leads_master.csv")


def sync(csv_filepath=None, lock=None):
    """Two-way sync of all app data with the database. Returns True when it reached the database.
    A csv_filepath other than the master leads file (a temp file, an old export) is not app data: False."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Error: Missing SUPABASE_URL or SUPABASE_KEY in environment or .env file.")
        return False
    if csv_filepath and os.path.abspath(os.path.join(datastore.BASE_DIR, csv_filepath)) != os.path.abspath(_MASTER):
        print(f"[DB] {csv_filepath} is not the master leads file - not synced.")
        return False
    report = datastore.sync(lock=lock)
    if not report.get("ok"):
        print(f"[DB] sync failed: {report.get('error')}")
        return False
    print(f"[DB] synced: {summary(report)}")
    return True


def summary(report):
    parts = []
    for kind, r in (report.get("kinds") or {}).items():
        if r.get("sent") or r.get("received"):
            parts.append(f"{kind} +{r.get('sent', 0)} up / +{r.get('received', 0)} down")
    return ", ".join(parts) or "already up to date"


if __name__ == "__main__":
    sync()
