import csv
import os
import re
from typing import List, Dict, Any

try:
    from telethon import TelegramClient
    TELETHON_AVAILABLE = True
except ImportError:
    TelegramClient = None
    TELETHON_AVAILABLE = False

# Telegram API Credentials
# Replace with your API ID and HASH from https://my.telegram.org, or set TELEGRAM_API_ID & TELEGRAM_API_HASH environment variables
API_ID = int(os.environ.get("TELEGRAM_API_ID", "30353212"))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "f8c329a35f17c590f3873a47ade224e0")
# Paste your Bot Token here from @BotFather (keep exact case)
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
SESSION_NAME = os.environ.get("TELEGRAM_SESSION_NAME", "lead_scraper_session")
CSV_FILE = "telegram_leads.csv"

# Regex for extracting contacts from message text
EMAIL_REGEX = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
PHONE_REGEX = r"(\+?\d[\d\s\-\(\)]{8,15}\d)"
URL_REGEX = r"(https?://[^\s]+)"
TELEGRAM_HANDLE_REGEX = r"(@[a-zA-Z0-9_]{4,32})"

# Target Public Groups/Channels known for client posts
TARGET_CHANNELS = [
    'remotework',
    'python_jobs',
    'freelance_projects',
    'it_jobs_remote'
]

# Keywords to filter high-intent client messages
KEYWORDS = ['looking for', 'hiring', 'need a developer', 'budget', 'freelancer', 'project', 'developer', 'frontend', 'backend', 'fullstack', 'react', 'python', 'wordpress', 'contract']


def init_csv():
    """Initializes CSV file if not exists."""
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "Channel/Group",
                "Sender Username",
                "Contact Email",
                "Contact Phone",
                "WhatsApp Link",
                "Telegram DM Link",
                "Contact Handle",
                "Project URL",
                "Message",
                "Found Keywords",
                "Date"
            ])
            writer.writeheader()


def save_to_csv(lead_data: Dict[str, Any]):
    """Appends a lead to the CSV."""
    init_csv()
    with open(CSV_FILE, mode="a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "Channel/Group",
            "Sender Username",
            "Contact Email",
            "Contact Phone",
            "WhatsApp Link",
            "Telegram DM Link",
            "Contact Handle",
            "Project URL",
            "Message",
            "Found Keywords",
            "Date"
        ])
        writer.writerow(lead_data)


