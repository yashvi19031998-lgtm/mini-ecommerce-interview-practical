"""Keeps all app data in ONE Supabase table (public.app_data), shared by this PC and GitHub Actions.

Every record is one row:  kind | key | data (jsonb) | hash | pos | updated_at
    kind = lead | activity | sent_email | scraper_run | source_quality | state | meta
    lead            one lead                        (all_leads_master.csv,       key = lead_id)
    activity        one follow-up activity          (logs/followup_activity.csv, key = activity_id)
    sent_email      one e-mail sent                 (logs/sent_emails.csv)
    scraper_run     one scraper run                 (logs/scraper_runs.csv)
    source_quality  one row of the source report    (logs/source_quality.csv,    key = source)
    state           one settings/state JSON file    (company_settings.json, logs/*.json; key = file name)
    meta            column order of each CSV        (key = "columns:<kind>")

The app keeps working on local files (a working copy). sync() merges both ways, row by row:
  - a row changed only here      -> sent to the database
  - a row changed only in the DB -> written into the local file
  - changed on both sides        -> this machine's version wins (a delete never beats an edit)
The last agreed state is kept in .datastore/snapshot.json, so each side only sends what changed.
Mass deletes (more than 30% of a file at once) are refused - a truncated file never wipes the database.

Usage:  python datastore.py sync [--required]     (--required: exit 1 if the database cannot be reached)
        python datastore.py status
Setup:  run the SQL in docs/database.md once in the Supabase SQL editor.
"""
import csv
import hashlib
import io
import json
import os
import sys
import threading
import time

import env_loader  # noqa: F401  (loads .env)

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TABLE = "app_data"
SNAPSHOT = os.path.join(BASE_DIR, ".datastore", "snapshot.json")
STATUS_FILE = os.path.join(BASE_DIR, ".datastore", "last_sync.json")
PAGE = 1000          # Supabase returns at most 1000 rows per request
BATCH = 200          # rows per upsert request
KEYS_PER_GET = 80    # keys per "in.(...)" filter (URL length)
MAX_DELETE_SHARE = 0.30

# kind -> (file, key column or None = content hash)
CSV_KINDS = {
    "lead": ("all_leads_master.csv", "lead_id"),
    "activity": (os.path.join("logs", "followup_activity.csv"), "activity_id"),
    "sent_email": (os.path.join("logs", "sent_emails.csv"), None),
    "scraper_run": (os.path.join("logs", "scraper_runs.csv"), None),
    "source_quality": (os.path.join("logs", "source_quality.csv"), "source"),
}
# Settings are changed only in the app on the owner's PC: GitHub Actions reads them, never writes them back.
OWNER_ONLY_STATE = {"company_settings.json", "followup_templates.json"}
STATE_FILES = [
    "company_settings.json",
    "followup_templates.json",
    os.path.join("logs", "mail_check_status.json"),
    os.path.join("logs", "imap_state.json"),
]

sync_lock = threading.Lock()

# The one table (same SQL as docs/database.md). RLS on with no policies: only the service_role key can use it.
SETUP_SQL = """
create table if not exists public.app_data (
  kind       text        not null,
  key        text        not null,
  data       jsonb       not null,
  hash       text        not null,
  pos        integer     not null default 0,
  updated_at timestamptz not null default now(),
  primary key (kind, key)
);
alter table public.app_data enable row level security;
create index if not exists app_data_kind_updated on public.app_data (kind, updated_at desc);
notify pgrst, 'reload schema';
"""


def setup_table():
    """Create the table using SUPABASE_DB_URL (Supabase -> Connect -> connection string, with the DB password)."""
    db_url = os.getenv("SUPABASE_DB_URL", "").strip()
    if not db_url:
        raise DatastoreError("SUPABASE_DB_URL is not set in .env - or run the SQL in docs/database.md by hand")
    try:
        import psycopg
    except ImportError:
        raise DatastoreError("install the driver first: pip install \"psycopg[binary]\"")
    with psycopg.connect(db_url, connect_timeout=20) as conn:
        conn.execute(SETUP_SQL)
        conn.commit()


class _ProcessLock:
    """Only one process (app, scraper run, CLI) syncs at a time. A lock older than 10 minutes is stale."""
    def __init__(self, wait_sec=90):
        self.wait_sec = wait_sec
        self.path = None

    def __enter__(self):
        path = os.path.join(os.path.dirname(SNAPSHOT), "sync.lock")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        deadline = time.time() + self.wait_sec
        while True:
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                self.path = path
                return self
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(path) > 600:
                        os.remove(path)
                        continue
                except OSError:
                    continue
                if time.time() > deadline:
                    raise DatastoreError("another sync is still running")
                time.sleep(1)

    def __exit__(self, *a):
        try:
            if self.path:
                os.remove(self.path)
        except OSError:
            pass
        return False


