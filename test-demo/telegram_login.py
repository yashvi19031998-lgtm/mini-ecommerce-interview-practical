"""
One-time helper: log in to Telegram interactively and print a StringSession.

    python telegram_login.py

Copy the printed string into:
  - .env                        -> TELEGRAM_SESSION_STRING=...   (local)
  - GitHub repo secret           -> TELEGRAM_SESSION_STRING       (CI)

Treat that string like a password: anyone who has it can use your Telegram account.
"""

from telethon.sync import TelegramClient
from telethon.sessions import StringSession

import telegram_scraper  # loads .env

api_id = telegram_scraper.API_ID or int(input("TELEGRAM_API_ID: "))
api_hash = telegram_scraper.API_HASH or input("TELEGRAM_API_HASH: ").strip()

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("\nLogged in. Your session string (keep it secret):\n")
    print(client.session.save())