async def scrape_telegram_leads() -> List[Dict[str, Any]]:
    """Scrapes public Telegram channels for hiring/client leads."""
    collected_leads: List[Dict[str, Any]] = []

    if not TELETHON_AVAILABLE:
        print("[WARN] Telethon library is not available. Run: pip install telethon")
        return collected_leads

    # Check if placeholder credentials are still present
    if API_ID == 12345678 or API_HASH == 'your_api_hash_here':
        print("[INFO] Telegram scraper requires valid API_ID and API_HASH from https://my.telegram.org")
        print("       Set them via TELEGRAM_API_ID and TELEGRAM_API_HASH environment variables or inside telegram_scraper.py.")
        return collected_leads

    init_csv()
    print("[INFO] Initializing Telegram Client...")

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    try:
        if BOT_TOKEN:
            await client.start(bot_token=BOT_TOKEN)
        else:
            await client.start()
        print("[SUCCESS] Connected to Telegram successfully!")
    except Exception as e:
        print(f"[ERROR] Could not start Telegram client: {e}")
        return collected_leads

    total_saved = 0

    for channel_username in TARGET_CHANNELS:
        try:
            print(f"\n[INFO] Scanning channel: @{channel_username}...")
            entity = await client.get_entity(channel_username)

            # Fetch recent messages (e.g., last 100 messages)
            async for message in client.iter_messages(entity, limit=100):
                if not message.text:
                    continue

                text_lower = message.text.lower()
                matched_keywords = [kw for kw in KEYWORDS if kw in text_lower]

                if matched_keywords:
                    sender = await message.get_sender()
                    username = f"@{sender.username}" if sender and getattr(sender, 'username', None) else getattr(sender, 'first_name', 'Unknown')

                    # 1. Email extraction
                    emails = re.findall(EMAIL_REGEX, message.text)
                    valid_emails = [e for e in emails if not e.endswith(('.png', '.jpg', '.jpeg', '.webp'))]

                    # 2. Phone extraction (clean numbers only)
                    raw_phones = re.findall(PHONE_REGEX, message.text)
                    valid_phones = []
                    for p in raw_phones:
                        cleaned = re.sub(r'[\s\-\(\)]', '', p)
                        # Valid mobile phone length (10 to 14 digits)
                        if 10 <= len(cleaned.replace('+', '')) <= 14:
                            valid_phones.append(p.strip())

                    # 3. URL extraction
                    urls = re.findall(URL_REGEX, message.text)
                    project_urls = [u for u in urls if not ('t.me/' in u and u.count('/') <= 4)]

                    # 4. Telegram Handle extraction (filter out email domains and channel itself)
                    raw_handles = re.findall(TELEGRAM_HANDLE_REGEX, message.text)
                    clean_handles = []
                    for h in raw_handles:
                        h_lower = h.lower()
                        if h_lower in (f"@{channel_username}".lower(), "@gmail", "@yahoo", "@outlook", "@mail", "@proton", "@yandex"):
                            continue
                        clean_handles.append(h)

                    # Primary handle
                    primary_handle = clean_handles[0] if clean_handles else (username if username != "Unknown" and username != f"@{channel_username}" else "")
                    
                    # 5. Direct Action Links
                    # Telegram Direct DM Link
                    tg_dm_link = f"https://t.me/{primary_handle.replace('@', '')}" if primary_handle and primary_handle != f"@{channel_username}" else ""
                    
                    # WhatsApp Direct Click-to-Chat Link
                    primary_phone = valid_phones[0] if valid_phones else ""
                    clean_phone_digits = re.sub(r'\D', '', primary_phone)
                    wa_link = f"https://wa.me/{clean_phone_digits}" if len(clean_phone_digits) >= 10 else ""

                    email_str = ", ".join(set(valid_emails)) if valid_emails else ""
                    phone_str = primary_phone
                    url_str = project_urls[0] if project_urls else (urls[0] if urls else "")
                    handle_str = ", ".join(set(clean_handles)) if clean_handles else primary_handle

                    lead = {
                        "Channel/Group": f"@{channel_username}",
                        "Sender Username": username,
                        "Contact Email": email_str,
                        "Contact Phone": phone_str,
                        "WhatsApp Link": wa_link,
                        "Telegram DM Link": tg_dm_link,
                        "Contact Handle": handle_str,
                        "Project URL": url_str,
                        "Message": message.text.replace("\n", " ")[:300],
                        "Found Keywords": ", ".join(matched_keywords),
                        "Date": str(message.date)
                    }

                    save_to_csv(lead)
                    collected_leads.append(lead)
                    total_saved += 1
                    
                    lead_label = email_str or handle_str or tg_dm_link or "Post"
                    print(f"  [SAVED] {lead_label} | Channel: @{channel_username}")

        except Exception as e:
            print(f"  [ERROR] Could not scan @{channel_username}: {e}")

    print(f"\n[SUCCESS] Telegram scraping complete! Saved {total_saved} potential leads to '{CSV_FILE}'.")
    try:
        await client.disconnect()
    except Exception:
        pass

    return collected_leads


def run_telegram_scraper_sync() -> List[Dict[str, Any]]:
    """Synchronous entry point for scraper runners."""
    import asyncio
    try:
        return asyncio.run(scrape_telegram_leads())
    except Exception as err:
        print(f"  [telegram_scraper notice] {err}")
        return []


if __name__ == "__main__":
    import asyncio
    asyncio.run(scrape_telegram_leads())
