# Database: one table for everything

All app data is kept in **one Supabase table, `public.app_data`**. The app on the PC and the
GitHub Actions jobs (1-hour scraper, 12 AM report) all read and write this same table.
Nothing with lead data is committed to git any more.

| kind             | one row is…                      | key            | local working file              |
|------------------|----------------------------------|----------------|---------------------------------|
| `lead`           | a lead                           | `lead_id`      | `all_leads_master.csv`          |
| `activity`       | a follow-up activity             | `activity_id`  | `logs/followup_activity.csv`    |
| `sent_email`     | an e-mail that was sent          | content hash   | `logs/sent_emails.csv`          |
| `scraper_run`    | one scraper run                  | content hash   | `logs/scraper_runs.csv`         |
| `source_quality` | one line of the source report    | `source`       | `logs/source_quality.csv`       |
| `state`          | a settings / state file          | file name      | `company_settings.json`, `logs/*.json` |
| `meta`           | column order of a file           | `columns:<kind>` | –                             |

The full record is in the `data` column (JSON). The local files are a working copy that
`datastore.py` keeps in step with the table: on app start, every 2 minutes while the app runs,
after every scraper run / import, and before and after every GitHub run.

## One-time setup

1. Supabase → your project → **SQL Editor** → New query → paste and **Run**:

```sql
create table if not exists public.app_data (
  kind       text        not null,
  key        text        not null,
  data       jsonb       not null,
  hash       text        not null,
  pos        integer     not null default 0,
  updated_at timestamptz not null default now(),
  primary key (kind, key)
);

-- Lead data is private: switch on Row Level Security and add NO policies.
-- Then only the service_role key (backend + GitHub Actions) can read or write; the
-- public anon key used in the browser cannot see anything.
alter table public.app_data enable row level security;

create index if not exists app_data_kind_updated on public.app_data (kind, updated_at desc);
```

2. `.env` on the PC: `SUPABASE_URL` and `SUPABASE_KEY` (the **service_role** key, from
   Supabase → Project Settings → API). Never put the service_role key in the frontend.
3. GitHub → repository → Settings → Secrets and variables → Actions → Secrets:
   `SUPABASE_URL` and `SUPABASE_KEY` with the same values.
4. First upload from the PC: `venv\Scripts\python.exe datastore.py sync`

## Commands

```
python datastore.py sync              # merge local files and the table both ways
python datastore.py sync --required   # same, exit code 1 if the database cannot be used (GitHub)
python datastore.py status            # result of the last sync
```

## How conflicts are handled

- Changed only on one side → that change is copied to the other side.
- Changed on both sides → the machine running the sync wins; a delete never beats an edit.
- More than 30% of a file deleted at once → refused (a broken or emptied file never wipes the table).
- Settings (`company_settings.json`, `followup_templates.json`) are only changed from the app;
  GitHub Actions reads them but never writes them back.
- If the GitHub job cannot load the data it stops before scraping, so it can never e-mail someone
  twice because the sent-mail log was missing.

The old `leads` table (filled by the earlier per-lead upload) is no longer written to.
