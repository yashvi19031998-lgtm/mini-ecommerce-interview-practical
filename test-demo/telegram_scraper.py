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
API_ID = int(os.environ.get("TELEGRAM_API_ID", "12345678"))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "your_api_hash_here")
SESSION_NAME = os.environ.get("TELEGRAM_SESSION_NAME", "lead_scraper_session")

CSV_FILE = "telegram_leads.csv"

# Target Public Groups/Channels known for client posts
TARGET_CHANNELS = [
    'remote_jobs_bot',       # Example tech job channel
    'freelance_work_board',  # Example freelance board
    'python_jobs'            # Python specific channel
]

# Keywords to filter high-intent client messages
KEYWORDS = ['looking for', 'hiring', 'need a developer', 'budget', 'freelancer', 'project']


def init_csv():
    """Initializes CSV file if not exists."""
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "Channel/Group",
                "Sender Username",
                "Message",
                "Found Keywords",
                "Date"
            ])
            writer.writeheader()


def save_to_csv(lead_data: Dict[str, Any]):
    """Appends a lead to the CSV."""
    init_csv()
    with open(CSV_FILE, mode="a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=lead_data.keys())
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

                    lead = {
                        "Channel/Group": f"@{channel_username}",
                        "Sender Username": username,
                        "Message": message.text.replace("\n", " ")[:300],
                        "Found Keywords": ", ".join(matched_keywords),
                        "Date": str(message.date)
                    }

                    save_to_csv(lead)
                    collected_leads.append(lead)
                    total_saved += 1
                    print(f"  [FOUND] Lead from {username} in @{channel_username}")

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
