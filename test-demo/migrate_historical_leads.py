"""
Historical Lead Migrator
========================
Safely imports and reconciles all existing leads from previous CSV files
into all_leads_master.csv without loss or duplication.
"""

import os
import csv
import glob
from lead_normalizer import MasterLeadRegistry, normalize_lead_record

CSV_PRIORITY_ORDER = [
    # Master & High-Quality CSVs
    "leads.csv",
    "master_leads.csv",
    "all_leads_clean.csv",
    "all_leads_multi.csv",
    "leads_perfect.csv",
    "instant_leads_master.csv",
    "leads_with_contacts.csv",
    "leads_new_way_direct.csv",
    "freelance_reddit_leads_v2.csv",
    "freelance_reddit_leads.csv",
    "linkedin_leads.csv",
    "b2b_portals_leads.csv",
    "reddit_rss_leads.csv",
]


def migrate_existing_csv_leads(master_file: str = "all_leads_master.csv") -> dict:
    """Reads all historical CSVs, normalizes records, and populates master registry."""
    print("=" * 65)
    print("       HISTORICAL LEAD MIGRATION & RECONCILIATION")
    print("=" * 65)

    registry = MasterLeadRegistry(master_file)
    initial_count = len(registry.leads)
    print(f"[*] Starting with {initial_count} existing leads in '{master_file}'.")

    stats = {
        "files_processed": 0,
        "raw_records_read": 0,
        "new_leads_added": 0,
        "existing_leads_updated": 0,
        "duplicates_skipped": 0,
        "invalid_skipped": 0,
    }

    for filename in CSV_PRIORITY_ORDER:
        if not os.path.exists(filename):
            continue

        stats["files_processed"] += 1
        file_records = 0
        file_added = 0
        file_updated = 0

        try:
            with open(filename, mode="r", encoding="utf-8-sig", errors="ignore") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    continue

                for row in reader:
                    file_records += 1
                    stats["raw_records_read"] += 1

                    # Ignore job seeker / for hire posts from uncurated files
                    title = (row.get("Title") or row.get("Business Name/Title") or "").lower()
                    if "[for hire]" in title or "[for-hire]" in title:
                        stats["invalid_skipped"] += 1
                        continue

                    # Filter out obvious Wikipedia/Microsoft noise from b2b_portals_leads.csv
                    url = (row.get("Portal_URL") or row.get("URL") or "").lower()
                    if "wikipedia.org" in url or "microsoft.com" in url or "softonic.com" in url or "geeksforgeeks.org" in url:
                        stats["invalid_skipped"] += 1
                        continue

                    source_default = f"Imported ({filename})"
                    outcome, is_new = registry.add_lead(row, default_source=source_default)

                    if outcome == "added":
                        stats["new_leads_added"] += 1
                        file_added += 1
                    elif outcome == "updated":
                        stats["existing_leads_updated"] += 1
                        file_updated += 1
                    elif outcome == "duplicate":
                        stats["duplicates_skipped"] += 1
                    else:
                        stats["invalid_skipped"] += 1

            print(f"  [+] {filename:<30} -> Read {file_records:<3} | Added: {file_added:<3} | Updated: {file_updated:<3}")

        except Exception as e:
            print(f"  [!] Error processing {filename}: {e}")

    registry.save_master_safely()
    final_count = len(registry.leads)

    print("-" * 65)
    print(f"[SUCCESS] Historical migration complete!")
    print(f"  - Total Files Processed:     {stats['files_processed']}")
    print(f"  - Total Raw Records Read:    {stats['raw_records_read']}")
    print(f"  - Genuinely New Leads Added: {stats['new_leads_added']}")
    print(f"  - Existing Leads Enriched:   {stats['existing_leads_updated']}")
    print(f"  - Duplicates Skipped:        {stats['duplicates_skipped']}")
    print(f"  - Master Leads Count:        {final_count}")
    print("=" * 65 + "\n")

    return stats


if __name__ == "__main__":
    migrate_existing_csv_leads()
