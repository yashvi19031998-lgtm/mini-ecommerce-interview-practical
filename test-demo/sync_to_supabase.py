import os
import json
import pandas as pd
import requests

def load_env(env_path=".env"):
    """Load key-value pairs from .env into os.environ if not already present."""
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip("'\"")
            if k not in os.environ:
                os.environ[k] = v

load_env()

SUPABASE_URL = (
    os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    or os.getenv("SUPABASE_URL")
    or ""
).rstrip("/ ")

SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    or os.getenv("SUPABASE_KEY")
    or ""
).strip()

CSV_FILE = "leads_new.csv"

def sync(csv_filepath=None):
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Error: Missing SUPABASE_URL or SUPABASE_KEY in environment or .env file.")
        return

    target_file = csv_filepath or CSV_FILE
    if not os.path.exists(target_file):
        print(f"Error: {target_file} does not exist.")
        return

    df = pd.read_csv(target_file)
    print(f"Read {len(df)} leads from {target_file}")

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

    endpoint = f"{SUPABASE_URL}/rest/v1/leads"
    
    success_count = 0
    for _, row in df.iterrows():
        # Handle field mappings for both leads_new.csv and all_leads_master.csv
        company = (
            row.get("company_name")
            or row.get("Company Name")
            or row.get("Company / Domain")
            or ""
        )
        website = row.get("website") or row.get("Website URL") or ""
        phone = row.get("mobile_number") or row.get("Mobile Number") or row.get("Phone") or ""
        location = row.get("location") or row.get("Address") or row.get("Location") or ""
        lead_type = row.get("lead_type") or row.get("Lead Type") or row.get("Category / Intent") or "Potential Buyer"
        source = row.get("source") or row.get("Search Query") or "Unified Master Scraper"
        source_url = row.get("source_url") or website
        description = row.get("description") or row.get("Page Title") or ""
        email = row.get("email") or row.get("Email") or ""
        full_name = row.get("full_name") or ""

        curr_status = str(row.get("lead_status") or row.get("Status") or row.get("email_status") or row.get("Email Status") or "NEW").strip().upper()
        if curr_status in ["SENT", "EMAIL_SENT"]:
            lead_status_val = "CONTACTED"
        elif curr_status in ["DISQUALIFIED", "REJECTED"]:
            lead_status_val = "DISQUALIFIED"
        elif curr_status in ["QUALIFIED", "INTERESTED"]:
            lead_status_val = "QUALIFIED"
        else:
            lead_status_val = "NEW"

        lead_data = {
            "company_name": str(company).strip() if pd.notna(company) and str(company).strip() else None,
            "website": str(website).strip() if pd.notna(website) and str(website).strip() and str(website) != "N/A" else None,
            "phone": str(phone).strip() if pd.notna(phone) and str(phone).strip() and str(phone) != "N/A" else None,
            "location": str(location).strip() if pd.notna(location) and str(location).strip() and str(location) != "N/A" else None,
            "lead_type": str(lead_type).strip() if pd.notna(lead_type) and str(lead_type).strip() else "Potential Buyer",
            "lead_quality": "High",
            "lead_status": lead_status_val,
            "source_platform": str(source)[:50] if pd.notna(source) and str(source).strip() else "Multi-Source Harvester",
            "source_url": str(source_url).strip() if pd.notna(source_url) and str(source_url).strip() else None,
            "project_description": str(description)[:400] if pd.notna(description) and str(description).strip() else None,
        }
        
        if pd.notna(email) and str(email).strip() and str(email) != "N/A":
            clean_email = str(email).split(",")[0].strip()
            lead_data["email"] = clean_email
            if not full_name:
                lead_data["full_name"] = clean_email.split("@")[0].capitalize()
            else:
                lead_data["full_name"] = str(full_name).strip()
        elif full_name:
            lead_data["full_name"] = str(full_name).strip()

        try:
            r = requests.post(endpoint, headers=headers, json=lead_data)
            if r.status_code in [200, 201]:
                success_count += 1
            else:
                print(f"Failed to insert {lead_data.get('company_name')}: {r.status_code} - {r.text}")
        except Exception as e:
            print(f"Error inserting {lead_data.get('company_name')}: {e}")

    print(f"\n==========================================")
    print(f"Successfully synced {success_count} / {len(df)} leads to Supabase!")
    print(f"==========================================")

if __name__ == "__main__":
    sync()