class DatastoreError(RuntimeError):
    pass


# ---------------------------------------------------------------- connection
def _config():
    url = (os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL") or "").rstrip("/ ")
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY") or "").strip()
    return url, key


def configured() -> bool:
    url, key = _config()
    return bool(url and key and requests)


def _req(method, params="", body=None, headers=None):
    url, key = _config()
    h = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    h.update(headers or {})
    for attempt in range(3):
        try:
            r = requests.request(method, f"{url}/rest/v1/{TABLE}{params}", headers=h,
                                 data=None if body is None else json.dumps(body), timeout=60)
        except requests.RequestException as e:
            if attempt == 2:
                raise DatastoreError(f"database not reachable: {e}")
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code >= 500 and attempt < 2:
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code >= 300:
            hint = " - run the SQL in docs/database.md first" if "PGRST205" in r.text else ""
            raise DatastoreError(f"database answered {r.status_code}: {r.text[:200]}{hint}")
        return r.json() if r.text.strip() else []
    raise DatastoreError("database not reachable")


def _in(keys):
    return "in.(" + ",".join('"' + k.replace('"', '') + '"' for k in keys) + ")"


def remote_hashes(kind):
    """key -> hash of every row of this kind in the database."""
    out, offset = {}, 0
    while True:
        rows = _req("GET", f"?select=key,hash&kind=eq.{kind}&order=key&limit={PAGE}&offset={offset}")
        out.update({r["key"]: r["hash"] for r in rows})
        if len(rows) < PAGE:
            return out
        offset += PAGE


def remote_rows(kind, keys):
    out = {}
    keys = list(keys)
    for i in range(0, len(keys), KEYS_PER_GET):
        for r in _req("GET", f"?select=key,data,hash,pos&kind=eq.{kind}&key={_in(keys[i:i + KEYS_PER_GET])}"):
            out[r["key"]] = r
    return out


def upsert(kind, rows):
    """rows: list of {"key", "data", "hash", "pos"}"""
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    payload = [{"kind": kind, "updated_at": stamp, **r} for r in rows]
    for i in range(0, len(payload), BATCH):
        _req("POST", "?on_conflict=kind,key", payload[i:i + BATCH],
             {"Prefer": "resolution=merge-duplicates,return=minimal"})


def delete(kind, keys):
    keys = list(keys)
    for i in range(0, len(keys), KEYS_PER_GET):
        _req("DELETE", f"?kind=eq.{kind}&key={_in(keys[i:i + KEYS_PER_GET])}", headers={"Prefer": "return=minimal"})


# ---------------------------------------------------------------- local files
def _hash(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def read_csv_file(path, key_col):
    """-> (columns, {key: (row, pos)}, fmt) or (None, None, None) when the file does not exist."""
    if not os.path.exists(path):
        return None, None, None
    with open(path, "rb") as fh:
        raw = fh.read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig", errors="replace")
    newline = "\r\n" if "\r\n" in text[:5000] else "\n"
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        columns = next(reader)
    except StopIteration:
        return [], {}, {"bom": bom, "newline": newline}
    rows, seen = {}, {}
    for pos, values in enumerate(reader):
        if not any(v.strip() for v in values):
            continue
        row = {c: (values[i] if i < len(values) else "") for i, c in enumerate(columns)}
        if len(values) > len(columns):        # stray extra cells: keep them, never drop data
            row["__extra__"] = values[len(columns):]
        if key_col and row.get(key_col, "").strip():
            k = row[key_col].strip()
        else:
            base = _hash(row)[:20]
            seen[base] = seen.get(base, 0) + 1
            k = f"h{base}-{seen[base]}"
        if k in rows:                          # duplicate key in the file: keep both
            k = f"{k}~{pos}"
        rows[k] = (row, pos)
    return columns, rows, {"bom": bom, "newline": newline}


def write_csv_file(path, columns, ordered_rows, fmt):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator=fmt.get("newline", "\n"))
    w.writerow(columns)
    for row in ordered_rows:
        w.writerow([row.get(c, "") for c in columns] + list(row.get("__extra__", [])))
    data = buf.getvalue().encode("utf-8")
    if fmt.get("bom"):
        data = b"\xef\xbb\xbf" + data
    tmp = path + ".sync.tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)


def _load_snapshot():
    try:
        with open(SNAPSHOT, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _save_snapshot(snap):
    os.makedirs(os.path.dirname(SNAPSHOT), exist_ok=True)
    tmp = SNAPSHOT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(snap, fh)
    os.replace(tmp, SNAPSHOT)


# ---------------------------------------------------------------- merge logic
def plan(local, remote, snap):
    """Decide per key. local/remote/snap: {key: hash}; local None = file missing (no local opinion).
    -> (push, delete_remote, pull, delete_local)"""
    push, del_remote, pull, del_local = [], [], [], []
    for k in set(remote) | set(snap) | set(local or {}):
        s, r = snap.get(k), remote.get(k)
        l = s if local is None else local.get(k)
        if l == r:
            continue                                   # both sides agree
        local_changed, remote_changed = l != s, r != s
        if local_changed and not remote_changed:
            (del_remote if l is None else push).append(k)
        elif remote_changed and not local_changed:
            (del_local if r is None else pull).append(k)
        elif l is not None:
            push.append(k)                             # changed on both sides: this machine wins
        else:
            pull.append(k)                             # deleted here but edited in the DB: keep the edit
    return push, del_remote, pull, del_local


def agreed_snapshot(local, remote, snap, push, del_remote, pull, del_local, applied_local):
    """The state both sides share after this sync. Changes not carried out keep the old view,
    so they are tried again next time."""
    new = {}
    for k in set(remote) | set(snap) | set(local or {}):
        s, r = snap.get(k), remote.get(k)
        l = s if local is None else local.get(k)
        if k in push:
            new[k] = l
        elif k in del_remote:
            continue
        elif k in pull or k in del_local:
            if applied_local:
                if r is not None:
                    new[k] = r
            elif s is not None:
                new[k] = s
        elif l == r:
            if r is not None:
                new[k] = r
        elif s is not None:                            # refused delete: nothing changed
            new[k] = s
    return new


def _too_many(n, total):
    return n > 20 and total and n / total > MAX_DELETE_SHARE


def sync_csv(kind, lock=None, report=None):
    rel, key_col = CSV_KINDS[kind]
    path = os.path.join(BASE_DIR, rel)
    snap = _load_snapshot().get(kind, {})
    mtime = os.path.getmtime(path) if os.path.exists(path) else None
    columns, rows, fmt = read_csv_file(path, key_col)
    local = None if rows is None else {k: _hash(r) for k, (r, _) in rows.items()}
    remote = remote_hashes(kind)
    push, del_remote, pull, del_local = plan(local, remote, snap)
    if rows is None:                                   # file missing here: rebuild it from the database
        pull = sorted(remote)

    notes = []
    if _too_many(len(del_remote), len(snap)):
        notes.append(f"refused to delete {len(del_remote)} {kind} rows in the database (too many at once)")
        del_remote = []
    if _too_many(len(del_local), len(local or {})):
        notes.append(f"refused to delete {len(del_local)} local {kind} rows (too many at once)")
        del_local = []

    # column order travels with the data (needed to rebuild the file on a fresh machine)
    meta_key = f"columns:{kind}"
    if columns:
        upsert("meta", [{"key": meta_key, "data": {"columns": columns, **fmt}, "hash": _hash([columns, fmt]), "pos": 0}])
    if push:
        upsert(kind, [{"key": k, "data": rows[k][0], "hash": local[k], "pos": rows[k][1]} for k in push])
    if del_remote:
        delete(kind, del_remote)

    applied = False
    if pull or del_local:
        fetched = remote_rows(kind, pull)
        if columns is None:
            meta = remote_rows("meta", [meta_key]).get(meta_key, {}).get("data") or {}
            columns = list(meta.get("columns") or [])
            fmt = {"bom": meta.get("bom", kind == "lead"), "newline": meta.get("newline", "\n")}
        for r in fetched.values():                     # a column only the database knows about
            for c in r["data"]:
                if c not in columns and c != "__extra__":
                    columns.append(c)
        with (lock if lock is not None else _NoLock()):
            now_mtime = os.path.getmtime(path) if os.path.exists(path) else None
            if now_mtime != mtime:                     # the file was written meanwhile: next time
                notes.append(f"{rel} changed during sync, local update postponed")
            else:
                gone = set(del_local)
                merged = {k: v for k, v in (rows or {}).items() if k not in gone}
                for k in pull:
                    if k in fetched:
                        pos = merged[k][1] if k in merged else fetched[k].get("pos") or 0
                        merged[k] = (fetched[k]["data"], pos)
                order = sorted(merged.items(), key=lambda kv: (kv[1][1], kv[0]))
                try:
                    write_csv_file(path, columns, [r for _, (r, _) in order], fmt)
                    applied = True
                except PermissionError:                # Windows: file open elsewhere right now
                    notes.append(f"{rel} is in use, local update postponed")

    snap_all = _load_snapshot()
    snap_all[kind] = agreed_snapshot(local, remote, snap, set(push), set(del_remote), set(pull),
                                     set(del_local), applied)
    _save_snapshot(snap_all)
    if report is not None:
        report[kind] = {"sent": len(push), "received": len(pull) if applied else 0,
                        "deleted_in_db": len(del_remote), "deleted_here": len(del_local) if applied else 0,
                        "rows": len(snap_all[kind]), "notes": notes}


def sync_state(report=None):
    """Settings/state JSON files: one row per file. A missing file never deletes the database copy."""
    snap = _load_snapshot().get("state", {})
    files = {}
    for rel in STATE_FILES:
        p = os.path.join(BASE_DIR, rel)
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as fh:
                    files[rel.replace(os.sep, "/")] = json.load(fh)
            except ValueError:
                continue
    remote = remote_hashes("state")
    local = {**snap, **{k: _hash(v) for k, v in files.items()}}
    push, _, pull, _ = plan(local, remote, snap)
    push = [k for k in push if k in files]
    if os.getenv("GITHUB_ACTIONS") == "true":
        kept = [k for k in push if k in OWNER_ONLY_STATE]
        push = [k for k in push if k not in OWNER_ONLY_STATE]
        pull += [k for k in kept if k in remote]          # put the owner's version back
    if push:
        upsert("state", [{"key": k, "data": files[k], "hash": local[k], "pos": 0} for k in push])
    for k, r in remote_rows("state", pull).items():
        p = os.path.join(BASE_DIR, *k.split("/"))
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        tmp = p + ".sync.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(r["data"], fh, indent=2, ensure_ascii=False)
        os.replace(tmp, p)
    snap_all = _load_snapshot()
    snap_all["state"] = {**{k: v for k, v in remote.items()}, **{k: local[k] for k in push}}
    _save_snapshot(snap_all)
    if report is not None:
        report["state"] = {"sent": len(push), "received": len(pull)}


class _NoLock:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def sync(lock=None, required=False):
    """Two-way merge of every file with the database. Returns a report dict; never raises unless required."""
    report = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "ok": False}
    if not configured():
        report["error"] = "database not configured (SUPABASE_URL / SUPABASE_KEY)"
        if required:
            raise DatastoreError(report["error"])
        return report
    with sync_lock:
        try:
            with _ProcessLock():
                kinds = report.setdefault("kinds", {})
                for kind in CSV_KINDS:
                    sync_csv(kind, lock=lock if kind == "lead" else None, report=kinds)
                sync_state(kinds)
            report["ok"] = True
        except Exception as e:
            report["error"] = str(e)[:300]
            if required:
                _write_status(report)
                raise
    _write_status(report)
    return report


def _write_status(report):
    try:
        os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
        with open(STATUS_FILE, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1)
    except OSError:
        pass


def last_status():
    try:
        with open(STATUS_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def start_background_sync(lock=None, every_sec=120):
    """Sync now and then every few minutes, in a daemon thread (used by app.py)."""
    if not configured():
        return None

    def loop():
        while True:
            r = sync(lock=lock)
            if not r.get("ok"):
                print(f"[DB] sync failed: {r.get('error')}")
            time.sleep(every_sec)

    t = threading.Thread(target=loop, name="datastore-sync", daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sync"
    if cmd == "setup":
        try:
            setup_table()
        except Exception as e:
            print(f"[DB] setup FAILED: {e}")
            sys.exit(1)
        print("[DB] table public.app_data is ready")
        sys.exit(0)
    if cmd == "status":
        print(json.dumps(last_status(), indent=1))
        sys.exit(0)
    try:
        r = sync(required="--required" in sys.argv)
    except Exception as e:
        print(f"[DB] sync FAILED: {e}")
        sys.exit(1)
    print(json.dumps(r, indent=1))
    sys.exit(0 if r.get("ok") or "--required" not in sys.argv else 1)
