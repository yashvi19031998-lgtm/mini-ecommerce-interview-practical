import csv
import os
import re
import time
from typing import List, Dict, Any
from playwright.sync_api import sync_playwright

CSV_FILE = "google_maps_leads.csv"


def init_csv():
    """Initializes CSV file with header if it doesn't already exist."""
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode="w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "Business Name",
                    "Rating",
                    "Reviews Count",
                    "Phone",
                    "Website",
                    "Address",
                    "Category",
                    "City",
                    "Google Maps URL",
                ],
            )
            writer.writeheader()


def save_lead_to_csv(lead_data: Dict[str, Any]):
    """Appends a single lead to the CSV."""
    init_csv()
    with open(CSV_FILE, mode="a", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=lead_data.keys())
        writer.writerow(lead_data)


def scrape_google_maps(
    search_query: str = "Software Development Company",
    location: str = "Ahmedabad",
    max_results: int = 30,
    headless: bool = True
) -> List[Dict[str, Any]]:
    """
    Scrapes business listings from Google Maps using Playwright.
    :param search_query: What to search for (e.g., 'Software Development Company')
    :param location: City or area (e.g., 'Ahmedabad')
    :param max_results: Maximum number of leads to extract
    :param headless: Run Playwright browser in headless mode (default: True)
    :return: List of collected lead dictionaries
    """
    init_csv()

    full_query = f"{search_query} in {location}"
    url = f"https://www.google.com/maps/search/{full_query.replace(' ', '+')}"

    print(f"\n[INFO] Starting Google Maps Scraper for: '{search_query}' in '{location}'")
    print(f"[INFO] Target URL: {url}")

    collected_leads: List[Dict[str, Any]] = []
    seen_leads = set()
    total_saved = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )

        page = context.new_page()

        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(4)

            # Scroll pane to load results
            print("[INFO] Scrolling sidebar to load listings...")

            # The scrollable container in Google Maps sidebar
            sidebar_selector = 'div[role="feed"]'

            scroll_attempts = 0
            max_scrolls = 20

            while total_saved < max_results and scroll_attempts < max_scrolls:
                # Find all business cards in the feed
                cards = page.locator('div[role="feed"] > div > a[href*="/maps/place/"]').all()

                if not cards:
                    # Alternative fallback selector for links
                    cards = page.locator('a[href*="/maps/place/"]').all()

                for card in cards:
                    if total_saved >= max_results:
                        break

                    try:
                        href = card.get_attribute("href")
                        aria_label = card.get_attribute("aria-label")

                        if not aria_label or not href or href in seen_leads:
                            continue

                        seen_leads.add(href)

                        # Click on the card to open detailed view in the sidebar pane
                        card.click()
                        time.sleep(2.5)  # Wait for details panel to load

                        # Extract Business Name
                        name = aria_label

                        # Extract Rating & Reviews from the active details pane
                        rating = "N/A"
                        reviews = "0"
                        try:
                            rating_el = page.locator('div.F7nice span[aria-hidden="true"]').first
                            if rating_el.count() > 0:
                                rating = rating_el.inner_text().strip()

                            rev_el = page.locator('div.F7nice span[aria-label*="reviews"]').first
                            if rev_el.count() > 0:
                                rev_text = rev_el.get_attribute("aria-label") or ""
                                rev_match = re.search(r"([\d,]+)", rev_text)
                                if rev_match:
                                    reviews = rev_match.group(1).replace(",", "")
                        except Exception:
                            pass

                        # Extract Address
                        address = "N/A"
                        try:
                            addr_btn = page.locator('button[data-item-id="address"]').first
                            if addr_btn.count() > 0:
                                raw_addr = addr_btn.get_attribute("aria-label") or ""
                                address = raw_addr.replace("Address: ", "").strip()
                        except Exception:
                            pass

                        # Extract Phone Number
                        phone = "Not Available"
                        try:
                            phone_btn = page.locator('button[data-item-id^="phone:tel:"]').first
                            if phone_btn.count() > 0:
                                phone_text = phone_btn.get_attribute("aria-label") or ""
                                phone_match = re.search(r"([\d\s\-\+\(\)]+)", phone_text.replace("Phone: ", ""))
                                if phone_match:
                                    phone = phone_match.group(1).strip()
                        except Exception:
                            pass

                        # Extract Website
                        website = "N/A"
                        try:
                            web_btn = page.locator('a[data-item-id="authority"]').first
                            if web_btn.count() > 0:
                                website = (web_btn.get_attribute("href") or "").strip()
                        except Exception:
                            pass

                        lead = {
                            "Business Name": name,
                            "Rating": rating,
                            "Reviews Count": reviews,
                            "Phone": phone if phone != "Not Available" else "",
                            "Website": website if website != "N/A" else "",
                            "Address": address.replace("\n", " ") if address != "N/A" else "",
                            "Category": search_query,
                            "City": location,
                            "Google Maps URL": href,
                        }

                        save_lead_to_csv(lead)
                        collected_leads.append(lead)
                        total_saved += 1
                        print(f"  [{total_saved}/{max_results}] Saved: {name} | Phone: {phone} | Web: {website}")

                    except Exception as err:
                        continue

                # Scroll down inside the sidebar feed
                try:
                    page.locator(sidebar_selector).evaluate("node => node.scrollBy(0, 1000)")
                except Exception:
                    page.mouse.wheel(0, 1000)

                time.sleep(2)
                scroll_attempts += 1

            print(f"\n[SUCCESS] Google Maps scraping complete! Saved {total_saved} records to '{CSV_FILE}'.")

        except Exception as e:
            print(f"[ERROR] An unexpected error occurred: {e}")
        finally:
            browser.close()

    return collected_leads


if __name__ == "__main__":
    # Example usage:
    scrape_google_maps(
        search_query="Software Development Company",
        location="Ahmedabad",
        max_results=20,
        headless=False
    )
